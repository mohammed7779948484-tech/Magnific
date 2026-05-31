"""Tests for api/routes/video.py — no unittest.mock, real lightweight fakes."""

import pytest

from api.routes import video as video_module
from api.schemas.video_schemas import VideoRequest, VideoResponse
from models.base import ModelRegistry
from tests.helpers.fake_deps import FakeClient, FakePoller, FakeResponse, FakeSession, FakeUploader

# Import cached module to get model instance for re-registration
import models.video.seedance_2_pro as _seedance_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_video_module_deps():
    """Reset module-level globals so tests don't leak state."""
    video_module._client = None
    video_module._poller = None
    video_module._uploader = None
    yield
    video_module._client = None
    video_module._poller = None
    video_module._uploader = None


@pytest.fixture(autouse=True)
def _ensure_video_model_registered():
    """Ensure 'bytedance-seedance-pro-2.0' is in the registry.

    Python caches module imports, so re-importing won't re-trigger __post_init__.
    We explicitly register from the cached module instance.
    """
    slug = "bytedance-seedance-pro-2.0"
    if slug not in ModelRegistry._video_models:
        ModelRegistry._video_models[slug] = _seedance_mod.seedance_2_pro
    yield


def _make_deps(
    post_response=None,
    poll_result=None,
    session_get_response=None,
):
    """Build FakeClient + FakePoller + FakeUploader with canned responses."""
    client = FakeClient()
    if post_response is not None:
        client.post_responses = [post_response]

    poller = FakePoller()
    if poll_result is not None:
        poller.poll_result = poll_result

    if session_get_response is not None:
        client._session = FakeSession(get_response=session_get_response)

    uploader = FakeUploader()

    video_module.set_deps(client, poller, uploader)

    return client, poller, uploader


# ---------------------------------------------------------------------------
# Test 1: generate_video returns success (happy path)
# ---------------------------------------------------------------------------

class TestGenerateVideoReturnsSuccess:
    """Happy path — POST returns creation, poll returns download URL."""

    @pytest.mark.asyncio
    async def test_generate_video_returns_success(self):
        client, poller, _uploader = _make_deps(
            post_response={"data": {"creations": [{"id": "99"}]}},
            poll_result={"download_url": "https://example.com/vid.mp4"},
        )

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=True,
        )

        response = await video_module.generate_video(request)

        assert response.success is True
        assert response.creation_id == "99"
        assert response.status == "completed"
        assert response.video_url == "https://example.com/vid.mp4"

        # Observable side-effects: client.post was called once
        assert len(client.post_calls) == 1
        assert client.post_calls[0]["path"] == "/api/video/generate?return_creations=true"

        # Poller was invoked with the correct creation_id
        assert len(poller.poll_calls) == 1
        assert poller.poll_calls[0]["creation_id"] == "99"
        assert poller.poll_calls[0]["creation_type"] == "video"


# ---------------------------------------------------------------------------
# Test 2: no creation returned → error
# ---------------------------------------------------------------------------

class TestGenerateVideoNoCreationReturned:
    """POST returns empty creations list → error response."""

    @pytest.mark.asyncio
    async def test_generate_video_no_creation_returned(self):
        client, poller, _uploader = _make_deps(
            post_response={"data": {"creations": []}},
        )

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=True,
        )

        response = await video_module.generate_video(request)

        assert response.success is False
        assert response.status == "error"
        assert "No creation returned" in (response.message or "")

        # Client was called, poller was NOT called
        assert len(client.post_calls) == 1
        assert len(poller.poll_calls) == 0


# ---------------------------------------------------------------------------
# Test 3: wait=False → processing
# ---------------------------------------------------------------------------

class TestGenerateVideoWaitFalse:
    """wait=False returns immediately with status 'processing'."""

    @pytest.mark.asyncio
    async def test_generate_video_wait_false(self):
        client, poller, _uploader = _make_deps(
            post_response={"data": {"creations": [{"id": "42"}]}},
        )

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=False,
        )

        response = await video_module.generate_video(request)

        assert response.status == "processing"
        assert response.creation_id == "42"

        # Poller should NOT have been called — we returned early
        assert len(poller.poll_calls) == 0

        # Client WAS called
        assert len(client.post_calls) == 1


# ---------------------------------------------------------------------------
# Test 4: download=True → video_base64 populated
# ---------------------------------------------------------------------------

class TestGenerateVideoDownloadsBase64:
    """With download=True, video_base64 is populated."""

    @pytest.mark.asyncio
    async def test_generate_video_downloads_base64(self):
        video_bytes = b"\x00\x01\x02VIDEO"
        client, poller, _uploader = _make_deps(
            post_response={"data": {"creations": [{"id": "55"}]}},
            poll_result={"download_url": "https://example.com/vid.mp4"},
            session_get_response=FakeResponse(status_code=200, content=video_bytes),
        )

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=True,
            download=True,
        )

        response = await video_module.generate_video(request)

        assert response.success is True
        assert response.creation_id == "55"
        assert response.status == "completed"
        assert response.video_base64 is not None
        assert len(response.video_base64) > 0

        # Verify the base64 content decodes back to our original bytes
        import base64
        decoded = base64.b64decode(response.video_base64)
        assert decoded == video_bytes

        # Session.get was called with the download URL
        session = client.session
        assert len(session.get_calls) == 1
        assert session.get_calls[0]["url"] == "https://example.com/vid.mp4"
