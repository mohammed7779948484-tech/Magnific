"""Tests for config/constants.py — AspectRatios class."""

import pytest

from config.constants import AspectRatios


class TestAspectRatioDimensions1k:
    """Called Shot 1: 1:1 at 1k = 1024x1024."""

    def test_aspect_ratio_dimensions_1k(self):
        w, h = AspectRatios.dimensions("1:1", "1k")
        assert w == 1024
        assert h == 1024


class TestAspectRatioDimensions16_9:
    """Called Shot 2: 16:9 at 1k = 1344x768."""

    def test_aspect_ratio_dimensions_16_9(self):
        w, h = AspectRatios.dimensions("16:9", "1k")
        assert w == 1344
        assert h == 768


class TestAspectRatioScaling4k:
    """Called Shot 3: 1:1 at 4k = 4096x4096 (4x multiplier)."""

    def test_aspect_ratio_scaling_4k(self):
        w, h = AspectRatios.dimensions("1:1", "4k")
        assert w == 4096
        assert h == 4096


class TestInvalidRatioRaisesKeyError:
    """Called Shot 4: Invalid ratio raises KeyError."""

    def test_invalid_ratio_raises_key_error(self):
        with pytest.raises(KeyError):
            AspectRatios.dimensions("99:1", "1k")


class TestAvailableRatios:
    """Extra: available() returns all known ratios."""

    def test_available_ratios(self):
        ratios = AspectRatios.available()
        assert "1:1" in ratios
        assert "16:9" in ratios
        assert "4:3" in ratios
        assert "21:9" in ratios


class Test2kScaling:
    """Extra: 2k doubles 1k dimensions."""

    def test_2k_scaling(self):
        w1k, h1k = AspectRatios.dimensions("16:9", "1k")
        w2k, h2k = AspectRatios.dimensions("16:9", "2k")
        assert w2k == w1k * 2
        assert h2k == h1k * 2
