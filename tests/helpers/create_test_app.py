"""Factory for creating a test FastAPI app with lightweight fake dependencies.

This creates a real FastAPI app with real routes but injects FakeClient,
FakePoller, and FakeUploader so no network calls happen. No mocks needed.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.error_handler import register_error_handlers
from api.middleware.rate_limiter import RateLimitMiddleware
from api.routes.image import router as image_router, set_deps as image_set_deps
from api.routes.status import router as status_router, set_deps as status_set_deps
from api.routes.video import router as video_router, set_deps as video_set_deps
from models.base import ModelRegistry
from tests.helpers.fake_deps import FakeClient, FakePoller, FakeUploader


def create_test_app(
    rate_limit: int = 999,
    xsrf_token: str | None = "fake-token",
) -> FastAPI:
    """Create a FastAPI app for testing with no network dependencies.

    Uses a no-op lifespan that injects lightweight fakes instead of
    real MagnificClient/CookieParser/Authenticator. No mocks involved.

    Args:
        rate_limit: Rate limit (default 999 to avoid rate limiting in tests)
        xsrf_token: XSRF token value (default "fake-token" for authenticated state)

    Returns:
        FastAPI app ready for TestClient
    """

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        """No-op lifespan: inject fakes and discover models."""
        # Discover models (reads local files only, no network)
        ModelRegistry.discover()

        # Create lightweight fakes — no network calls
        client = FakeClient(xsrf_token=xsrf_token)
        poller = FakePoller()
        uploader = FakeUploader()

        # Inject into route modules (same as production create_app)
        image_set_deps(client, poller, uploader)
        video_set_deps(client, poller, uploader)
        status_set_deps(client, poller)

        yield

        # Cleanup — reset module globals
        import api.routes.image as img_mod
        import api.routes.status as stat_mod
        import api.routes.video as vid_mod
        img_mod._client = None
        img_mod._poller = None
        img_mod._uploader = None
        vid_mod._client = None
        vid_mod._poller = None
        vid_mod._uploader = None
        stat_mod._client = None
        stat_mod._poller = None

    app = FastAPI(
        title="Magnific API (Test)",
        version="1.0.0-test",
        lifespan=test_lifespan,
    )

    # Register error handlers (same as production)
    register_error_handlers(app)

    # CORS middleware — MUST be first (before rate limiter), same as production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware — after CORS, same as production
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=rate_limit,
    )

    # Register routes (same as production)
    app.include_router(image_router)
    app.include_router(video_router)
    app.include_router(status_router)

    # Static files — create a temp downloads dir
    downloads_dir = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    try:
        from fastapi.staticfiles import StaticFiles
        app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")
    except Exception:
        pass  # StaticFiles might not be available in all test environments

    return app
