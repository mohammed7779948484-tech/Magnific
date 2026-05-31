"""Tests for queue integration with image and video generation routes.

Called Shot Protocol:
    Tests verify that QueueManager hooks are called correctly during generation.
    Uses FakeQueueManager + FakeCreationRegistry — zero mocks.
"""

import pytest

from api.routes.image import generate_image, set_deps as image_set_deps
from api.schemas.image_schemas import ImageRequest
from api.routes.video import generate_video, set_deps as video_set_deps
from api.schemas.video_schemas import VideoRequest
from models.base import ModelRegistry
from tests.helpers.fake_deps import (
    FakeClient,
    FakeCreationRegistry,
    FakePoller,
    FakeQueueManager,
    FakeUploader,
)

# Import cached module for model re-registration
import models.image.nano_banana_2 as _nano_mod
import models.video.seedance_2_pro as _vid_mod


@pytest.fixture(autouse=True)
def _reset_module_deps():
    """Set lightweight fake deps before each test, tear down after."""
    slug = "imagen-nano-banana-2"
    if slug not in ModelRegistry._image_models:
        ModelRegistry._image_models[slug] = _nano_mod.nano_banana_2
    vslug = "bytedance-seedance-pro-2.0"
    if vslug not in ModelRegistry._video_models:
        ModelRegistry._video_models[vslug] = _vid_mod.seedance_2_pro

    client = FakeClient(xsrf_token="fake-token")
    poller = FakePoller()
    uploader = FakeUploader()
    qm = FakeQueueManager(enabled=False)
    reg = FakeCreationRegistry()

    image_set_deps(client, poller, uploader, queue_manager=qm, creation_registry=reg)
    video_set_deps(client, poller, uploader, queue_manager=qm, creation_registry=reg)

    yield

    import api.routes.image as img_mod
    import api.routes.video as vid_mod
    img_mod._client = None
    img_mod._poller = None
    img_mod._uploader = None
    img_mod._queue_manager = None
    img_mod._registry = None
    vid_mod._client = None
    vid_mod._poller = None
    vid_mod._uploader = None
    vid_mod._queue_manager = None
    vid_mod._registry = None


def _make_image_request(**overrides) -> ImageRequest:
    defaults = dict(prompt="test prompt", model="imagen-nano-banana-2", wait=True, download=False)
    defaults.update(overrides)
    return ImageRequest(**defaults)


def _make_video_request(**overrides) -> VideoRequest:
    defaults = dict(prompt="test video", model="bytedance-seedance-pro-2.0", wait=True, download=False)
    defaults.update(overrides)
    return VideoRequest(**defaults)


# ─── Called Shot 1: Image generation clears queue when enabled ──────────────

@pytest.mark.asyncio
async def test_image_generate_clears_queue_when_enabled():
    """When queue_manager is enabled, clear_external_queue is called before start-tti-v2."""
    import api.routes.image as img_mod

    qm = FakeQueueManager(enabled=True)
    qm.clear_result = {"cleared": 1, "errors": 0, "skipped_ours": 0, "total_queued": 1, "enabled": True, "reason": "cleared", "cancelled_identifiers": ["ext_x"], "skipped_identifiers": []}
    reg = FakeCreationRegistry()
    img_mod._queue_manager = qm
    img_mod._registry = reg

    img_mod._client.post_responses = [
        {"request_tokens": ["tok123"], "family": "test"},
        {"creation": {"id": "42", "identifier": "img_abc"}},
    ]

    request = _make_image_request(wait=False)
    await generate_image(request)

    assert qm.clear_external_queue_calls == 1


# ─── Called Shot 2: Image generation registers creation after submit ──────────

@pytest.mark.asyncio
async def test_image_generate_registers_creation_after_submit():
    """After render/v4, registry.register is called with creation identifier."""
    import api.routes.image as img_mod

    qm = FakeQueueManager(enabled=False)
    reg = FakeCreationRegistry()
    img_mod._queue_manager = qm
    img_mod._registry = reg

    img_mod._client.post_responses = [
        {"request_tokens": ["tok123"], "family": "test"},
        {"creation": {"id": "42", "identifier": "img_abc"}},
    ]

    request = _make_image_request(wait=False)
    await generate_image(request)

    assert len(reg.register_calls) == 1
    assert reg.register_calls[0][0] == "img_abc"
    assert reg.register_calls[0][1]["tool"] == "text-to-image"


