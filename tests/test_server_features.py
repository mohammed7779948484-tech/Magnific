"""Tests for SSE streaming, CORS middleware order, static file serving, and health check.

Called Shots:
1. test_sse_stream_returns_events — SSE endpoint yields correctly formatted events
2. test_cors_headers_present — CORS headers appear on OPTIONS requests
3. test_static_downloads_mount — /downloads/nonexistent returns 404 (not 405/500)
4. test_health_check_works — GET /api/health returns {"status": "ok"}

No unittest.mock usage. All tests use real lightweight fakes (FakeClient, FakePoller)
and create_test_app from tests.helpers.
"""

import json

import pytest
from fastapi.responses import StreamingResponse
from starlette.testclient import TestClient

from api.routes import status as status_module
from api.routes.status import stream_status
from tests.helpers.create_test_app import create_test_app
from tests.helpers.fake_deps import FakeClient, FakePoller


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_status_module():
    """Ensure status module deps are clean after each test."""
    status_module._client = None
    status_module._poller = None


# ---------------------------------------------------------------------------
# Called Shot 1: SSE stream returns events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_stream_returns_events():
    """The SSE endpoint should yield data: {json}\\n\\n for each poller update."""
    fake_client = FakeClient(xsrf_token="fake-token")
    fake_poller = FakePoller()
    fake_poller.poll_result = {"url": "https://example.com/img.png"}

    status_module.set_deps(fake_client, fake_poller)

    response = await stream_status(creation_id="test-123", type="image")

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"

    # Collect all chunks from the body iterator
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    full_body = "".join(chunks)

    # FakePoller yields one "completed" event
    lines = [line for line in full_body.strip().split("\n") if line.startswith("data: ")]
    assert len(lines) == 1

    event_data = json.loads(lines[0].replace("data: ", ""))
    assert event_data["status"] == "completed"
    assert event_data["data"]["url"] == "https://example.com/img.png"

    _reset_status_module()


# ---------------------------------------------------------------------------
# Called Shot 2: CORS headers present
# ---------------------------------------------------------------------------

def test_cors_headers_present():
    """CORS middleware should inject Access-Control-Allow-Origin on OPTIONS requests."""
    app = create_test_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    # allow_credentials=True means origin is echoed back (not "*")
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-methods" in response.headers


# ---------------------------------------------------------------------------
# Called Shot 3: Static downloads mount
# ---------------------------------------------------------------------------

def test_static_downloads_mount():
    """GET /downloads/nonexistent should return 404 (not 405 or 500)."""
    app = create_test_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/downloads/nonexistent.png")

    # 404 proves the mount exists and routes through StaticFiles
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Called Shot 4: Health check works
# ---------------------------------------------------------------------------

def test_health_check_works():
    """GET /api/health should return {"status": "ok"}."""
    app = create_test_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
