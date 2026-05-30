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
