"""Tests for models/base.py — BaseImageModel, BaseVideoModel, ModelRegistry."""

import pytest

from models.base import BaseImageModel, BaseVideoModel, ModelRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear model registries before each test to avoid cross-contamination."""
    ModelRegistry._image_models.clear()
    ModelRegistry._video_models.clear()
    yield
    ModelRegistry._image_models.clear()
    ModelRegistry._video_models.clear()


class TestImageModelAutoRegisters:
    """Called Shot 1: Creating BaseImageModel auto-registers in ModelRegistry."""

    def test_image_model_auto_registers(self):
        assert len(ModelRegistry._image_models) == 0

        model = BaseImageModel(
            slug="test-model",
            display_name="Test Model",
            credits="50-100",
        )

        assert "test-model" in ModelRegistry._image_models
        assert ModelRegistry._image_models["test-model"] is model


class TestVideoModelAutoRegisters:
    """Called Shot 2: Creating BaseVideoModel auto-registers in ModelRegistry."""

    def test_video_model_auto_registers(self):
        assert len(ModelRegistry._video_models) == 0

        model = BaseVideoModel(
            slug="test-video-model",
            display_name="Test Video Model",
            api="test_api",
            model="test_model",
            mode="test_mode",
            family="test_family",
        )

        assert "test-video-model" in ModelRegistry._video_models
        assert ModelRegistry._video_models["test-video-model"] is model


class TestDiscoverLoadsAllModels:
    """Called Shot 3: ModelRegistry.discover() loads models from files."""

    def test_discover_loads_all_models(self):
        # Before discover, registries are empty (reset_registry runs)
        assert len(ModelRegistry._image_models) == 0
        assert len(ModelRegistry._video_models) == 0

        ModelRegistry.discover()

        # After discover, we should have the real models loaded from disk
        assert len(ModelRegistry._image_models) > 0
        assert len(ModelRegistry._video_models) > 0


class TestGetUnknownModelRaises:
    """Called Shot 4: Getting non-existent model raises ValueError."""

    def test_get_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown image model"):
            ModelRegistry.get_image("nonexistent-model")

        with pytest.raises(ValueError, match="Unknown video model"):
            ModelRegistry.get_video("nonexistent-video")


class TestImageModelBuildStartTtiBody:
    """Called Shot 5: build_start_tti_body returns correct dict structure."""

    def test_image_model_build_start_tti_body(self):
        model = BaseImageModel(
            slug="flux-2-pro",
            display_name="Flux 2 Pro",
            credits="75-150",
        )

        body = model.build_start_tti_body(
            prompt="A golden dragon",
            aspect_ratio="16:9",
            num_images=2,
        )

        assert body["mode"] == "flux-2-pro"
        assert body["prompt"] == "A golden dragon"
        assert body["aspect_ratio"] == "16:9"
        assert body["num_images"] == 2
        assert body["references"] == []
        assert body["color_palette"] is None
        assert body["variations"] is False
        assert body["modifiers"] == []

    def test_build_start_tti_body_with_references(self):
        model = BaseImageModel(
            slug="test",
            display_name="Test",
            credits="10",
        )
        refs = [{"image": "data:image/png;base64,abc", "type": "reference"}]

        body = model.build_start_tti_body(
            prompt="Test prompt",
            references=refs,
        )

        assert body["references"] == refs


class TestImageModelBuildRenderBody:
    """Called Shot 6: build_render_body returns correct dict with seed."""

    def test_image_model_build_render_body(self):
        model = BaseImageModel(
            slug="flux-2-pro",
            display_name="Flux 2 Pro",
            credits="75-150",
        )

        body = model.build_render_body(
            prompt="A golden dragon",
            family="family-123",
            request_token="token-abc",
            aspect_ratio="16:9",
            resolution="4k",
            width=1344,
            height=768,
            seed=42,
        )

        assert body["tool"] == "text-to-image"
        assert body["mode"] == "flux-2-pro"
        assert body["family"] == "family-123"
        assert body["request_token"] == "token-abc"
        assert body["prompt"] == "A golden dragon"
        assert body["seed"] == 42
        assert body["width"] == 1344
        assert body["height"] == 768
        assert body["aspect_ratio"] == "16:9"
        assert body["resolution"] == "4k"
        assert "metadata" in body
        assert body["metadata"]["inputPrompt"] == "A golden dragon"

    def test_build_render_body_auto_seed(self):
        model = BaseImageModel(
            slug="test",
            display_name="Test",
            credits="10",
        )

        body = model.build_render_body(
            prompt="Test",
            family="f",
            request_token="t",
        )

        # seed should be auto-generated when None
        assert body["seed"] is not None
        assert isinstance(body["seed"], int)


class TestVideoModelBuildVideoBody:
    """Called Shot 7: build_video_body returns correct nested structure."""

    def test_video_model_build_video_body(self):
        model = BaseVideoModel(
            slug="seedance-2-pro",
            display_name="Seedance 2 Pro",
            api="bytedance",
            model="seedance",
            mode="pro-2.0",
            family="bytedance",
        )

        body = model.build_video_body(
            prompt="A cinematic sunset",
            aspect_ratio="16:9",
            duration=5,
            seed=99,
        )

        assert "video" in body
        assert body["video"]["family"] == "bytedance"
        assert len(body["video"]["clips"]) == 1

        clip = body["video"]["clips"][0]
        assert clip["prompt"] == "A cinematic sunset"
        assert clip["aspectRatio"] == "16:9"
        assert clip["duration"] == 5
        assert clip["seed"] == 99
        assert clip["api"] == "bytedance"
        assert clip["model"] == "seedance"
        assert clip["mode"] == "pro-2.0"
        assert clip["slug"] == "seedance-2-pro"

    def test_build_video_body_with_references(self):
        model = BaseVideoModel(
            slug="test",
            display_name="Test",
            api="test",
            model="test",
            mode="test",
            family="test",
        )

        refs = [{"type": "image", "url": "https://example.com/img.jpg", "name": "hero"}]
        body = model.build_video_body(prompt="Test", references=refs)

        clip = body["video"]["clips"][0]
        assert clip["references"] == refs


class TestKlingOmni3UpdatedParams:
    """Called Shot 9: Kling Omni3 has updated params from Magnific API discovery.

    API data shows: duration 3-15s (not 5-10), 4K resolution (not just 720p/1080p),
    sound effects supported (was False, should be True).
    Import concrete model directly to avoid importlib cache issues in discover().
    """

    def test_kling_omni3_duration_range(self):
        from models.video.kling_omni3 import kling_omni3

        assert kling_omni3.duration_range == (3, 15), (
            f"Expected duration_range (3, 15), got {kling_omni3.duration_range}"
        )

    def test_kling_omni3_has_4k_resolution(self):
        from models.video.kling_omni3 import kling_omni3

        assert "4K" in kling_omni3.resolutions, (
            f"Expected '4K' in resolutions, got {kling_omni3.resolutions}"
        )

    def test_kling_omni3_supports_sound(self):
        from models.video.kling_omni3 import kling_omni3

        assert kling_omni3.supports_sound is True, (
            f"Expected supports_sound=True, got {kling_omni3.supports_sound}"
        )


class TestKling30Model:
    """Called Shot 10: Kling 3.0 model exists with correct params from API.

    API slug: kling-30, api: kling, model: kling, mode: 30
    Duration: 3-15s, Resolutions: 720p/1080p/4K, Sound: yes
    Image refs: 12 (start+end+3 character+3 product+3 advanced)
    Multishot: 6, Keyframes: start+end
    """

    def test_kling_30_slug_and_display_name(self):
        from models.video.kling_30 import kling_30

        assert kling_30.slug == "kling-30"
        assert kling_30.display_name == "Kling 3.0"

    def test_kling_30_to_dict_params(self):
        from models.video.kling_30 import kling_30

        d = kling_30.to_dict()

        assert d["slug"] == "kling-30"
        assert d["api"] == "kling"
        assert d["model"] == "kling"
        assert d["mode"] == "30"
        assert d["family"] == "kling"
        assert d["duration_range"] == [3, 15]
        assert d["resolutions"] == ["720p", "1080p", "4K"]
        assert d["max_image_refs"] == 12
        assert d["max_video_refs"] == 0
        assert d["multishot_max"] == 6
        assert d["supports_sound"] is True
        assert d["supports_keyframes"] == ["start", "end"]

    def test_kling_30_sound_in_video_body(self):
        from models.video.kling_30 import kling_30

        body = kling_30.build_video_body(
            prompt="A robot walking",
            with_sound=True,
        )

        clip = body["video"]["clips"][0]
        assert clip["withSoundEffects"] is True


class TestKlingMotionControl30Model:
    """Called Shot 11: Kling 3.0 Motion Control model with special constraints.

    API slug: kling-motion-control-30, mode: motion-control-30
    Requires: start frame (image) + video ref (both mandatory)
    No sound, no multishot, aspect_ratios from start frame (empty list)
    Keyframes: start + video (not end)
    """

    def test_kling_motion_control_30_slug_and_display(self):
        from models.video.kling_motion_control_30 import kling_motion_control_30

        assert kling_motion_control_30.slug == "kling-motion-control-30"
        assert kling_motion_control_30.display_name == "Kling 3.0 Motion Control"

    def test_kling_motion_control_30_to_dict(self):
        from models.video.kling_motion_control_30 import kling_motion_control_30

        d = kling_motion_control_30.to_dict()

        assert d["slug"] == "kling-motion-control-30"
        assert d["mode"] == "motion-control-30"
        assert d["duration_range"] == [3, 15]
        assert d["resolutions"] == ["720p", "1080p"]  # No 4K for MC
        assert d["max_image_refs"] == 1  # start frame mandatory
        assert d["max_video_refs"] == 1  # video ref mandatory
        assert d["multishot_max"] == 0  # no multishot
        assert d["supports_sound"] is False  # no sound
        assert d["supports_keyframes"] == ["start", "video"]  # not "end"


class TestGpt2ImageModel:
    """Called Shot 12: GPT Image 2 model with unique capabilities.

    API slug: gpt-2, tool: text-to-image, family: gpt
    Credits: 25-2100, Max refs: 16, Resolutions: 1k/2k/4k
    Supports: seed, quality (low/medium/high), smart prompt, color palette,
    effects, camera, character generator. Max prompt: 10000 chars.
    """

    def test_gpt_2_slug_and_display_name(self):
        from models.image.gpt_2 import gpt_2

        assert gpt_2.slug == "gpt-2"
        assert gpt_2.display_name == "GPT 2"

    def test_gpt_2_to_dict_params(self):
        from models.image.gpt_2 import gpt_2

        d = gpt_2.to_dict()

        assert d["slug"] == "gpt-2"
        assert d["display_name"] == "GPT 2"
        assert d["credits"] == "25-2100"
        assert d["resolutions"] == ["1k", "2k", "4k"]
        assert d["max_refs"] == 16


class TestModelToDict:
    """Called Shot 8: to_dict() serialization includes all fields."""

    def test_image_model_to_dict(self):
        model = BaseImageModel(
            slug="test-img",
            display_name="Test Image",
            credits="50-100",
            resolutions=["1k", "2k"],
            max_refs=10,
        )

        d = model.to_dict()
        assert d["slug"] == "test-img"
        assert d["display_name"] == "Test Image"
        assert d["credits"] == "50-100"
        assert d["resolutions"] == ["1k", "2k"]
        assert d["max_refs"] == 10

    def test_video_model_to_dict(self):
        model = BaseVideoModel(
            slug="test-vid",
            display_name="Test Video",
            api="test",
            model="test",
            mode="test",
            family="test",
            duration_range=(3, 10),
            max_image_refs=5,
            supports_sound=True,
        )

        d = model.to_dict()
        assert d["slug"] == "test-vid"
        assert d["display_name"] == "Test Video"
        assert d["api"] == "test"
        assert d["model"] == "test"
        assert d["mode"] == "test"
        assert d["family"] == "test"
        assert d["duration_range"] == [3, 10]
        assert d["max_image_refs"] == 5
        assert d["supports_sound"] is True
        assert "supports_keyframes" in d
        assert "aspect_ratios" in d
        assert "resolutions" in d
