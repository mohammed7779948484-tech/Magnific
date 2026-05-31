"""Pydantic schemas for the monitoring API endpoints.

Defines request parameters and response models for the monitor router.
"""

from typing import Any

from pydantic import BaseModel, Field


class QueueItem(BaseModel):
    """A creation currently in the queue."""
    id: int | None = None
    tool: str | None = None
    model: str | None = None
    position: int | None = None
    expected_queued_time: int | None = None
    expected_generation_time: int | None = None
    prompt: str | None = None
    created_at: str | None = None
    date_for_humans: str | None = None


class ProcessingItem(BaseModel):
    """A creation currently being processed."""
    id: int | None = None
    tool: str | None = None
    model: str | None = None
    expected_generation_time: int | None = None
    prompt: str | None = None
    created_at: str | None = None
    date_for_humans: str | None = None


class QueueOverview(BaseModel):
    """Snapshot of current queue state."""
    queued: int = 0
    processing: int = 0
    queued_items: list[QueueItem] = Field(default_factory=list)
    processing_items: list[ProcessingItem] = Field(default_factory=list)
    total_active: int = 0
    checked_at: str | None = None


class CreationSummary(BaseModel):
    """Flattened creation for list views."""
    id: int | str | None = None
    status: str | None = None
    tool: str | None = None
    model: str | None = None
    prompt: str | None = None
    url: str | None = None
    created_at: str | None = None
    date_for_humans: str | None = None
    credits_used: dict[str, Any] | None = None
    resolution: str | None = None
    aspect_ratio: str | None = None
    width: int | None = None
    height: int | None = None


class MonitorStats(BaseModel):
    """Aggregate statistics across all creation statuses."""
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    checked_at: str | None = None


class PaginationParams(BaseModel):
    """Validated pagination query parameters."""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=50)
    sort: str = Field(default="-createdAt")
    status: str | None = None


class MonitorHealthResponse(BaseModel):
    """Monitor subsystem health check."""
    status: str = "ok"
    detail: str | None = None
