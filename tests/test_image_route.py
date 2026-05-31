"""Tests for api/routes/image.py — async unblocking + retry.

Called Shots:
1. test_generate_image_returns_success_on_valid_input
2. test_generate_image_returns_error_on_no_request_token
3. test_generate_image_returns_processing_when_wait_false
4. test_generate_image_downloads_base64_when_download_true

NO unittest.mock — uses real lightweight fakes from tests.helpers.fake_deps.
"""

import pytest

from api.routes.image import generate_image, set_deps
from api.schemas.image_schemas import ImageRequest
from models.base import ModelRegistry
from tests.helpers.fake_deps import (
    FakeClient,
    FakePoller,
    FakeResponse,
    FakeSession,
    FakeUploader,
)

# Import cached module to get model instance for re-registration
import models.image.nano_banana_2 as _nano_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_module_deps():
    """Set lightweight fake deps before each test, tear down after."""
    # Re-register image model if cleared by another test module
    slug = "imagen-nano-banana-2"
    if slug not in ModelRegistry._image_models:
        ModelRegistry._image_models[slug] = _nano_mod.nano_banana_2

    client = FakeClient(xsrf_token="fake-token")
    poller = FakePoller()
    uploader = FakeUploader()
    set_deps(client, poller, uploader)
    yield
    import api.routes.image as img_mod
    img_mod._client = None
    img_mod._poller = None
    img_mod._uploader = None


def _make_request(**overrides) -> ImageRequest:
    defaults = dict(
        prompt="test prompt",
        model="imagen-nano-banana-2",
        wait=True,
        download=False,
    )
    defaults.update(overrides)
    return ImageRequest(**defaults)


def _setup_success_responses(client: FakeClient, poller: FakePoller):
    """Configure fake client + poller for a successful full pipeline."""
    client.post_responses = [
        {"request_tokens": ["tok123"], "family": "test"},
        {"creation": {"id": "42"}},
    ]
    poller.poll_result = {"download_url": "https://example.com/img.png"}


# ---------------------------------------------------------------------------
# Called Shot 1: success on valid input
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_returns_success_on_valid_input():
    """When client.post and poller return valid data, ImageResponse has success=True."""
    import api.routes.image as img_mod

    _setup_success_responses(img_mod._client, img_mod._poller)

    request = _make_request(wait=True, download=False)
    response = await generate_image(request)

    assert response.success is True
    assert response.creation_id == "42"
    assert response.status == "completed"
    assert response.image_url == "https://example.com/img.png"
    assert response.elapsed is not None and response.elapsed >= 0


# ---------------------------------------------------------------------------
# Called Shot 2: error when no request token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_returns_error_on_no_request_token():
    """When start-tti-v2 returns no request token, returns success=False."""
    import api.routes.image as img_mod

    img_mod._client.post_responses = [
        {"request_tokens": [None], "family": "test"},
    ]

    request = _make_request(wait=True)
    response = await generate_image(request)

    assert response.success is False
    assert response.status == "error"
    assert "Failed to get request token" in (response.message or "")


# ---------------------------------------------------------------------------
# Called Shot 3: processing when wait=False
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_returns_processing_when_wait_false():
    """When wait=False, returns immediately with status='processing'."""
    import api.routes.image as img_mod

    img_mod._client.post_responses = [
        {"request_tokens": ["tok456"], "family": "test"},
        {"creation": {"id": "99"}},
    ]

    request = _make_request(wait=False)
    response = await generate_image(request)

    assert response.status == "processing"
    assert response.creation_id == "99"
    assert response.success is True
    assert response.family == "test"


# ---------------------------------------------------------------------------
# Called Shot 4: base64 download when download=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_downloads_base64_when_download_true():
    """When download=True and completed, image_base64 is populated."""
    import api.routes.image as img_mod

    _setup_success_responses(img_mod._client, img_mod._poller)
    # Configure session for download
    img_mod._client.session = FakeSession(
        get_response=FakeResponse(status_code=200, content=b"fakeimg")
    )

    request = _make_request(wait=True, download=True)
    response = await generate_image(request)

    assert response.image_base64 is not None
    assert response.image_base64.startswith("data:image/png;base64,")
    assert response.success is True
    assert response.creation_id == "42"
    # Verify the base64 content matches b"fakeimg"
    import base64
    payload = response.image_base64.split(",", 1)[1]
    assert base64.b64decode(payload) == b"fakeimg"
