"""Base model classes and automatic model registry.

Every model (image/video) inherits from BaseImageModel or BaseVideoModel.
The registry automatically discovers and registers all models.
Adding a new model = creating a single file in the appropriate directory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from utils.logger import setup_logger

logger = setup_logger("models")


# ── Model Registry ────────────────────────────────────────────────────

class ModelRegistry:
    """Automatic registry for all models.

    Call ModelRegistry.discover() to scan all model files and register them.
    Then use ModelRegistry.get_image("slug") or ModelRegistry.get_video("slug").
    """

    _image_models: dict[str, BaseImageModel] = {}
    _video_models: dict[str, BaseVideoModel] = {}

    @classmethod
    def register_image(cls, model: BaseImageModel):
        """Register an image generation model."""
        if model.slug in cls._image_models:
            logger.warning(f"Image model '{model.slug}' already registered, overwriting")
        cls._image_models[model.slug] = model
        logger.debug(f"Registered image model: {model.slug} ({model.display_name})")

    @classmethod
    def register_video(cls, model: BaseVideoModel):
        """Register a video generation model."""
        if model.slug in cls._video_models:
            logger.warning(f"Video model '{model.slug}' already registered, overwriting")
        cls._video_models[model.slug] = model
        logger.debug(f"Registered video model: {model.slug} ({model.display_name})")

    @classmethod
    def get_image(cls, slug: str) -> BaseImageModel:
        """Get an image model by slug."""
        if slug not in cls._image_models:
            available = ", ".join(cls._image_models.keys()) or "none"
            raise ValueError(f"Unknown image model: '{slug}'. Available: {available}")
        return cls._image_models[slug]

    @classmethod
    def get_video(cls, slug: str) -> BaseVideoModel:
        """Get a video model by slug."""
        if slug not in cls._video_models:
            available = ", ".join(cls._video_models.keys()) or "none"
            raise ValueError(f"Unknown video model: '{slug}'. Available: {available}")
        return cls._video_models[slug]

    @classmethod
    def list_images(cls) -> dict[str, BaseImageModel]:
        return dict(cls._image_models)

    @classmethod
    def list_videos(cls) -> dict[str, BaseVideoModel]:
        return dict(cls._video_models)

    @classmethod
    def discover(cls):
        """Scan model directories and register all models."""
        cls._discover_image_models()
        cls._discover_video_models()
        logger.info(
            f"Discovered {len(cls._image_models)} image models, "
            f"{len(cls._video_models)} video models"
        )

    @classmethod
    def _discover_image_models(cls):
        """Import all modules in models/image/ to trigger registration."""
        from pathlib import Path
        import importlib

        package_dir = Path(__file__).parent / "image"
        if not package_dir.exists():
            return

        for file in sorted(package_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
            module_name = f"models.image.{file.stem}"
            try:
                importlib.import_module(module_name)
            except Exception as e:
                logger.error(f"Failed to import {module_name}: {e}")

    @classmethod
    def _discover_video_models(cls):
        """Import all modules in models/video/ to trigger registration."""
        from pathlib import Path
        import importlib

        package_dir = Path(__file__).parent / "video"
        if not package_dir.exists():
            return

        for file in sorted(package_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
            module_name = f"models.video.{file.stem}"
            try:
                importlib.import_module(module_name)
            except Exception as e:
                logger.error(f"Failed to import {module_name}: {e}")


# ── Base Image Model ─────────────────────────────────────────────────

@dataclass
class BaseImageModel:
    """Base class for all image generation models.

    Attributes:
        slug: Internal model identifier used in API calls
        display_name: Human-readable model name
        credits: Credit cost range (e.g. "75-150")
        resolutions: Available resolutions (e.g. ["1k", "2k", "4k"])
        max_refs: Maximum number of reference images
    """

    slug: str
    display_name: str
    credits: str
    resolutions: list[str] = field(default_factory=lambda: ["1k", "2k", "4k"])
    max_refs: int = 14

    def __post_init__(self):
        """Auto-register this model when created."""
        ModelRegistry.register_image(self)

    def build_start_tti_body(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        num_images: int = 1,
        references: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        """Build the request body for start-tti-v2 endpoint.

        Args:
            prompt: Text prompt for image generation
            aspect_ratio: Aspect ratio (e.g. "16:9")
            num_images: Number of images to generate
            references: List of reference dicts for start-tti-v2 format
                [{image: "temporal:...", type: "reference", category: "product", label: "name", frame: None}]
            **kwargs: Additional optional fields

        Returns:
            Dict body for POST /pikaso/api/start-tti-v2
        """
        return {
            "mode": self.slug,
            "prompt": prompt,
            "references": references or [],
            "num_images": num_images,
            "aspect_ratio": aspect_ratio,
            "color_palette": kwargs.get("color_palette", None),
            "color_palette_id": kwargs.get("color_palette_id", None),
            "variations": kwargs.get("variations", False),
            "force_credits": kwargs.get("force_credits", False),
            "modifiers": kwargs.get("modifiers", []),
        }

    def build_render_body(
        self,
        prompt: str,
        family: str,
        request_token: str,
        aspect_ratio: str = "1:1",
        resolution: str = "4k",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
        negative_prompt: str | None = None,
        image_references: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        """Build the request body for render/v4 endpoint.

        IMPORTANT: image_references MUST use base64 + id + label format.
        temporal: paths are blocked by Cloudflare WAF.
        URLs are rejected by API validation.

        Args:
            prompt: Text prompt
            family: Family ID from start-tti-v2 response
            request_token: Token from start-tti-v2 response
            aspect_ratio: Aspect ratio
            resolution: "1k", "2k", or "4k"
            width: Image width in pixels
            height: Image height in pixels
            seed: Random seed (None = auto-generate)
            negative_prompt: Negative prompt
            image_references: List of reference dicts for render/v4 format
                [{id: "label", label: "label", image: "data:...", type: "reference", category: "product", frame: None}]
            **kwargs: Additional optional fields

        Returns:
            Dict body for POST /pikaso/api/render/v4
        """
        import random

        return {
            "tool": "text-to-image",
            "mode": self.slug,
            "family": family,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": seed if seed is not None else random.randint(0, 9999999),
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "quality": kwargs.get("quality", None),
            "thinking_level": kwargs.get("thinking_level", None),
            "image_references": image_references or [],
            "color_palette": kwargs.get("color_palette", None),
            "color_palette_id": kwargs.get("color_palette_id", None),
            "cinematographer": kwargs.get("cinematographer", None),
            "request_token": request_token,
            "force_credits": kwargs.get("force_credits", False),
            "board_uuid": kwargs.get("board_uuid", None),
            "metadata": {
                "inputPrompt": prompt,
                "aspectRatio": aspect_ratio,
                "mode": self.slug,
                "unlimited": kwargs.get("unlimited", False),
                "smartPrompt": kwargs.get("smart_prompt", False),
            },
            "modifiers": kwargs.get("modifiers", []),
            "smart_prompt": kwargs.get("smart_prompt", False),
            "image_index": kwargs.get("image_index", 0),
            "num_images": kwargs.get("num_images", 1),
            "custom_references": kwargs.get("custom_references", {}),
        }

    def to_dict(self) -> dict:
        """Serialize model info to dict."""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "credits": self.credits,
            "resolutions": self.resolutions,
            "max_refs": self.max_refs,
        }


# ── Base Video Model ─────────────────────────────────────────────────

@dataclass
class BaseVideoModel:
    """Base class for all video generation models.

    Attributes:
        slug: Full slug (e.g. "bytedance-seedance-pro-2.0")
        display_name: Human-readable name
        api: API family (e.g. "bytedance")
        model: Model name (e.g. "seedance")
        mode: Mode identifier (e.g. "pro-2.0")
        family: Family identifier (e.g. "bytedance")
        duration_range: Tuple of (min_seconds, max_seconds)
        aspect_ratios: Available aspect ratios
        resolutions: Available resolutions
        max_image_refs: Maximum image references
        max_video_refs: Maximum video references (0 = not supported)
        max_audio_refs: Maximum audio references
        multishot_max: Max scenes for multi-shot (0 = not supported)
        supports_sound: Whether sound effects are supported
        supports_keyframes: Which keyframe types are supported
    """

    slug: str
    display_name: str
    api: str
    model: str
    mode: str
    family: str
    duration_range: tuple[int, int] = (4, 15)
    aspect_ratios: list[str] = field(default_factory=lambda: ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"])
    resolutions: list[str] = field(default_factory=lambda: ["1080p", "720p", "480p"])
    max_image_refs: int = 9
    max_video_refs: int = 0
    max_audio_refs: int = 0
    multishot_max: int = 0
    supports_sound: bool = False
    supports_keyframes: list[str] = field(default_factory=lambda: ["start"])

    def __post_init__(self):
        """Auto-register this model when created."""
        ModelRegistry.register_video(self)

    def build_video_body(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "1080p",
        negative_prompt: str = "",
        references: list[dict] | None = None,
        keyframes: dict | None = None,
        audio_url: str | None = None,
        with_sound: bool = False,
        prompt_type: str = "basic",
        multi_prompt: list[dict] | None = None,
        seed: int | None = None,
        **kwargs,
    ) -> dict:
        """Build the request body for video/generate endpoint.

        Args:
            prompt: Text prompt for video generation
            aspect_ratio: Aspect ratio
            duration: Video duration in seconds
            resolution: Video resolution
            negative_prompt: Negative prompt
            references: List of reference dicts
                [{type: "image", url: "...", name: "hero"}, ...]
            keyframes: Keyframe dict
                {start: {type: "image", url: "..."}, end: {type: "image", url: "..."}}
            audio_url: Audio URL for background music
            with_sound: Whether to add AI sound effects
            prompt_type: "basic" or "multishot"
            multi_prompt: Multi-shot scene descriptions
            seed: Random seed
            **kwargs: Additional optional fields

        Returns:
            Dict body for POST /pikaso/api/video/generate
        """
        # Build keyframes structure
        keyframes_struct = {
            "start": None,
            "end": None,
            "video": None,
            "sketch": None,
        }
        if keyframes:
            if "start" in keyframes and keyframes["start"]:
                keyframes_struct["start"] = keyframes["start"]
            if "end" in keyframes and keyframes["end"]:
                keyframes_struct["end"] = keyframes["end"]
            if "video" in keyframes and keyframes["video"]:
                keyframes_struct["video"] = keyframes["video"]
            if "sketch" in keyframes and keyframes["sketch"]:
                keyframes_struct["sketch"] = keyframes["sketch"]

        clip: dict[str, Any] = {
            "position": 0,
            "prompt": prompt,
            "negativePrompt": negative_prompt,
            "name": prompt,
            "family": self.family,
            "aspectRatio": aspect_ratio,
            "cameraMotion": None,
            "duration": duration,
            "api": self.api,
            "model": self.model,
            "mode": self.mode,
            "slug": self.slug,
            "extraParameters": {},
            "seed": seed,
            "withSoundEffects": with_sound and self.supports_sound,
            "promptType": prompt_type,
            "resolution": resolution,
            "keyframes": keyframes_struct,
            "references": references or [],
            "audioUrl": audio_url,
            "voices": [],
            "draftId": None,
            "boardUuid": None,
            "videoPreset": "custom",
        }

        # Add multi_prompt if multishot
        if prompt_type == "multishot" and multi_prompt:
            clip["multi_prompt"] = multi_prompt

        return {
            "video": {
                "family": self.family,
                "clips": [clip],
            }
        }

    def to_dict(self) -> dict:
        """Serialize model info to dict."""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "api": self.api,
            "model": self.model,
            "mode": self.mode,
            "family": self.family,
            "duration_range": list(self.duration_range),
            "aspect_ratios": self.aspect_ratios,
            "resolutions": self.resolutions,
            "max_image_refs": self.max_image_refs,
            "max_video_refs": self.max_video_refs,
            "max_audio_refs": self.max_audio_refs,
            "multishot_max": self.multishot_max,
            "supports_sound": self.supports_sound,
            "supports_keyframes": self.supports_keyframes,
        }
