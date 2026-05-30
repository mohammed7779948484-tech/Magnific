"""Tests for Pydantic schema validation on ImageRequest and VideoRequest."""

import pytest
from pydantic import ValidationError

from api.schemas.image_schemas import ImageRequest
from api.schemas.video_schemas import VideoRequest


# ── ImageRequest Validation Tests ──────────────────────────────────────


class TestImagePromptEmptyRaises:
    """Called Shot 1: Empty prompt raises ValidationError."""

    def test_image_prompt_empty_raises(self):
        with pytest.raises(ValidationError):
            ImageRequest(prompt="")


class TestImagePromptTooLongRaises:
    """Called Shot 2: Prompt > 2000 chars raises ValidationError."""

    def test_image_prompt_too_long_raises(self):
        with pytest.raises(ValidationError):
            ImageRequest(prompt="x" * 2001)


class TestImageInvalidAspectRatioRaises:
    """Called Shot 3: Invalid ratio like "5:4" raises ValidationError."""

    def test_image_invalid_aspect_ratio_raises(self):
        with pytest.raises(ValidationError):
            ImageRequest(prompt="a castle", aspect_ratio="5:4")


class TestImageInvalidResolutionRaises:
    """Called Shot 4: Resolution "8k" raises ValidationError."""

    def test_image_invalid_resolution_raises(self):
        with pytest.raises(ValidationError):
            ImageRequest(prompt="a castle", resolution="8k")


class TestImageValidRequestPasses:
    """Called Shot 8: Valid ImageRequest passes validation."""

    def test_image_valid_request_passes(self):
        req = ImageRequest(
            prompt="A golden dragon in a mountain fortress",
            model="imagen-nano-banana-2",
            aspect_ratio="16:9",
            resolution="4k",
            seed=12345,
        )
        assert req.prompt == "A golden dragon in a mountain fortress"
        assert req.aspect_ratio == "16:9"
        assert req.resolution == "4k"
        assert req.seed == 12345


# ── VideoRequest Validation Tests ──────────────────────────────────────


class TestVideoDurationZeroRaises:
    """Called Shot 5: Duration 0 raises ValidationError."""

    def test_video_duration_zero_raises(self):
        with pytest.raises(ValidationError):
            VideoRequest(prompt="a bird flying", duration=0)


class TestVideoDurationNegativeRaises:
    """Called Shot 6: Duration -1 raises ValidationError."""

    def test_video_duration_negative_raises(self):
        with pytest.raises(ValidationError):
            VideoRequest(prompt="a bird flying", duration=-1)


class TestVideoInvalidResolutionRaises:
    """Called Shot 7: Resolution "4k" raises ValidationError (videos use 1080p etc.)."""

    def test_video_invalid_resolution_raises(self):
        with pytest.raises(ValidationError):
            VideoRequest(prompt="a bird flying", resolution="4k")


class TestVideoValidRequestPasses:
    """Called Shot 9: Valid VideoRequest passes validation."""

    def test_video_valid_request_passes(self):
        req = VideoRequest(
            prompt="A cinematic sunset over the ocean",
            model="bytedance-seedance-pro-2.0",
            aspect_ratio="16:9",
            duration=10,
            resolution="1080p",
        )
        assert req.prompt == "A cinematic sunset over the ocean"
        assert req.duration == 10
        assert req.resolution == "1080p"
