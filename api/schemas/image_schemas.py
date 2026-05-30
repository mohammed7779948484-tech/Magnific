"""Pydantic schemas for image generation API."""

from typing import Any

from pydantic import BaseModel, Field


class ImageReferenceInput(BaseModel):
    """Input for a reference image in image generation.

    For render/v4, references must be base64 + id + label format.
    """
    image_base64: str | None = Field(None, description="Base64 data URI of the reference image")
    image_path: str | None = Field(None, description="Local file path of the reference image")
    label: str = Field(..., description="Reference label (becomes @label in prompt)")
    type: str = Field("reference", description="reference or style")
    category: str = Field("product", description="character, product, image, composition, style")


class ImageRequest(BaseModel):
    """Image generation request."""
    prompt: str = Field(..., description="Text prompt for image generation")
    model: str = Field("imagen-nano-banana-2", description="Model slug")
    aspect_ratio: str = Field("1:1", description="Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 21:9)")
    resolution: str = Field("4k", description="Resolution: 1k, 2k, 4k")
    negative_prompt: str | None = Field(None, description="Negative prompt")
    references: list[ImageReferenceInput] = Field(default_factory=list, description="Reference images")
    num_images: int = Field(1, description="Number of images to generate")
    seed: int | None = Field(None, description="Random seed")
    wait: bool = Field(True, description="Wait for completion before responding")
    download: bool = Field(False, description="Download and return base64 data")


class ImageResponse(BaseModel):
    """Image generation response."""
    success: bool
    creation_id: str | int | None = None
    family: str | None = None
    status: str = "processing"
    image_url: str | None = None
    image_base64: str | None = None
    message: str | None = None
    elapsed: float | None = None
