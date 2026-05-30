"""Common Pydantic schemas for API requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    detail: str | None = None
    status_code: int | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    authenticated: bool = False
    version: str = "1.0.0"


class StatusResponse(BaseModel):
    """Creation status response."""
    success: bool
    creation_id: str | int
    status: str
    url: str | None = None
    download_url: str | None = None
    image_base64: str | None = None
    video_base64: str | None = None
    elapsed: float | None = None


class ModelsResponse(BaseModel):
    """Available models response."""
    success: bool = True
    image: list[dict[str, Any]] = Field(default_factory=list)
    video: list[dict[str, Any]] = Field(default_factory=list)
