"""Pydantic schemas for video generation API."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.constants import AspectRatios, Resolutions


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

    prompt: str = Field(..., min_length=1, max_length=2000, description="Text prompt for video generation")
    model: str = Field("bytedance-seedance-pro-2.0", description="Model slug")
    aspect_ratio: str = Field("16:9", description="Aspect ratio")
    duration: int = Field(5, ge=1, le=30, description="Video duration in seconds (1-30)")
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

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect_ratio(cls, v: str) -> str:
        if v not in AspectRatios.DATA:
            raise ValueError(
                f"Invalid aspect_ratio '{v}'. "
                f"Must be one of: {', '.join(AspectRatios.DATA.keys())}"
            )
        return v

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        if v not in Resolutions.VIDEO:
            raise ValueError(
                f"Invalid resolution '{v}'. Must be one of: {', '.join(Resolutions.VIDEO)}"
            )
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: int, info) -> int:
        """Validate duration is within the model's allowed range.

        If the model is known to ModelRegistry, additionally checks
        the model-specific duration_range. Falls back to global 1-30.
        """
        if v < 1 or v > 30:
            raise ValueError(f"Duration must be between 1 and 30 seconds, got {v}")

        # Model-specific validation (non-fatal if registry not loaded)
        try:
            from models.base import ModelRegistry
            model = ModelRegistry.get_video(info.data.get("model", ""))
            min_d, max_d = model.duration_range
            if v < min_d or v > max_d:
                raise ValueError(
                    f"Model '{model.slug}' supports duration {min_d}-{max_d}s, got {v}s"
                )
        except (ValueError, KeyError):
            pass  # Model not registered — skip model-specific check

        return v


class VideoResponse(BaseModel):
    """Video generation response."""
    success: bool
    creation_id: str | int | None = None
    status: str = "processing"
    video_url: str | None = None
    video_base64: str | None = None
    message: str | None = None
    elapsed: float | None = None
