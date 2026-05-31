"""Queue control API routes — smart queue clearing with ownership tracking.

Provides 5 endpoints for managing the Magnific account queue:
- POST /api/queue/clear — clear external queued creations
- GET /api/queue/status — queue snapshot with ownership tags
- POST /api/queue/cancel/{identifier} — cancel specific creation
- POST /api/queue/configure — enable/disable auto-clearing
- GET /api/queue/registry — view tracked creations
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.schemas.queue_schemas import QueueConfigureRequest
from core.creation_registry import CreationRegistry
from core.queue_manager import QueueManager
from utils.logger import setup_logger

logger = setup_logger("queue_routes")

router = APIRouter(prefix="/api/queue", tags=["Queue Control"])

_queue_manager: QueueManager | None = None
_registry: CreationRegistry | None = None


def set_deps(queue_manager: QueueManager, registry: CreationRegistry):
    """Inject dependencies (called during server lifespan)."""
    global _queue_manager, _registry
    _queue_manager = queue_manager
    _registry = registry


def _require_deps():
    """Verify both deps are available, raise 503 if not."""
    if _queue_manager is None or _registry is None:
        raise HTTPException(
            status_code=503,
            detail="Queue manager not available — server not fully initialized",
        )


# ---------------------------------------------------------------------------
# POST /api/queue/clear
# ---------------------------------------------------------------------------

@router.post("/clear")
async def clear_external_queue():
    """Manually trigger smart queue clearing.

    Cancels all queued creations that were NOT submitted by our project.
    Our project's creations (tracked in the registry) are preserved.
    """
    _require_deps()

    result = await asyncio.to_thread(_queue_manager.clear_external_queue)

    return {
        "success": True,
        "enabled": result.get("enabled", False),
        "cleared": result.get("cleared", 0),
        "errors": result.get("errors", 0),
        "skipped_ours": result.get("skipped_ours", 0),
        "total_queued": result.get("total_queued", 0),
        "reason": result.get("reason"),
        "details": {
            "cancelled_identifiers": result.get("cancelled_identifiers", []),
            "skipped_identifiers": result.get("skipped_identifiers", []),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/queue/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def queue_status():
    """Queue snapshot with ownership classification for each item.

    Returns counts of ours vs external, and a list of items with is_ours flag.
    """
    _require_deps()

    snapshot = await asyncio.to_thread(_queue_manager.get_queue_snapshot)

    return {
        "total_queued": snapshot.get("total_queued", 0),
        "ours": snapshot.get("ours_count", 0),
        "external": snapshot.get("external_count", 0),
        "items": snapshot.get("items", []),
        "processing_count": 0,  # Could be fetched from monitor
        "auto_clear_enabled": snapshot.get("auto_clear_enabled", False),
        "checked_at": snapshot.get("checked_at"),
    }


# ---------------------------------------------------------------------------
# POST /api/queue/cancel/{identifier}
# ---------------------------------------------------------------------------

@router.post("/cancel/{identifier}")
async def cancel_specific(identifier: str):
    """Cancel a specific queued creation by its identifier.

    Args:
        identifier: The creation identifier string to cancel.
    """
    _require_deps()

    result = await asyncio.to_thread(_queue_manager.cancel_creation, identifier)

    return {
        "success": result.get("success", True),
        "identifier": identifier,
        "message": result.get("message", "Cancel request sent"),
    }


# ---------------------------------------------------------------------------
# POST /api/queue/configure
# ---------------------------------------------------------------------------

@router.post("/configure")
async def configure_queue(body: QueueConfigureRequest | None = None):
    """Enable or disable automatic queue clearing before generation.

    Accepts JSON body: {"auto_clear": true/false}
    """
    _require_deps()

    auto_clear = body.auto_clear if body else False

    _queue_manager.configure(auto_clear)

    return {
        "auto_clear": auto_clear,
        "message": (
            "Automatic queue clearing enabled. Non-project queued creations "
            "will be cancelled before each generation."
            if auto_clear
            else "Automatic queue clearing disabled."
        ),
    }


# ---------------------------------------------------------------------------
# GET /api/queue/registry
# ---------------------------------------------------------------------------

@router.get("/registry")
async def view_registry():
    """View all creations tracked by the project registry.

    Returns list of identifiers and metadata for all creations
    that were submitted through our project.
    """
    _require_deps()

    items = _registry.list_all()
    return {
        "count": _registry.count(),
        "creations": items,
    }
