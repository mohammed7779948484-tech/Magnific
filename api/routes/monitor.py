"""Monitor API routes — real-time monitoring of Magnific creations.

Provides 7 endpoints for monitoring queue status, creation history,
statistics, account limits, and SSE streaming of active creations.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.schemas.monitor_schemas import (
    MonitorHealthResponse,
    MonitorStats,
    QueueOverview,
)
from core.monitor import MagnificMonitor
from utils.logger import setup_logger

logger = setup_logger("monitor_routes")

router = APIRouter(prefix="/api/monitor", tags=["Monitoring"])

_monitor: MagnificMonitor | None = None


def set_deps(monitor: MagnificMonitor):
    """Inject dependencies (called during server lifespan)."""
    global _monitor
    _monitor = monitor


def _require_monitor():
    """Verify monitor is available, raise 503 if not."""
    if _monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Monitor not available — server not fully initialized",
        )


# ---------------------------------------------------------------------------
# GET /api/monitor/health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=MonitorHealthResponse)
async def monitor_health():
    """Health check for the monitor subsystem."""
    if _monitor is None:
        return MonitorHealthResponse(
            status="error",
            detail="Monitor not available — server not fully initialized",
        )

    return MonitorHealthResponse(status="ok")


# ---------------------------------------------------------------------------
# GET /api/monitor/queue
# ---------------------------------------------------------------------------

@router.get("/queue", response_model=QueueOverview)
async def queue_status():
    """Current queue snapshot: queued + processing items.

    Returns counts, items with positions and expected times.
    """
    _require_monitor()
    return await asyncio.to_thread(_monitor.get_queue_status)


# ---------------------------------------------------------------------------
# GET /api/monitor/creations
# ---------------------------------------------------------------------------

@router.get("/creations")
async def list_creations(
    status: str | None = Query(
        None,
        description="Filter: processing, queued, completed, failed, cancelled",
        pattern=r"^(processing|queued|completed|failed|cancelled)$",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page (max 50)"),
    sort: str = Query("-createdAt", description="Sort field", pattern=r"^-?[a-zA-Z_]+$"),
) -> dict:
    """Paginated list of creations with optional status filter."""
    _require_monitor()
    return await asyncio.to_thread(
        _monitor.list_creations,
        status=status,
        page=page,
        per_page=per_page,
        sort=sort,
    )


# ---------------------------------------------------------------------------
# GET /api/monitor/creations/{creation_id}
# ---------------------------------------------------------------------------

@router.get("/creations/{creation_id}")
async def creation_detail(creation_id: str) -> dict:
    """Detailed view of a single creation."""
    _require_monitor()
    return await asyncio.to_thread(_monitor.get_creation, creation_id)


# ---------------------------------------------------------------------------
# GET /api/monitor/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=MonitorStats)
async def stats():
    """Aggregate statistics across all creation statuses.

    Returns counts per status, total, and timestamp.
    """
    _require_monitor()
    return await asyncio.to_thread(_monitor.get_stats)


# ---------------------------------------------------------------------------
# GET /api/monitor/limits
# ---------------------------------------------------------------------------

@router.get("/limits")
async def limits():
    """Account limits and credit information."""
    _require_monitor()
    return await asyncio.to_thread(_monitor.get_limits)


# ---------------------------------------------------------------------------
# GET /api/monitor/stream (SSE)
# ---------------------------------------------------------------------------

@router.get("/stream")
async def stream_monitor() -> StreamingResponse:
    """SSE stream monitoring all active (processing + queued) creations.

    Emits status updates and heartbeats. Auto-terminates after 5 minutes
    to prevent resource leaks from forgotten connections.
    """
    _require_monitor()

    max_lifetime = 300  # 5 minutes max
    poll_interval = 5
    heartbeat_interval = 15

    async def event_generator():
        """Generate SSE events by polling active creations."""
        active: list[dict] = []
        elapsed = 0.0
        last_heartbeat = 0.0

        try:
            while elapsed < max_lifetime:
                loop_start = asyncio.get_event_loop().time()

                try:
                    active = await asyncio.to_thread(_monitor.get_active_creations)

                    if active:
                        for creation in active:
                            yield f"event: status_update\ndata: {json.dumps(creation)}\n\n"

                except Exception as e:
                    logger.warning(f"Monitor stream poll error: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': 'Failed to fetch active creations'})}\n\n"

                await asyncio.sleep(poll_interval)
                elapsed += asyncio.get_event_loop().time() - loop_start

                # Heartbeat every heartbeat_interval seconds
                if elapsed - last_heartbeat >= heartbeat_interval:
                    yield f"event: heartbeat\ndata: {json.dumps({'active_count': len(active), 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                    last_heartbeat = elapsed

            # Final heartbeat before closing
            yield f"event: heartbeat\ndata: {json.dumps({'active_count': len(active), 'timestamp': datetime.now(timezone.utc).isoformat(), 'closing': True})}\n\n"

        except asyncio.CancelledError:
            logger.info("Monitor SSE stream closed by client")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
