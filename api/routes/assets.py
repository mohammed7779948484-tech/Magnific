"""Asset management API routes.

Endpoints for browsing, searching, and managing cloud-stored assets.
Also provides endpoints for using stored assets as references in
new generations without re-uploading.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.schemas.asset_schemas import (
    AssetDeleteResponse,
    AssetInfo,
    AssetsListResponse,
    AssetsStatsResponse,
    CloudinaryConfigResponse,
)
from utils.logger import setup_logger

logger = setup_logger("api.assets")

router = APIRouter(prefix="/api/assets", tags=["Asset Management"])

# Dependencies — set during app initialization
_cloudinary_service: Any = None
_asset_registry: Any = None


def set_deps(cloudinary_service=None, asset_registry=None):
    """Set shared dependencies from the server."""
    global _cloudinary_service, _asset_registry
    _cloudinary_service = cloudinary_service
    _asset_registry = asset_registry


@router.get("/config", response_model=CloudinaryConfigResponse)
async def get_cloudinary_config() -> CloudinaryConfigResponse:
    """Check Cloudinary configuration status."""
    if _cloudinary_service is None:
        return CloudinaryConfigResponse(
            enabled=False,
            message="Cloudinary service not initialized"
        )

    enabled = _cloudinary_service.is_enabled()
    return CloudinaryConfigResponse(
        enabled=enabled,
        cloud_name=_cloudinary_service.folder if enabled else None,
        folder=_cloudinary_service.folder,
        message="Cloudinary active and connected" if enabled else "Cloudinary disabled or not configured",
    )


@router.get("", response_model=AssetsListResponse)
async def list_assets(
    asset_type: str | None = Query(None, description="Filter: image or video"),
    model: str | None = Query(None, description="Filter by model slug"),
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Skip N results"),
) -> AssetsListResponse:
    """List stored assets with optional filtering.

    Returns metadata about all cloud-stored assets. Use the
    cloudinary_url to display thumbnails or download the full asset.
    """
    if _asset_registry is None:
        raise HTTPException(status_code=503, detail="Asset registry not initialized")

    records = _asset_registry.list_assets(
        asset_type=asset_type,
        model=model,
        tag=tag,
        limit=limit,
        offset=offset,
    )

    assets = [
        AssetInfo(**record.to_dict()) for record in records
    ]

    return AssetsListResponse(
        assets=assets,
        total=len(_asset_registry.list_assets(
            asset_type=asset_type, model=model, tag=tag,
            limit=999999, offset=0,
        )),
        offset=offset,
        limit=limit,
    )


@router.get("/stats", response_model=AssetsStatsResponse)
async def get_stats() -> AssetsStatsResponse:
    """Get aggregate statistics about stored assets."""
    if _asset_registry is None:
        raise HTTPException(status_code=503, detail="Asset registry not initialized")

    return AssetsStatsResponse(stats=_asset_registry.stats())


@router.get("/{asset_id}", response_model=AssetInfo)
async def get_asset(asset_id: str) -> AssetInfo:
    """Get detailed info about a specific asset."""
    if _asset_registry is None:
        raise HTTPException(status_code=503, detail="Asset registry not initialized")

    record = _asset_registry.get(asset_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    return AssetInfo(**record.to_dict())


@router.delete("/{asset_id}", response_model=AssetDeleteResponse)
async def delete_asset(
    asset_id: str,
    delete_from_cloud: bool = Query(False, description="Also delete from Cloudinary"),
) -> AssetDeleteResponse:
    """Delete an asset from the registry and optionally from Cloudinary.

    If delete_from_cloud=true, also removes the file from Cloudinary
    storage. Otherwise only removes the local metadata record.
    """
    if _asset_registry is None:
        raise HTTPException(status_code=503, detail="Asset registry not initialized")

    record = _asset_registry.get(asset_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    # Delete from registry
    registry_deleted = _asset_registry.delete(asset_id)

    # Delete from Cloudinary if requested
    cloudinary_deleted = False
    if delete_from_cloud and _cloudinary_service and _cloudinary_service.is_enabled():
        try:
            resource_type = "video" if record.asset_type == "video" else "image"
            _cloudinary_service.delete(record.public_id, resource_type=resource_type)
            cloudinary_deleted = True
        except Exception as e:
            logger.error(f"Failed to delete from Cloudinary: {e}")

    return AssetDeleteResponse(
        success=registry_deleted,
        message=f"Asset '{asset_id}' deleted" if registry_deleted else f"Asset '{asset_id}' not found",
        cloudinary_deleted=cloudinary_deleted,
        registry_deleted=registry_deleted,
    )


@router.post("/{asset_id}/use")
async def mark_asset_used(asset_id: str) -> dict:
    """Mark an asset as used (increments use_count).

    Call this when an asset is used as a reference for a new generation
    to track reuse statistics.
    """
    if _asset_registry is None:
        raise HTTPException(status_code=503, detail="Asset registry not initialized")

    success = _asset_registry.mark_used(asset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    return {"success": True, "message": f"Asset '{asset_id}' marked as used"}
