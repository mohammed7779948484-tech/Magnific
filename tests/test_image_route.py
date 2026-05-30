"""Tests for api/routes/image.py — async unblocking + retry.

Called Shots:
1. test_generate_image_returns_success_on_valid_input
2. test_generate_image_returns_error_on_no_request_token
3. test_generate_image_returns_processing_when_wait_false
4. test_generate_image_downloads_base64_when_download_true
"""

import asyncio
import base64
from unittest.mock import MagicMock, patch

import pytest

from api.routes.image import generate_image, set_deps
from api.schemas.image_schemas import ImageRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_module_deps():
    """Ensure deps are set and torn down per test."""
    mock_client = MagicMock()
    mock_poller = MagicMock()
    mock_uploader = MagicMock()
    set_deps(mock_client, mock_poller, mock_uploader)
    yield
    # Reset globals so no state leaks
    import api.routes.image as img_mod
    img_mod._client = None
    img_mod._poller = None
    img_mod._uploader = None


@pytest.fixture(autouse=True)
def _mock_registry():
    """Patch ModelRegistry.get_image so no real models are needed."""
    fake_model = MagicMock()
    fake_model.build_start_tti_body.return_value = {"mode": "test", "prompt": "test"}
    fake_model.build_render_body.return_value = {"tool": "text-to-image", "mode": "test"}
    with patch("api.routes.image.ModelRegistry") as MockReg:
        MockReg.get_image.return_value = fake_model
        yield


def _make_request(**overrides) -> ImageRequest:
    defaults = dict(
        prompt="test prompt",
        model="imagen-nano-banana-2",
        wait=True,
        download=False,
    )
    defaults.update(overrides)
    return ImageRequest(**defaults)


def _mock_response(status_code=200, content=b"fakeimg"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# Called Shot 1: success on valid input
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_returns_success_on_valid_input():
    """When client.post and poller return valid data, ImageResponse has success=True."""
    from api.routes import image as img_mod

    # First call: start-tti-v2
    # Second call: render/v4
    img_mod._client.post.side_effect = [
        {"request_tokens": ["tok123"], "family": "test"},
        {"creation": {"id": "42"}},
    ]
    img_mod._poller.poll_creation.return_value = {
        "download_url": "https://example.com/img.png"
    }

    request = _make_request(wait=True, download=False)
    response = await generate_image(request)

    assert response.success is True
    assert response.creation_id == "42"
    assert response.status == "completed"


# ---------------------------------------------------------------------------
# Called Shot 2: error when no request token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_returns_error_on_no_request_token():
    """When start-tti-v2 returns no request token, returns success=False."""
    from api.routes import image as img_mod

    img_mod._client.post.return_value = {
        "request_tokens": [None],
        "family": "test",
    }

    request = _make_request(wait=True)
    response = await generate_image(request)

    assert response.success is False
    assert response.status == "error"


# ---------------------------------------------------------------------------
# Called Shot 3: processing when wait=False
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_returns_processing_when_wait_false():
    """When wait=False, returns immediately with status='processing'."""
    from api.routes import image as img_mod

    img_mod._client.post.side_effect = [
        {"request_tokens": ["tok456"], "family": "test"},
        {"creation": {"id": "99"}},
    ]

    request = _make_request(wait=False)
    response = await generate_image(request)

    assert response.status == "processing"
    assert response.creation_id is not None


# ---------------------------------------------------------------------------
# Called Shot 4: base64 download when download=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_downloads_base64_when_download_true():
    """When download=True and completed, image_base64 is populated."""
    from api.routes import image as img_mod

    img_mod._client.post.side_effect = [
        {"request_tokens": ["tok789"], "family": "test"},
        {"creation": {"id": "55"}},
    ]
    img_mod._poller.poll_creation.return_value = {
        "download_url": "https://example.com/img.png"
    }
    img_mod._client.session.get.return_value = _mock_response(status_code=200, content=b"fakeimg")

    request = _make_request(wait=True, download=True)
    response = await generate_image(request)

    assert response.image_base64 is not None
    assert response.image_base64.startswith("data:")
