"""Pydantic schemas for asset management API."""

from typing import Any

from pydantic import BaseModel, Field


class AssetInfo(BaseModel):
    """Detailed information about a stored asset."""

    id: str = Field(..., description="Asset registry ID")
    asset_type: str = Field(..., description="image or video")
    model: str = Field(..., description="Model slug used for generation")
    creation_id: str = Field(..., description="Magnific creation ID")
    public_id: str = Field(..., description="Cloudinary public ID")
    cloudinary_url: str = Field(..., description="Cloudinary secure URL")
    original_url: str | None = Field(None, description="Original Magnific CDN URL")
    resource_type: str = Field("image", description="Cloudinary resource type")
    bytes: int = Field(0, description="File size in bytes")
    width: int | None = Field(None, description="Image width")
    height: int | None = Field(None, description="Image height")
    duration: float | None = Field(None, description="Video duration in seconds")
    format: str = Field("", description="File format (png, jpg, mp4, etc.)")
    prompt: str = Field("", description="Prompt used for generation")
    created_at: str = Field("", description="ISO timestamp")
    last_used_at: str = Field("", description="Last used timestamp")
    use_count: int = Field(0, description="Times used as reference")
    tags: list[str] = Field(default_factory=list, description="Custom tags")


class AssetsListResponse(BaseModel):
    """Response for listing assets."""

    success: bool = True
    assets: list[AssetInfo] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class AssetsStatsResponse(BaseModel):
    """Response for asset statistics."""

    success: bool = True
    stats: dict[str, Any] = Field(default_factory=dict)


class AssetDeleteResponse(BaseModel):
    """Response for deleting an asset."""

    success: bool
    message: str
    cloudinary_deleted: bool = False
    registry_deleted: bool = False


class CloudinaryConfigResponse(BaseModel):
    """Response for Cloudinary configuration status."""

    success: bool = True
    enabled: bool = False
    cloud_name: str | None = None
    folder: str = ""
    message: str = ""


class AssetReferenceInput(BaseModel):
    """Input for using a stored asset as a reference.

    When using a cloud-stored asset as a reference for generation,
    just provide the asset_id and the system resolves the Cloudinary URL
    to the proper format (base64 for images, URL for videos).
    """

    asset_id: str = Field(..., description="Registry asset ID to use as reference")
    label: str = Field("reference", description="Reference label (becomes @label in prompt)")
    type: str = Field("reference", description="reference or style (for image refs)")
    category: str = Field("product", description="character, product, image, composition, style")
