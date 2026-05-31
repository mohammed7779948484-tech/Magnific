"""Tests for api/routes/monitor.py — 7 monitoring endpoints.

Called Shots:
1. test_monitor_queue_endpoint — GET /api/monitor/queue returns queue status
2. test_monitor_creations_endpoint — GET /api/monitor/creations with filters
3. test_monitor_creation_detail_endpoint — GET /api/monitor/creations/{id}
4. test_monitor_stats_endpoint — GET /api/monitor/stats returns counts
5. test_monitor_health_endpoint — GET /api/monitor/health returns ok
6. test_monitor_limits_endpoint — GET /api/monitor/limits returns limits
7. test_monitor_stream_endpoint — GET /api/monitor/stream yields SSE events
8. test_monitor_no_deps_503 — Returns 503 when deps not injected
9. test_monitor_creations_pagination_validation — per_page > 50 returns 422
10. test_monitor_routes_registered — All routes accessible via test app

No unittest.mock usage. Tests use real FakeMonitor from tests.helpers.
"""

import json

import pytest
from starlette.testclient import TestClient

from tests.helpers.fake_deps import FakeClient, FakeMonitor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_monitor_deps():
    """Auto-cleanup monitor module globals after every test."""
    yield
    import api.routes.monitor as m
    m._monitor = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_monitor(queue_result=None, creations_result=None,
                   detail_result=None, stats_result=None,
                   limits_result=None, active_result=None):
    """Set up monitor module deps with FakeMonitor."""
    from api.routes import monitor as monitor_module

    fake_monitor = FakeMonitor()

    if queue_result is not None:
        fake_monitor.queue_status_result = queue_result
    if creations_result is not None:
        fake_monitor.list_creations_result = creations_result
    if detail_result is not None:
        fake_monitor.creation_detail_result = detail_result
    if stats_result is not None:
        fake_monitor.stats_result = stats_result
    if limits_result is not None:
        fake_monitor.limits_result = limits_result
    if active_result is not None:
        fake_monitor.active_creations_result = active_result

    monitor_module.set_deps(fake_monitor)
    return monitor_module


def _make_app_with_monitor():
    """Create test app with monitor routes registered."""
    from api.routes.monitor import router as monitor_router, set_deps as monitor_set_deps

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from api.middleware.error_handler import register_error_handlers
    from api.middleware.rate_limiter import RateLimitMiddleware
    from fastapi.middleware.cors import CORSMiddleware
    from models.base import ModelRegistry

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        ModelRegistry.discover()
        monitor = FakeMonitor()
        monitor_set_deps(monitor)
        yield

    app = FastAPI(title="Test", lifespan=test_lifespan)
    register_error_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                      allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RateLimitMiddleware, max_requests=999)
    app.include_router(monitor_router)
    return app


# ---------------------------------------------------------------------------
# Called Shot 1: GET /api/monitor/queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_queue_endpoint():
    """GET /api/monitor/queue should return queue status from monitor."""
    _setup_monitor(queue_result={
        "queued": 2,
        "processing": 1,
        "queued_items": [{"id": 101, "position": 1}],
        "processing_items": [{"id": 202}],
        "total_active": 3,
        "checked_at": "2026-01-30T10:05:00Z",
    })

    from api.routes.monitor import queue_status

    result = await queue_status()

    assert result["queued"] == 2
    assert result["processing"] == 1
    assert result["total_active"] == 3
    assert len(result["queued_items"]) == 1


# ---------------------------------------------------------------------------
# Called Shot 2: GET /api/monitor/creations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_creations_endpoint():
    """GET /api/monitor/creations should pass filters to monitor."""
    _setup_monitor(creations_result={
        "data": [{"id": 1, "status": "completed"}],
        "meta": {"total": 100, "current_page": 1, "last_page": 10, "per_page": 10},
    })

    from api.routes.monitor import list_creations

    result = await list_creations(status="completed", page=1, per_page=10, sort="-createdAt")

    assert result["meta"]["total"] == 100
    assert len(result["data"]) == 1


# ---------------------------------------------------------------------------
# Called Shot 3: GET /api/monitor/creations/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_creation_detail_endpoint():
    """GET /api/monitor/creations/{id} should return creation detail."""
    _setup_monitor(detail_result={
        "id": 42,
        "status": "completed",
        "tool": "text-to-image",
        "url": "https://example.com/img.png",
    })

    from api.routes.monitor import creation_detail

    result = await creation_detail("42")

    assert result["id"] == 42
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Called Shot 4: GET /api/monitor/stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_stats_endpoint():
    """GET /api/monitor/stats should return aggregate counts."""
    _setup_monitor(stats_result={
        "counts": {
            "processing": 1, "queued": 3,
            "completed": 50, "failed": 2, "cancelled": 1,
        },
        "total": 57,
        "checked_at": "2026-01-30T10:05:00Z",
    })

    from api.routes.monitor import stats

    result = await stats()

    assert result["total"] == 57
    assert result["counts"]["queued"] == 3


# ---------------------------------------------------------------------------
# Called Shot 5: GET /api/monitor/health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_health_endpoint():
    """GET /api/monitor/health should return ok when deps available."""
    _setup_monitor()

    from api.routes.monitor import monitor_health

    result = await monitor_health()

    assert result.status == "ok"


# ---------------------------------------------------------------------------
# Called Shot 6: GET /api/monitor/limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_limits_endpoint():
    """GET /api/monitor/limits should return account limits."""
    _setup_monitor(limits_result={
        "credits": 500,
        "used": 120,
        "remaining": 380,
    })

    from api.routes.monitor import limits

    result = await limits()

    assert result["credits"] == 500
    assert result["remaining"] == 380


# ---------------------------------------------------------------------------
# Called Shot 7: GET /api/monitor/stream (SSE)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_stream_endpoint():
    """GET /api/monitor/stream should yield SSE events."""
    _setup_monitor(active_result=[
        {"id": 101, "status": "queued"},
        {"id": 202, "status": "processing"},
    ])

    from api.routes.monitor import stream_monitor
    from fastapi.responses import StreamingResponse

    response = await stream_monitor()

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"

    # Collect chunks
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
        break  # Just get the first chunk (it's a single poll cycle)

    body = "".join(chunks)
    assert "data: " in body


# ---------------------------------------------------------------------------
# Called Shot 8: 503 when deps not injected
# ---------------------------------------------------------------------------

def test_monitor_no_deps_503():
    """Monitor endpoints should return 503 when deps not available."""
    app = _make_app_with_monitor()

    # Don't inject deps — they start as None
    from api.routes import monitor as monitor_module
    monitor_module._monitor = None

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/monitor/queue")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Called Shot 9: Pagination validation
# ---------------------------------------------------------------------------

def test_monitor_creations_pagination_validation():
    """per_page > 50 should return 422 via Pydantic validation."""
    app = _make_app_with_monitor()

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/monitor/creations?per_page=51")

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Called Shot 10: Router registration
# ---------------------------------------------------------------------------

def test_monitor_routes_registered():
    """Monitor routes should be accessible via test app."""
    app = _make_app_with_monitor()

    client = TestClient(app, raise_server_exceptions=False)

    # All routes should exist (return 200 or 503, not 404)
    routes = [
        "/api/monitor/health",
        "/api/monitor/queue",
        "/api/monitor/creations",
        "/api/monitor/stats",
        "/api/monitor/limits",
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code != 404, f"Route {route} returned 404"
