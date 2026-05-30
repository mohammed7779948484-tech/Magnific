"""Constants used across the project."""


class AspectRatios:
    """Supported aspect ratios and their pixel dimensions at 1k resolution."""

    DATA = {
        "1:1":  (1024, 1024),
        "16:9": (1344, 768),
        "9:16": (768, 1344),
        "4:3":  (1152, 896),
        "3:4":  (896, 1152),
        "3:2":  (1216, 832),
        "2:3":  (832, 1216),
        "21:9": (1536, 640),
    }

    @classmethod
    def dimensions(cls, ratio: str, resolution: str = "1k") -> tuple[int, int]:
        """Get pixel dimensions for a ratio at a given resolution.

        Args:
            ratio: Aspect ratio string (e.g. "16:9")
            resolution: "1k", "2k", or "4k"

        Returns:
            Tuple of (width, height)
        """
        multiplier = {"1k": 1, "2k": 2, "4k": 4}.get(resolution, 1)
        w, h = cls.DATA[ratio]
        return (w * multiplier, h * multiplier)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls.DATA.keys())


class Resolutions:
    """Supported resolution values for images."""

    IMAGE = ["1k", "2k", "4k"]
    VIDEO = ["1080p", "720p", "480p"]


class ImageCategories:
    """Categories for image references."""

    CHARACTER = "character"
    PRODUCT = "product"
    IMAGE = "image"
    COMPOSITION = "composition"
    STYLE = "style"

    ALL = [CHARACTER, PRODUCT, IMAGE, COMPOSITION, STYLE]


class ReferenceLimits:
    """Reference limits per generation type."""

    MAX_IMAGE_REFS = 14          # Max refs for image generation
    MAX_VIDEO_IMAGE_REFS = 9     # Max image refs in video gen (Seedance 2.0)
    MAX_VIDEO_VIDEO_REFS = 2     # Max video refs in video gen
    MAX_VIDEO_AUDIO_REFS = 2     # Max audio refs in video gen
