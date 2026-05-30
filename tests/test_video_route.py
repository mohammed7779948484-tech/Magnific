"""Tests for api/routes/video.py — async blocking fix + retry with backoff."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from api.routes import video as video_module
from api.schemas.video_schemas import VideoRequest, VideoResponse
from core.client import MagnificClient
from core.poller import Poller
from core.uploader import Uploader
from models.base import ModelRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_video_model():
    """Create a fake video model that satisfies build_video_body."""
    model = MagicMock()
    model.build_video_body.return_value = {"prompt": "test", "some": "body"}
    return model


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
def _register_test_video_model():
    """Ensure the model 'bytedance-seedance-pro-2.0' is registered."""
    from models.base import BaseVideoModel
    slug = "bytedance-seedance-pro-2.0"
    # Only register if not already present (discover may have done it)
    if slug not in ModelRegistry._video_models:
        fake = MagicMock(spec=BaseVideoModel)
        fake.slug = slug
        fake.build_video_body.return_value = {"prompt": "test"}
        ModelRegistry._video_models[slug] = fake
    yield


# ---------------------------------------------------------------------------
# Called Shot 1: generate_video returns success
# ---------------------------------------------------------------------------

class TestGenerateVideoReturnsSuccess:
    """Called Shot 1: Happy path — POST returns creation, poll returns download URL."""

    @pytest.mark.asyncio
    async def test_generate_video_returns_success(self):
        # Arrange
        mock_client = MagicMock(spec=MagnificClient)
        mock_poller = MagicMock(spec=Poller)
        mock_uploader = MagicMock(spec=Uploader)

        mock_client.post.return_value = {
            "data": {"creations": [{"id": "99"}]}
        }
        mock_poller.poll_creation.return_value = {
            "download_url": "https://example.com/vid.mp4"
        }

        video_module.set_deps(mock_client, mock_poller, mock_uploader)

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=True,
        )

        # Patch asyncio.to_thread to just call the function directly (sync)
        with patch.object(asyncio, "to_thread", new_callable=AsyncMock) as mock_to_thread:
            # Make to_thread actually call the function with its args
            async def _sync_runner(fn, *args, **kwargs):
                return fn(*args, **kwargs)
            mock_to_thread.side_effect = _sync_runner

            # Act
            response = await video_module.generate_video(request)

        # Assert
        assert response.success is True
        assert response.creation_id == "99"
        assert response.status == "completed"
        assert response.video_url == "https://example.com/vid.mp4"
        mock_client.post.assert_called_once()


# ---------------------------------------------------------------------------
# Called Shot 2: no creation returned
# ---------------------------------------------------------------------------

class TestGenerateVideoNoCreationReturned:
    """Called Shot 2: POST returns empty creations list → error response."""

    @pytest.mark.asyncio
    async def test_generate_video_no_creation_returned(self):
        mock_client = MagicMock(spec=MagnificClient)
        mock_poller = MagicMock(spec=Poller)
        mock_uploader = MagicMock(spec=Uploader)

        mock_client.post.return_value = {"data": {"creations": []}}

        video_module.set_deps(mock_client, mock_poller, mock_uploader)

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=True,
        )

        with patch.object(asyncio, "to_thread", new_callable=AsyncMock) as mock_to_thread:
            async def _sync_runner(fn, *args, **kwargs):
                return fn(*args, **kwargs)
            mock_to_thread.side_effect = _sync_runner

            response = await video_module.generate_video(request)

        assert response.success is False
        assert response.status == "error"


# ---------------------------------------------------------------------------
# Called Shot 3: wait=False → processing
# ---------------------------------------------------------------------------

class TestGenerateVideoWaitFalse:
    """Called Shot 3: wait=False returns immediately with status 'processing'."""

    @pytest.mark.asyncio
    async def test_generate_video_wait_false(self):
        mock_client = MagicMock(spec=MagnificClient)
        mock_poller = MagicMock(spec=Poller)
        mock_uploader = MagicMock(spec=Uploader)

        mock_client.post.return_value = {
            "data": {"creations": [{"id": "42"}]}
        }

        video_module.set_deps(mock_client, mock_poller, mock_uploader)

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=False,
        )

        with patch.object(asyncio, "to_thread", new_callable=AsyncMock) as mock_to_thread:
            async def _sync_runner(fn, *args, **kwargs):
                return fn(*args, **kwargs)
            mock_to_thread.side_effect = _sync_runner

            response = await video_module.generate_video(request)

        assert response.status == "processing"
        assert response.creation_id == "42"
        # Poller should NOT have been called
        mock_poller.poll_creation.assert_not_called()


# ---------------------------------------------------------------------------
# Called Shot 4: download and return base64
# ---------------------------------------------------------------------------

class TestGenerateVideoDownloadsBase64:
    """Called Shot 4: With download=True, video_base64 is populated."""

    @pytest.mark.asyncio
    async def test_generate_video_downloads_base64(self):
        mock_client = MagicMock(spec=MagnificClient)
        mock_poller = MagicMock(spec=Poller)
        mock_uploader = MagicMock(spec=Uploader)

        mock_client.post.return_value = {
            "data": {"creations": [{"id": "55"}]}
        }
        mock_poller.poll_creation.return_value = {
            "download_url": "https://example.com/vid.mp4"
        }

        # Simulate HTTP download response (mock session separately since spec doesn't include it)
        fake_response = SimpleNamespace(status_code=200, content=b"\x00\x01\x02VIDEO")
        mock_session = MagicMock()
        mock_session.get.return_value = fake_response
        mock_client.session = mock_session

        video_module.set_deps(mock_client, mock_poller, mock_uploader)

        request = VideoRequest(
            prompt="test",
            model="bytedance-seedance-pro-2.0",
            wait=True,
            download=True,
        )

        with patch.object(asyncio, "to_thread", new_callable=AsyncMock) as mock_to_thread:
            async def _sync_runner(fn, *args, **kwargs):
                return fn(*args, **kwargs)
            mock_to_thread.side_effect = _sync_runner

            response = await video_module.generate_video(request)

        assert response.success is True
        assert response.video_base64 is not None
        assert len(response.video_base64) > 0
        mock_client.session.get.assert_called_once()
