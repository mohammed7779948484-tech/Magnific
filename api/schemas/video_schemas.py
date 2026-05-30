"""Pydantic schemas for video generation API."""

from typing import Any

from pydantic import BaseModel, Field


class KeyframeInput(BaseModel):
    """Keyframe input for video generation."""
    type: str = Field("image", description="Type: image, video, sketch")
    url: str = Field(..., description="URL of the keyframe image")


class VideoReferenceInput(BaseModel):
    """Input for a reference in video generation.

    Video references use URLs (not base64) — opposite of image references.
    """
    type: str = Field("image", description="image, video, or audio")
    url: str = Field(..., description="URL of the reference (CDN, uploaded, or temporal)")
    name: str = Field(..., description="Reference name (becomes @name in prompt)")


class VideoRequest(BaseModel):
    """Video generation request."""
    prompt: str = Field(..., description="Text prompt for video generation")
    model: str = Field("bytedance-seedance-pro-2.0", description="Model slug")
    aspect_ratio: str = Field("16:9", description="Aspect ratio")
    duration: int = Field(5, description="Video duration in seconds")
    resolution: str = Field("1080p", description="Resolution: 1080p, 720p, 480p")
    negative_prompt: str = Field("", description="Negative prompt")
    references: list[VideoReferenceInput] = Field(default_factory=list, description="References (images, videos, audio)")
    keyframes: dict[str, KeyframeInput | None] | None = Field(None, description="Keyframes: start, end")
    audio_url: str | None = Field(None, description="Audio URL for background music")
    with_sound: bool = Field(False, description="Add AI sound effects")
    prompt_type: str = Field("basic", description="basic or multishot")
    seed: int | None = Field(None, description="Random seed")
    wait: bool = Field(True, description="Wait for completion before responding")
    download: bool = Field(False, description="Download and return base64 data")


class VideoResponse(BaseModel):
    """Video generation response."""
    success: bool
    creation_id: str | int | None = None
    status: str = "processing"
    video_url: str | None = None
    video_base64: str | None = None
    message: str | None = None
    elapsed: float | None = None
