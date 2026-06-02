"""Image generation API routes."""

import asyncio
import base64 as _base64
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from api.schemas.image_schemas import ImageReferenceInput, ImageRequest, ImageResponse
from config.endpoints import Endpoints
from core.client import MagnificClient
from core.poller import Poller
from core.uploader import Uploader
from models.base import ModelRegistry
from utils.file_helpers import FileHelpers
from utils.logger import setup_logger
from utils.retry import retry_with_backoff

logger = setup_logger("api.image")

router = APIRouter(prefix="/api/image", tags=["Image Generation"])

# These will be set during app initialization
_client: MagnificClient | None = None
_poller: Poller | None = None
_uploader: Uploader | None = None
_queue_manager: Any = None  # Optional: QueueManager for smart queue clearing
_registry: Any = None  # Optional: CreationRegistry for tracking our creations
_cloudinary_service: Any = None  # Optional: CloudinaryService for cloud storage
_asset_registry: Any = None  # Optional: AssetRegistry for tracking stored assets


def set_deps(client: MagnificClient, poller: Poller, uploader: Uploader,
             queue_manager=None, creation_registry=None,
             cloudinary_service=None, asset_registry=None):
    """Set shared dependencies from the server."""
    global _client, _poller, _uploader, _queue_manager, _registry
    global _cloudinary_service, _asset_registry
    _client = client
    _poller = poller
    _uploader = uploader
    _queue_manager = queue_manager
    _registry = creation_registry
    _cloudinary_service = cloudinary_service
    _asset_registry = asset_registry


# ── Sync wrappers with retry — run via asyncio.to_thread to avoid blocking ──

def _do_post(endpoint: str, **kwargs) -> dict:
    """Sync wrapper around _client.post for use with retry + to_thread."""
    return _client.post(endpoint, **kwargs)  # type: ignore[union-attr]


def _do_poll(creation_id: str, **kwargs) -> dict:
    """Sync wrapper around _poller.poll_creation for use with retry + to_thread."""
    return _poller.poll_creation(creation_id, **kwargs)  # type: ignore[union-attr]


_post_with_retry = retry_with_backoff(max_retries=3, initial_delay=10.0)(_do_post)
_poll_with_retry = retry_with_backoff(max_retries=3, initial_delay=10.0)(_do_poll)


def _resolve_reference_base64(ref: ImageReferenceInput) -> str | None:
    """Resolve a reference to base64 data URI.

    Supports:
        1. image_base64 — direct base64 data URI
        2. image_path — local file path → convert to base64
        3. Cloudinary URL (image_base64 field) — download from cloud → convert to base64

    Returns:
        Base64 data URI string, or None if cannot resolve
    """
    if ref.image_base64:
        # Check if it's a Cloudinary URL (reusable reference)
        if (_cloudinary_service
                and _cloudinary_service.is_enabled()
                and _cloudinary_service.is_cloudinary_url(ref.image_base64)):
            try:
                public_id = CloudinaryService.extract_public_id_from_url(ref.image_base64)
                if public_id:
                    mime = "image/png"  # Default MIME
                    b64 = _cloudinary_service.download_as_base64(public_id, mime_type=mime)
                    logger.info(f"Resolved Cloudinary reference: {public_id}")

                    # Track usage in registry
                    if _asset_registry:
                        record = _asset_registry.get_by_cloudinary_url(ref.image_base64)
                        if record:
                            _asset_registry.mark_used(record.id)

                    return b64
            except Exception as e:
                logger.warning(f"Failed to resolve Cloudinary URL as reference: {e}")
                return ref.image_base64

        return ref.image_base64

    if ref.image_path:
        try:
            return FileHelpers.file_to_base64(ref.image_path)
        except Exception as e:
            logger.error(f"Failed to read reference file: {e}")
            return None

    return None


def _upload_to_cloud(
    creation_id: str,
    model_slug: str,
    download_url: str,
    prompt: str,
) -> dict | None:
    """Upload a generated image to Cloudinary cloud storage.

    Called after generation completes to persist the result in the cloud.
    Also registers the asset in the local registry for future reference reuse.

    Args:
        creation_id: Magnific creation ID
        model_slug: Model slug used
        download_url: CDN URL of the generated image
        prompt: The prompt used for generation

    Returns:
        Dict with cloudinary_url and public_id, or None if upload disabled/failed
    """
    if not _cloudinary_service or not _cloudinary_service.is_enabled():
        return None

    try:
        public_id = _cloudinary_service.build_public_id(
            asset_type="image",
            model_slug=model_slug,
            creation_id=str(creation_id),
        )

        result = _cloudinary_service.upload_from_url(
            url=download_url,
            public_id=public_id,
            resource_type="image",
        )

        cloudinary_url = result.get("url", "")

        # Register in asset registry
        if _asset_registry and cloudinary_url:
            _asset_registry.register(
                asset_type="image",
                model=model_slug,
                creation_id=str(creation_id),
                public_id=result.get("public_id", public_id),
                cloudinary_url=cloudinary_url,
                original_url=download_url,
                resource_type="image",
                bytes=result.get("bytes", 0),
                width=result.get("width"),
                height=result.get("height"),
                format=result.get("format", "png"),
                prompt=prompt,
            )
            logger.info(f"Image stored in cloud: {cloudinary_url}")

        return {
            "cloudinary_url": cloudinary_url,
            "public_id": result.get("public_id", public_id),
        }
    except Exception as e:
        logger.warning(f"Cloud upload failed (non-fatal): {e}")
        return None


