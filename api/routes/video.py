"""Video generation API routes."""

import time

from fastapi import APIRouter

from api.schemas.video_schemas import KeyframeInput, VideoReferenceInput, VideoRequest, VideoResponse
from config.endpoints import Endpoints
from core.client import MagnificClient
from core.poller import Poller
from core.uploader import Uploader
from models.base import ModelRegistry
from utils.file_helpers import FileHelpers
from utils.logger import setup_logger

logger = setup_logger("api.video")

router = APIRouter(prefix="/api/video", tags=["Video Generation"])

_client: MagnificClient | None = None
_poller: Poller | None = None
_uploader: Uploader | None = None


def set_deps(client: MagnificClient, poller: Poller, uploader: Uploader):
    global _client, _poller, _uploader
    _client = client
    _poller = poller
    _uploader = uploader


@router.post("/generate", response_model=VideoResponse)
async def generate_video(request: VideoRequest) -> VideoResponse:
    """Generate a video using the specified model."""
    assert _client is not None, "API not initialized"
    assert _poller is not None, "Poller not initialized"
    assert _uploader is not None, "Uploader not initialized"

    start_time = time.time()

    # Get the model
    model = ModelRegistry.get_video(request.model)

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
                    uploaded_url = _uploader.upload_reference_frame(file_path=ref.url)
                    ref_dict["url"] = uploaded_url
                elif ref.type in ("video", "audio"):
                    result = _uploader.upload_video_audio(file_path=ref.url)
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

    result = _client.post(
        f"/api/video/generate?return_creations=true",
        json_data=video_body,
        headers=headers,
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

    if not request.wait:
        return VideoResponse(
            success=True,
            creation_id=creation_id,
            status="processing",
            message="Video generation started. Use GET /api/status/{id}?type=video to check progress.",
            elapsed=time.time() - start_time,
        )

    # Poll for completion
    poll_result = _poller.poll_creation(creation_id, creation_type="video")
    download_url = poll_result.get("download_url")
    elapsed = time.time() - start_time

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
            raw = _client.session.get(
                download_url,
                headers={"Referer": f"{Endpoints.BASE_URL}/"},
            )
            if raw.status_code == 200:
                import base64
                response.video_base64 = base64.b64encode(raw.content).decode("utf-8")
        except Exception as e:
            logger.warning(f"Download for base64 failed: {e}")

    return response
