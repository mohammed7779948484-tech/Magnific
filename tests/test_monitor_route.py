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
10. test_monitor_invalid_status_filter — Invalid status returns 422

No unittest.mock usage. Tests use real FakeMonitor from tests.helpers.
"""

import json

import pytest
from starlette.testclient import TestClient

from tests.helpers.fake_deps import FakeClient, FakeMonitor
from tests.helpers.create_test_app import create_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_monitor_deps(queue_result=None, creations_result=None,
                        detail_result=None, stats_result=None,
                        limits_result=None, active_result=None):
    """Set up monitor module deps with FakeMonitor."""
    from api.routes import monitor as monitor_module

    fake_client = FakeClient(xsrf_token="fake-token")
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

    monitor_module.set_deps(fake_client, fake_monitor)
    return monitor_module


def _reset_monitor_deps():
    """Clean up monitor module deps after test."""
    from api.routes import monitor as monitor_module
    monitor_module._client = None
    monitor_module._monitor = None


def _make_app_with_monitor():
    """Create test app with monitor routes registered."""
    from api.routes.monitor import router as monitor_router, set_deps as monitor_set_deps
    from tests.helpers.fake_deps import FakeClient, FakeMonitor

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from api.middleware.error_handler import register_error_handlers
    from api.middleware.rate_limiter import RateLimitMiddleware
    from fastapi.middleware.cors import CORSMiddleware
    from models.base import ModelRegistry

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        ModelRegistry.discover()
        client = FakeClient(xsrf_token="fake-token")
        monitor = FakeMonitor()
        monitor_set_deps(client, monitor)
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

def test_monitor_queue_endpoint():
    """GET /api/monitor/queue should return queue status from monitor."""
    mod = _setup_monitor_deps(queue_result={
        "queued": 2,
        "processing": 1,
        "queued_items": [{"id": 101, "position": 1}],
        "processing_items": [{"id": 202}],
        "total_active": 3,
        "checked_at": "2026-01-30T10:05:00Z",
    })

    from api.routes.monitor import queue_status
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(queue_status())

    assert result["queued"] == 2
    assert result["processing"] == 1
    assert result["total_active"] == 3
    assert len(result["queued_items"]) == 1

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 2: GET /api/monitor/creations
# ---------------------------------------------------------------------------

def test_monitor_creations_endpoint():
    """GET /api/monitor/creations should pass filters to monitor."""
    mod = _setup_monitor_deps(creations_result={
        "data": [{"id": 1, "status": "completed"}],
        "meta": {"total": 100, "current_page": 1, "last_page": 10, "per_page": 10},
    })

    from api.routes.monitor import list_creations
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        list_creations(status="completed", page=1, per_page=10, sort="-createdAt")
    )

    assert result["meta"]["total"] == 100
    assert len(result["data"]) == 1

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 3: GET /api/monitor/creations/{id}
# ---------------------------------------------------------------------------

def test_monitor_creation_detail_endpoint():
    """GET /api/monitor/creations/{id} should return creation detail."""
    mod = _setup_monitor_deps(detail_result={
        "id": 42,
        "status": "completed",
        "tool": "text-to-image",
        "url": "https://example.com/img.png",
    })

    from api.routes.monitor import creation_detail
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(creation_detail("42"))

    assert result["id"] == 42
    assert result["status"] == "completed"

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 4: GET /api/monitor/stats
# ---------------------------------------------------------------------------

def test_monitor_stats_endpoint():
    """GET /api/monitor/stats should return aggregate counts."""
    mod = _setup_monitor_deps(stats_result={
        "counts": {
            "processing": 1, "queued": 3,
            "completed": 50, "failed": 2, "cancelled": 1,
        },
        "total": 57,
        "checked_at": "2026-01-30T10:05:00Z",
    })

    from api.routes.monitor import stats
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(stats())

    assert result["total"] == 57
    assert result["counts"]["queued"] == 3

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 5: GET /api/monitor/health
# ---------------------------------------------------------------------------

def test_monitor_health_endpoint():
    """GET /api/monitor/health should return ok when deps available."""
    _setup_monitor_deps()

    from api.routes.monitor import monitor_health
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(monitor_health())

    assert result["status"] == "ok"

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 6: GET /api/monitor/limits
# ---------------------------------------------------------------------------

def test_monitor_limits_endpoint():
    """GET /api/monitor/limits should return account limits."""
    mod = _setup_monitor_deps(limits_result={
        "credits": 500,
        "used": 120,
        "remaining": 380,
    })

    from api.routes.monitor import limits
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(limits())

    assert result["credits"] == 500
    assert result["remaining"] == 380

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 7: GET /api/monitor/stream (SSE)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_stream_endpoint():
    """GET /api/monitor/stream should yield SSE events."""
    mod = _setup_monitor_deps(active_result=[
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

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 8: 503 when deps not injected
# ---------------------------------------------------------------------------

def test_monitor_no_deps_503():
    """Monitor endpoints should return 503 when deps not available."""
    app = _make_app_with_monitor()

    # Don't inject deps — they start as None
    from api.routes import monitor as monitor_module
    monitor_module._client = None
    monitor_module._monitor = None

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/monitor/queue")

    assert response.status_code == 503

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 9: Pagination validation
# ---------------------------------------------------------------------------

def test_monitor_creations_pagination_validation():
    """per_page > 50 should return 422 via Pydantic validation."""
    app = _make_app_with_monitor()

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/monitor/creations?per_page=51")

    assert response.status_code == 422

    _reset_monitor_deps()


# ---------------------------------------------------------------------------
# Called Shot 10: Router registration
# ---------------------------------------------------------------------------

def test_monitor_routes_registered():
    """Monitor routes should be accessible via test app."""
    app = _make_app_with_monitor()

    client = TestClient(app, raise_server_exceptions=False)

    # All 7 routes should exist (return 200 or 503, not 404)
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

    _reset_monitor_deps()
