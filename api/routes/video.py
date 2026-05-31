"""Video generation API routes."""

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from api.schemas.video_schemas import KeyframeInput, VideoReferenceInput, VideoRequest, VideoResponse
from config.endpoints import Endpoints
from core.client import MagnificClient
from core.poller import Poller
from core.uploader import Uploader
from models.base import ModelRegistry
from utils.file_helpers import FileHelpers
from utils.logger import setup_logger
from utils.retry import retry_with_backoff

logger = setup_logger("api.video")

router = APIRouter(prefix="/api/video", tags=["Video Generation"])

_client: MagnificClient | None = None
_poller: Poller | None = None
_uploader: Uploader | None = None
_queue_manager: Any = None  # Optional: QueueManager for smart queue clearing
_registry: Any = None  # Optional: CreationRegistry for tracking our creations


def set_deps(client: MagnificClient, poller: Poller, uploader: Uploader,
             queue_manager=None, creation_registry=None):
    global _client, _poller, _uploader, _queue_manager, _registry
    _client = client
    _poller = poller
    _uploader = uploader
    _queue_manager = queue_manager
    _registry = creation_registry


@retry_with_backoff(max_retries=3, initial_delay=15.0)
def _post_video_generate(path: str, json_data: dict, headers: dict) -> dict:
    """POST to video generate endpoint with retry on rate-limit errors."""
    return _client.post(path, json_data=json_data, headers=headers)  # type: ignore[union-attr]


@router.post("/generate", response_model=VideoResponse)
async def generate_video(request: VideoRequest) -> VideoResponse:
    """Generate a video using the specified model."""
    if _client is None:
        raise HTTPException(status_code=503, detail="API client not initialized. Server may still be starting up.")
    if _poller is None:
        raise HTTPException(status_code=503, detail="Poller not initialized.")
    if _uploader is None:
        raise HTTPException(status_code=503, detail="Uploader not initialized.")

    start_time = time.time()

    # Get the model
    model = ModelRegistry.get_video(request.model)

    # ★ Queue clearing hook: clear external queue before our generation
    if _queue_manager is not None and _queue_manager.is_enabled:
        try:
            await asyncio.to_thread(_queue_manager.clear_external_queue)
        except Exception as e:
            logger.warning(f"Queue clearing failed (non-fatal): {e}")

    # Process references — video refs use URLs
    refs = []
    audio_url = request.audio_url

    for ref in request.references:
        ref_dict = {
            "type": ref.type,
            "url": ref.url,
            "name": ref.name,
        }

        # If it's a local file, upload it
        if FileHelpers.is_url(ref.url) or ref.url.startswith("temporal:"):
            refs.append(ref_dict)
        else:
            # Local file — need to upload
            try:
                if ref.type == "image":
                    uploaded_url = await asyncio.to_thread(
                        _uploader.upload_reference_frame, file_path=ref.url
                    )
                    ref_dict["url"] = uploaded_url
                elif ref.type in ("video", "audio"):
                    result = await asyncio.to_thread(
                        _uploader.upload_video_audio, file_path=ref.url
                    )
                    uploaded_path = result.get("path", "")
                    ref_dict["url"] = f"temporal:{uploaded_path}" if uploaded_path else ref.url
                refs.append(ref_dict)
            except Exception as e:
                logger.warning(f"Failed to upload reference {ref.name}: {e}")
                refs.append(ref_dict)

        # First audio ref also goes to audioUrl
        if ref.type == "audio" and not audio_url:
            audio_url = ref.url

    # Process keyframes
    keyframes = None
    if request.keyframes:
        keyframes = {}
        for key, kf in request.keyframes.items():
            if kf is not None:
                keyframes[key] = {"type": kf.type, "url": kf.url}

    # Build video body using model
    video_body = model.build_video_body(
        prompt=request.prompt,
        aspect_ratio=request.aspect_ratio,
        duration=request.duration,
        resolution=request.resolution,
        negative_prompt=request.negative_prompt,
        references=refs,
        keyframes=keyframes,
        audio_url=audio_url,
        with_sound=request.with_sound,
        prompt_type=request.prompt_type,
        seed=request.seed,
    )

    # Add x-request-origin header for video generation
    headers = {"x-request-origin": "video_generator"}

    result = await asyncio.to_thread(
        _post_video_generate,
        f"/api/video/generate?return_creations=true",
        video_body,
        headers,
    )

    # Extract creation ID
    creations = result.get("data", {}).get("creations", [])
    if not creations:
        return VideoResponse(
            success=False,
            status="error",
            message=f"No creation returned. Response: {str(result)[:300]}",
            elapsed=time.time() - start_time,
        )

    creation_id = creations[0].get("id")
    creation_identifier = creations[0].get("identifier")

    # ★ Registry hook: register our creation
    if _registry is not None and creation_identifier:
        try:
            _registry.register(creation_identifier, metadata={
                "creation_id": creation_id,
                "tool": "video-generator",
                "model": request.model,
            })
        except Exception as e:
            logger.warning(f"Registry register failed (non-fatal): {e}")

    if not request.wait:
        return VideoResponse(
            success=True,
            creation_id=creation_id,
            status="processing",
            message="Video generation started. Use GET /api/status/{id}?type=video to check progress.",
            elapsed=time.time() - start_time,
        )

    # Poll for completion
    poll_result = await asyncio.to_thread(
        _poller.poll_creation, creation_id, creation_type="video"
    )
    download_url = poll_result.get("download_url")
    elapsed = time.time() - start_time

    # ★ Registry hook: unregister on completion
    if _registry is not None and creation_identifier:
        try:
            _registry.unregister(creation_identifier)
        except Exception as e:
            logger.warning(f"Registry unregister failed (non-fatal): {e}")

    response = VideoResponse(
        success=True,
        creation_id=creation_id,
        status="completed",
        video_url=download_url,
        elapsed=elapsed,
    )

    # Optionally download and return base64
    if request.download and download_url:
        try:
            raw = await asyncio.to_thread(
                _client.session.get,
                download_url,
                headers={"Referer": f"{Endpoints.BASE_URL}/"},
            )
            if raw.status_code == 200:
                import base64
                response.video_base64 = base64.b64encode(raw.content).decode("utf-8")
        except Exception as e:
            logger.warning(f"Download for base64 failed: {e}")

    return response