# ─── Called Shot 3: Image generation unregisters on completion ──────────────

@pytest.mark.asyncio
async def test_image_generate_unregisters_on_completion():
    """After poll completes, registry.unregister is called."""
    import api.routes.image as img_mod

    qm = FakeQueueManager(enabled=False)
    reg = FakeCreationRegistry()
    img_mod._queue_manager = qm
    img_mod._registry = reg

    img_mod._client.post_responses = [
        {"request_tokens": ["tok123"], "family": "test"},
        {"creation": {"id": "42", "identifier": "img_abc"}},
    ]
    img_mod._poller.poll_result = {"download_url": "https://example.com/img.png"}

    request = _make_image_request(wait=True, download=False)
    await generate_image(request)

    assert "img_abc" in reg.unregister_calls


# ─── Called Shot 4: Image skips clear when disabled ────────────────────────

@pytest.mark.asyncio
async def test_image_generate_skips_clear_when_disabled():
    """When queue_manager is disabled, clear is NOT called."""
    import api.routes.image as img_mod

    qm = FakeQueueManager(enabled=False)
    reg = FakeCreationRegistry()
    img_mod._queue_manager = qm
    img_mod._registry = reg

    img_mod._client.post_responses = [
        {"request_tokens": ["tok123"], "family": "test"},
        {"creation": {"id": "42", "identifier": "img_abc"}},
    ]

    request = _make_image_request(wait=False)
    await generate_image(request)

    assert qm.clear_external_queue_calls == 0


# ─── Called Shot 5: Video generation clears queue when enabled ─────────────

@pytest.mark.asyncio
async def test_video_generate_clears_queue_when_enabled():
    """When queue_manager is enabled, clear_external_queue is called."""
    import api.routes.video as vid_mod

    qm = FakeQueueManager(enabled=True)
    qm.clear_result = {"cleared": 1, "errors": 0, "skipped_ours": 0, "total_queued": 1, "enabled": True, "reason": "cleared", "cancelled_identifiers": ["ext_x"], "skipped_identifiers": []}
    reg = FakeCreationRegistry()
    vid_mod._queue_manager = qm
    vid_mod._registry = reg

    vid_mod._client.post_responses = [
        {"data": {"creations": [{"id": 55, "identifier": "vid_xyz"}]}},
    ]

    request = _make_video_request(wait=False)
    await generate_video(request)

    assert qm.clear_external_queue_calls == 1


# ─── Called Shot 6: Video generation registers creation after submit ────────

@pytest.mark.asyncio
async def test_video_generate_registers_creation_after_submit():
    """After video/generate, registry.register is called with identifier."""
    import api.routes.video as vid_mod

    qm = FakeQueueManager(enabled=False)
    reg = FakeCreationRegistry()
    vid_mod._queue_manager = qm
    vid_mod._registry = reg

    vid_mod._client.post_responses = [
        {"data": {"creations": [{"id": 55, "identifier": "vid_xyz"}]}},
    ]

    request = _make_video_request(wait=False)
    await generate_video(request)

    assert len(reg.register_calls) == 1
    assert reg.register_calls[0][0] == "vid_xyz"
    assert reg.register_calls[0][1]["tool"] == "video-generator"


# ─── Called Shot 7: Video generation unregisters on completion ──────────────

@pytest.mark.asyncio
async def test_video_generate_unregisters_on_completion():
    """After poll completes, registry.unregister is called."""
    import api.routes.video as vid_mod

    qm = FakeQueueManager(enabled=False)
    reg = FakeCreationRegistry()
    vid_mod._queue_manager = qm
    vid_mod._registry = reg

    vid_mod._client.post_responses = [
        {"data": {"creations": [{"id": 55, "identifier": "vid_xyz"}]}},
    ]
    vid_mod._poller.poll_result = {"download_url": "https://example.com/vid.mp4"}

    request = _make_video_request(wait=True, download=False)
    await generate_video(request)

    assert "vid_xyz" in reg.unregister_calls