@router.post("/generate", response_model=ImageResponse)
async def generate_image(request: ImageRequest) -> ImageResponse:
    """Generate an image using the specified model.

    Supports both simple generation (no references) and reference-based generation.
    Generated images are automatically uploaded to Cloudinary cloud storage
    for persistence and reuse as future references.
    """
    if _client is None:
        raise HTTPException(status_code=503, detail="API client not initialized. Server may still be starting up.")
    if _poller is None:
        raise HTTPException(status_code=503, detail="Poller not initialized.")
    if _uploader is None:
        raise HTTPException(status_code=503, detail="Uploader not initialized.")

    start_time = time.time()

    # Get the model
    model = ModelRegistry.get_image(request.model)

    # ★ Queue clearing hook: clear external queue before our generation
    if _queue_manager is not None and _queue_manager.is_enabled:
        try:
            await asyncio.to_thread(_queue_manager.clear_external_queue)
        except Exception as e:
            logger.warning(f"Queue clearing failed (non-fatal): {e}")

    # Calculate dimensions
    from config.constants import AspectRatios
    width, height = AspectRatios.dimensions(request.aspect_ratio, request.resolution)

    # Process references if any
    temporal_refs = []  # For start-tti-v2
    render_refs = []    # For render/v4

    for ref in request.references:
        b64 = _resolve_reference_base64(ref)
        if not b64:
            continue

        # Upload to temporal storage for start-tti-v2
        try:
            upload_result = await asyncio.to_thread(_uploader.upload_temporal, base64_data=b64)
            temporal_path = upload_result.get("path", "")
            if temporal_path:
                temporal_refs.append({
                    "image": f"temporal:{temporal_path}",
                    "type": ref.type,
                    "category": ref.category,
                    "label": ref.label,
                    "frame": None,
                })
        except Exception as e:
            logger.warning(f"Temporal upload failed for {ref.label}: {e}")

        # Prepare base64 + id + label for render/v4
        render_refs.append({
            "id": ref.label,
            "label": ref.label,
            "image": b64,
            "type": ref.type,
            "category": ref.category,
            "frame": None,
        })

    # Step 1: start-tti-v2
    start_body = model.build_start_tti_body(
        prompt=request.prompt,
        aspect_ratio=request.aspect_ratio,
        num_images=request.num_images,
        references=temporal_refs,
    )

    tti_result = await asyncio.to_thread(_post_with_retry, "/api/start-tti-v2", json_data=start_body)
    request_token = tti_result.get("request_tokens", [None])[0]
    family = tti_result.get("family")

    if not request_token:
        return ImageResponse(
            success=False,
            status="error",
            message="Failed to get request token from start-tti-v2",
        )

    # Step 2: render/v4
    render_body = model.build_render_body(
        prompt=request.prompt,
        family=family,
        request_token=request_token,
        aspect_ratio=request.aspect_ratio,
        resolution=request.resolution,
        width=width,
        height=height,
        seed=request.seed,
        negative_prompt=request.negative_prompt,
        image_references=render_refs,
        num_images=request.num_images,
    )

    render_result = await asyncio.to_thread(_post_with_retry, "/api/render/v4", json_data=render_body)

    # Extract creation ID and identifier
    creation_data = render_result.get("creation", {})
    creation_id = creation_data.get("id")
    creation_identifier = creation_data.get("identifier")

    if not creation_id and isinstance(render_result, dict):
        # Try alternative response format
        creation_id = render_result.get("id") or render_result.get("creation_id")

    # ★ Registry hook: register our creation
    if _registry is not None and creation_identifier:
        try:
            _registry.register(creation_identifier, metadata={
                "creation_id": creation_id,
                "tool": "text-to-image",
                "model": request.model,
            })
        except Exception as e:
            logger.warning(f"Registry register failed (non-fatal): {e}")

    if not creation_id:
        return ImageResponse(
            success=True,
            status="submitted",
            family=family,
            message="Generation submitted but creation ID not found in response",
            elapsed=time.time() - start_time,
        )

    if not request.wait:
        return ImageResponse(
            success=True,
            creation_id=creation_id,
            family=family,
            status="processing",
            message="Generation started. Use GET /api/status/{id}?type=image to check progress.",
            elapsed=time.time() - start_time,
        )

    # Step 3: Poll for completion
    poll_result = await asyncio.to_thread(_poll_with_retry, creation_id, creation_type="image")
    download_url = poll_result.get("download_url")
    elapsed = time.time() - start_time

    # ★ Registry hook: unregister on completion
    if _registry is not None and creation_identifier:
        try:
            _registry.unregister(creation_identifier)
        except Exception as e:
            logger.warning(f"Registry unregister failed (non-fatal): {e}")

    response = ImageResponse(
        success=True,
        creation_id=creation_id,
        family=family,
        status="completed",
        image_url=download_url,
        elapsed=elapsed,
    )

    # Step 4: Optionally download and return base64
    if request.download and download_url:
        try:
            raw = await asyncio.to_thread(
                _client.session.get,
                download_url,
                headers={"Referer": f"{Endpoints.BASE_URL}/"},
            )
            if raw.status_code == 200:
                b64_data = _base64.b64encode(raw.content).decode("utf-8")
                response.image_base64 = f"data:image/png;base64,{b64_data}"
        except Exception as e:
            logger.warning(f"Download for base64 failed: {e}")

    # ★ Step 5: Upload to Cloudinary cloud storage (async, non-blocking)
    if download_url and response.success:
        try:
            cloud_result = await asyncio.to_thread(
                _upload_to_cloud,
                creation_id,
                request.model,
                download_url,
                request.prompt,
            )
            if cloud_result:
                response.cloudinary_url = cloud_result.get("cloudinary_url")
        except Exception as e:
            logger.warning(f"Cloud upload post-generation failed (non-fatal): {e}")

    return response
