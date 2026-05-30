"""All API endpoints used by Magnific internal API.

Thread Safety:
    The class-level BASE_URL and API_PREFIX are mutable shared state. All
    mutations are guarded by ``_lock`` (a ``threading.Lock``).  Callers that
    need to switch the base URL during concurrent request processing should
    always go through :meth:`set_base_url` or :meth:`reset` to avoid corrupt
    state (e.g. magnific URL paired with /pikaso prefix).
"""

import threading


class Endpoints:
    """Central registry of all Magnific/Pikaso/Freepik API endpoints.

    Supports magnific.com (prefix: /app) and freepik.com (prefix: /pikaso).
    The prefix is auto-detected from the base URL.

    **Thread safety:** All mutations of BASE_URL / API_PREFIX are serialized
    via ``_lock`` so that concurrent calls to :meth:`set_base_url` or
    :meth:`reset` can never produce an inconsistent URL/prefix pair.
    """

    _DEFAULT_BASE_URL = "https://www.magnific.com"
    _DEFAULT_API_PREFIX = "/app"

    BASE_URL = _DEFAULT_BASE_URL
    API_PREFIX = _DEFAULT_API_PREFIX

    _lock: threading.Lock = threading.Lock()

    @classmethod
    def set_base_url(cls, url: str):
        """Override the base URL and auto-detect API prefix.

        Thread-safe: acquires ``_lock`` before mutating class variables.
        """
        with cls._lock:
            cls.BASE_URL = url
            if "freepik.com" in url or "freepik.es" in url:
                cls.API_PREFIX = "/pikaso"
            else:
                cls.API_PREFIX = "/app"

    @classmethod
    def set_api_prefix(cls, prefix: str):
        """Manually override the API prefix.

        Thread-safe: acquires ``_lock`` before mutating.
        """
        with cls._lock:
            cls.API_PREFIX = prefix

    @classmethod
    def reset(cls):
        """Restore BASE_URL and API_PREFIX to their defaults.

        Thread-safe: acquires ``_lock`` before mutating.
        """
        with cls._lock:
            cls.BASE_URL = cls._DEFAULT_BASE_URL
            cls.API_PREFIX = cls._DEFAULT_API_PREFIX

    @classmethod
    def _p(cls, path: str) -> str:
        """Build API path with prefix."""
        return f"{cls.API_PREFIX}{path}"

    @classmethod
    def url(cls, path: str) -> str:
        """Build full URL from relative path."""
        return f"{cls.BASE_URL}{path}"

    @classmethod
    def creation_detail(cls, creation_id) -> str:
        return cls._p(f"/api/creation/{creation_id}")

    @classmethod
    def creations_list(cls) -> str:
        return cls._p("/api/creations")

    # ── Auth & Security ──────────────────────────────────────────────
    CSRF_COOKIE = "/sanctum/csrf-cookie"          # Needs prefix at runtime
    DEVICE_IDENTIFY = "/user/api/devices/identify"  # No prefix needed

    @classmethod
    def csrf_cookie(cls) -> str:
        return cls._p("/sanctum/csrf-cookie")

    # ── Image Generation ─────────────────────────────────────────────
    START_TTI_V2 = "/api/start-tti-v2"
    RENDER_V4 = "/api/render/v4"

    # ── Video Generation ─────────────────────────────────────────────
    VIDEO_GENERATE = "/api/video/generate"
    VIDEO_SIMULATE = "/api/video/simulate/generate"
    VIDEO_CANCEL = "/api/video/cancel"

    # ── File Upload ─────────────────────────────────────────────────
    TEMPORAL_STORAGE = "/api/temporal-storage"
    UPLOAD_FRAME = "/api/video/generate/upload-frame"
    UPLOAD_FRAMES = "/api/video/generate/upload-frames"

    # ── Model Discovery ───────────────────────────────────────────
    AI_MODELS = "/api/v2/ai-models"
    VIDEO_AI_MODELS = "/api/video/ai-models"
    CUSTOM_MODELS = "/api/custom-models"

    # ── Extra Features ─────────────────────────────────────────────
    DESCRIBE_FRAMES = "/api/video/describe-frames"
    PROMPT_IMPROVEMENT = "/api/video/prompt-improvement"
    SOUND_EFFECTS = "/api/video/feature/soundfx"
    VIDEO_EXTENSION = "/api/video/feature/extension"
    AUTO_CAPTION = "/api/video/feature/auto-caption"
    MULTI_SHOT = "/api/video/create-multi-shot-scenes"
