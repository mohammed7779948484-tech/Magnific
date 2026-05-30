"""Status check and health routes."""

from fastapi import APIRouter, Query

from api.schemas.common_schemas import HealthResponse, ModelsResponse, StatusResponse
from core.client import MagnificClient
from core.poller import Poller
from models.base import ModelRegistry
from utils.logger import setup_logger

logger = setup_logger("api.status")

router = APIRouter(prefix="/api", tags=["Status"])

_client: MagnificClient | None = None
_poller: Poller | None = None


def set_deps(client: MagnificClient, poller: Poller):
    global _client, _poller
    _client = client
    _poller = poller


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and authentication status."""
    is_auth = _client is not None and _client.xsrf_token is not None
    return HealthResponse(
        status="ok",
        authenticated=is_auth,
    )


@router.get("/status/{creation_id}", response_model=StatusResponse)
async def check_status(
    creation_id: str,
    type: str = Query("image", description="Creation type: image or video"),
):
    """Check the status of a creation (image or video)."""
    assert _client is not None, "API not initialized"

    import time
    start = time.time()

    result = _client.get(f"/api/creation/{creation_id}")
    status = result.get("status", "unknown")

    url = None
    if type == "video":
        url = result.get("metadata", {}).get("url")
    else:
        url = result.get("url") or result.get("metadata", {}).get("url")

    return StatusResponse(
        success=True,
        creation_id=creation_id,
        status=status,
        url=url,
        download_url=url,
        elapsed=time.time() - start,
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List all available image and video models."""
    # Discover models if not already done
    if not ModelRegistry.list_images() and not ModelRegistry.list_videos():
        ModelRegistry.discover()

    image_models = [m.to_dict() for m in ModelRegistry.list_images().values()]
    video_models = [m.to_dict() for m in ModelRegistry.list_videos().values()]

    return ModelsResponse(
        success=True,
        image=image_models,
        video=video_models,
    )
