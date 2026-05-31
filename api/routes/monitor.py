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
    PaginationParams,
)
from core.client import MagnificClient
from core.monitor import MagnificMonitor
from utils.logger import setup_logger

logger = setup_logger("monitor_routes")

router = APIRouter(prefix="/api/monitor", tags=["Monitoring"])

_client: MagnificClient | None = None
_monitor: MagnificMonitor | None = None


def set_deps(client: MagnificClient, monitor: MagnificMonitor):
    """Inject dependencies (called during server lifespan)."""
    global _client, _monitor
    _client = client
    _monitor = monitor


def _require_deps():
    """Verify dependencies are available, raise 503 if not."""
    if _monitor is None or _client is None:
        raise HTTPException(
            status_code=503,
            detail="Monitor not available — server not fully initialized",
        )


# ---------------------------------------------------------------------------
# GET /api/monitor/health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=MonitorHealthResponse)
async def monitor_health() -> dict:
    """Health check for the monitor subsystem."""
    if _monitor is None or _client is None:
        return MonitorHealthResponse(
            status="error",
            detail="Monitor not available — server not fully initialized",
        ).model_dump()

    return MonitorHealthResponse(
        status="ok",
    ).model_dump()


# ---------------------------------------------------------------------------
# GET /api/monitor/queue
# ---------------------------------------------------------------------------

@router.get("/queue")
async def queue_status() -> dict:
    """Current queue snapshot: queued + processing items.

    Returns counts, items with positions and expected times.
    """
    _require_deps()
    return await asyncio.to_thread(_monitor.get_queue_status)


# ---------------------------------------------------------------------------
# GET /api/monitor/creations
# ---------------------------------------------------------------------------

@router.get("/creations")
async def list_creations(
    status: str | None = Query(None, description="Filter: processing, queued, completed, failed, cancelled"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page (max 50)"),
    sort: str = Query("-createdAt", description="Sort field"),
) -> dict:
    """Paginated list of creations with optional status filter."""
    _require_deps()
    params = PaginationParams(page=page, per_page=per_page, sort=sort, status=status)
    return await asyncio.to_thread(
        _monitor.list_creations,
        status=params.status,
        page=params.page,
        per_page=params.per_page,
        sort=params.sort,
    )


# ---------------------------------------------------------------------------
# GET /api/monitor/creations/{creation_id}
# ---------------------------------------------------------------------------

@router.get("/creations/{creation_id}")
async def creation_detail(creation_id: str) -> dict:
    """Detailed view of a single creation."""
    _require_deps()
    return await asyncio.to_thread(_monitor.get_creation, creation_id)


# ---------------------------------------------------------------------------
# GET /api/monitor/stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def stats() -> dict:
    """Aggregate statistics across all creation statuses.

    Returns counts per status, total, and timestamp.
    """
    _require_deps()
    return await asyncio.to_thread(_monitor.get_stats)


# ---------------------------------------------------------------------------
# GET /api/monitor/limits
# ---------------------------------------------------------------------------

@router.get("/limits")
async def limits() -> dict:
    """Account limits and credit information."""
    _require_deps()
    try:
        return await asyncio.to_thread(_monitor.get_limits)
    except Exception as e:
        logger.warning(f"Failed to fetch limits: {e}")
        return {"status": "unavailable", "detail": str(e)}


# ---------------------------------------------------------------------------
# GET /api/monitor/stream (SSE)
# ---------------------------------------------------------------------------

@router.get("/stream")
async def stream_monitor() -> StreamingResponse:
    """SSE stream monitoring all active (processing + queued) creations.

    Emits status change events and heartbeats every 15 seconds.
    """
    _require_deps()

    heartbeat_interval = 15
    poll_interval = 5

    async def event_generator():
        """Generate SSE events by polling active creations."""
        try:
            while True:
                try:
                    active = await asyncio.to_thread(_monitor.get_active_creations)

                    if active:
                        for creation in active:
                            yield f"event: status_update\ndata: {json.dumps(creation)}\n\n"
                    else:
                        yield f"event: heartbeat\ndata: {json.dumps({'active_count': 0, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

                except Exception as e:
                    logger.warning(f"Monitor stream poll error: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

                await asyncio.sleep(poll_interval)

                # Heartbeat every 3rd poll cycle (~15 seconds)
                yield f"event: heartbeat\ndata: {json.dumps({'active_count': len(active) if active else 0, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                await asyncio.sleep(heartbeat_interval - poll_interval)

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
