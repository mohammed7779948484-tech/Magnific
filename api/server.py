"""FastAPI server for the Magnific local API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.middleware.error_handler import register_error_handlers
from api.middleware.rate_limiter import RateLimitMiddleware
from api.routes.image import router as image_router, set_deps as image_set_deps
from api.routes.status import router as status_router, set_deps as status_set_deps
from api.routes.video import router as video_router, set_deps as video_set_deps
from core.auth import Authenticator
from core.client import MagnificClient
from core.poller import Poller
from core.uploader import Uploader
from models.base import ModelRegistry
from utils.logger import setup_logger
from utils.cookie_parser import CookieParser

logger = setup_logger("server")

# Shared instances — initialized during lifespan
_client: MagnificClient | None = None


def create_app(
    cookies_file: str | None = None,
    cookies_dict: dict[str, str] | None = None,
    base_url: str | None = None,
    poll_interval: int = 5,
    poll_timeout: int = 180,
    rate_limit: int = 20,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        cookies_file: Path to cookies file (Netscape or JSON)
        cookies_dict: Direct cookie dict (alternative to file)
        base_url: Override base URL (magnific.com or freepik.com)
        poll_interval: Seconds between status polls
        poll_timeout: Max seconds to wait for generation
        rate_limit: Max requests per minute per client

    Returns:
        Configured FastAPI app
    """
    global _client

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialize and cleanup resources."""
        logger.info("Starting Magnific API server...")

        # Discover all models
        ModelRegistry.discover()
        logger.info(
            f"Loaded {len(ModelRegistry.list_images())} image models, "
            f"{len(ModelRegistry.list_videos())} video models"
        )

        # Load cookies
        cookies = None
        if cookies_dict:
            cookies = cookies_dict
        elif cookies_file:
            parser = CookieParser(cookies_file)
            cookies = parser.to_curl_cffi_dict()

        # Create HTTP client
        _client = MagnificClient(cookies=cookies, base_url=base_url)

        # Authenticate
        auth = Authenticator(_client)
        try:
            auth.authenticate()
            logger.info("Authentication successful")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.warning("Server started but NOT authenticated. API calls will fail until cookies are refreshed.")

        # Create shared dependencies
        poller = Poller(_client, poll_interval=poll_interval, poll_timeout=poll_timeout)
        uploader = Uploader(_client)

        # Inject into route modules
        image_set_deps(_client, poller, uploader)
        video_set_deps(_client, poller, uploader)
        status_set_deps(_client, poller)

        logger.info("Magnific API server ready")

        yield

        # Cleanup
        _client.close()
        logger.info("Magnific API server stopped")

    # Create FastAPI app
    app = FastAPI(
        title="Magnific API",
        description="Local API proxy for Freepik/Magnific AI generation (images & videos)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Register error handlers
    register_error_handlers(app)

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit)

    # Register routes
    app.include_router(image_router)
    app.include_router(video_router)
    app.include_router(status_router)

    # CORS middleware — allow all origins for local use
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
