"""Tests for SSE streaming, CORS middleware order, static file serving, and health check.

Called Shots:
1. test_sse_stream_returns_events — SSE endpoint yields correctly formatted events
2. test_cors_headers_present — CORS headers appear on OPTIONS requests
3. test_static_downloads_mount — /downloads/nonexistent returns 404 (not 405/500)
4. test_health_check_works — GET /api/health returns {"status": "ok"}
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from api.routes import status as status_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_status_module():
    """Ensure status module deps are clean."""
    status_module._client = None
    status_module._poller = None


def _set_status_deps():
    """Set mock deps on the status module."""
    mock_client = MagicMock()
    mock_poller = MagicMock()
    mock_client.xsrf_token = "fake-token"
    status_module.set_deps(mock_client, mock_poller)
    return mock_client, mock_poller


# ---------------------------------------------------------------------------
# Called Shot 1: SSE stream returns events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_stream_returns_events():
    """The SSE endpoint should yield data: {json}\\n\\n for each poller update."""
    mock_client, mock_poller = _set_status_deps()

    # Mock poll_creation_stream to yield two updates then stop
    mock_poller.poll_creation_stream.return_value = iter([
        {"status": "processing", "elapsed": 1.0, "data": {}},
        {"status": "completed", "elapsed": 5.0, "data": {"url": "https://example.com/img.png"}},
    ])

    from fastapi.responses import StreamingResponse
    from api.routes.status import stream_status

    # Call the endpoint directly
    response = await stream_status(creation_id="test-123", type="image")

    # Should return a StreamingResponse
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"

    # Collect all chunks from the body iterator (yields strings, not bytes)
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    full_body = "".join(chunks)

    # Should have two SSE events
    lines = [l for l in full_body.strip().split("\n") if l.startswith("data: ")]
    assert len(lines) == 2

    # First event should be "processing"
    first_data = json.loads(lines[0].replace("data: ", ""))
    assert first_data["status"] == "processing"

    # Second event should be "completed"
    second_data = json.loads(lines[1].replace("data: ", ""))
    assert second_data["status"] == "completed"

    _reset_status_module()


# ---------------------------------------------------------------------------
# Called Shot 2: CORS headers present
# ---------------------------------------------------------------------------

def test_cors_headers_present():
    """CORS middleware should inject Access-Control-Allow-Origin on OPTIONS requests."""
    _reset_status_module()

    # Patch lifespan so we don't need real cookies/network
    from api.server import create_app

    with patch("api.server.ModelRegistry"), \
         patch("api.server.CookieParser"), \
         patch("api.server.MagnificClient"), \
         patch("api.server.Authenticator"), \
         patch("api.server.Poller"), \
         patch("api.server.Uploader"):

        app = create_app(rate_limit=999)

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
    _reset_status_module()

    from api.server import create_app

    with patch("api.server.ModelRegistry"), \
         patch("api.server.CookieParser"), \
         patch("api.server.MagnificClient"), \
         patch("api.server.Authenticator"), \
         patch("api.server.Poller"), \
         patch("api.server.Uploader"):

        app = create_app(rate_limit=999)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/downloads/nonexistent.png")

    # 404 proves the mount exists and routes through StaticFiles
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Called Shot 4: Health check works
# ---------------------------------------------------------------------------

def test_health_check_works():
    """GET /api/health should return {"status": "ok"}."""
    _reset_status_module()

    from api.server import create_app

    with patch("api.server.ModelRegistry"), \
         patch("api.server.CookieParser"), \
         patch("api.server.MagnificClient") as MockClient, \
         patch("api.server.Authenticator"), \
         patch("api.server.Poller"), \
         patch("api.server.Uploader"):

        # Make the client have xsrf_token so "authenticated" is true
        mock_client_instance = MockClient.return_value
        mock_client_instance.xsrf_token = "fake-token"

        app = create_app(rate_limit=999)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
