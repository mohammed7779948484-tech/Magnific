"""Pydantic schemas for queue control API endpoints.

Defines request parameters and response models for the queue router,
which provides smart queue clearing with ownership-awareness.
"""

from typing import Any

from pydantic import BaseModel, Field


class QueueItemWithOwnership(BaseModel):
    """A queued creation with ownership classification."""
    id: int | None = None
    identifier: str | None = None
    tool: str | None = None
    model: str | None = None
    is_ours: bool = False
    created_at: str | None = None


class QueueClearResponse(BaseModel):
    """Response from POST /api/queue/clear."""
    success: bool = True
    enabled: bool = False
    cleared: int = 0
    errors: int = 0
    skipped_ours: int = 0
    total_queued: int = 0
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None


class QueueStatusResponse(BaseModel):
    """Response from GET /api/queue/status."""
    total_queued: int = 0
    ours: int = 0
    external: int = 0
    items: list[QueueItemWithOwnership] = Field(default_factory=list)
    processing_count: int = 0
    auto_clear_enabled: bool = False
    checked_at: str | None = None


class QueueCancelResponse(BaseModel):
    """Response from POST /api/queue/cancel/{identifier}."""
    success: bool = True
    identifier: str | None = None
    message: str | None = None


class QueueConfigureRequest(BaseModel):
    """Request body for POST /api/queue/configure."""
    auto_clear: bool = False


class QueueConfigureResponse(BaseModel):
    """Response from POST /api/queue/configure."""
    auto_clear: bool = False
    message: str | None = None


class RegistryItem(BaseModel):
    """A single tracked creation in the registry."""
    identifier: str
    creation_id: int | None = None
    tool: str | None = None
    model: str | None = None
    registered_at: str | None = None
    status: str = "active"


class RegistryResponse(BaseModel):
    """Response from GET /api/queue/registry."""
    count: int = 0
    creations: list[RegistryItem] = Field(default_factory=list)
