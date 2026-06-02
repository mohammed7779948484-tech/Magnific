"""FastAPI server for the Magnific local API."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.middleware.error_handler import register_error_handlers
from api.middleware.rate_limiter import RateLimitMiddleware
from api.routes.image import router as image_router, set_deps as image_set_deps
from api.routes.monitor import router as monitor_router, set_deps as monitor_set_deps
from api.routes.queue import router as queue_router, set_deps as queue_set_deps
from api.routes.status import router as status_router, set_deps as status_set_deps
from api.routes.video import router as video_router, set_deps as video_set_deps
from api.routes.assets import router as assets_router, set_deps as assets_set_deps
from core.auth import Authenticator
from core.client import MagnificClient
from core.creation_registry import CreationRegistry
from core.monitor import MagnificMonitor
from core.poller import Poller
from core.queue_manager import QueueManager
from core.uploader import Uploader
from core.cloudinary_service import CloudinaryService
from core.asset_registry import AssetRegistry
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
    cloudinary_cloud_name: str | None = None,
    cloudinary_api_key: str | None = None,
    cloudinary_api_secret: str | None = None,
    cloudinary_folder: str = "magnific",
    cloudinary_enabled: bool = True,
    data_dir: str = "data",
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        cookies_file: Path to cookies file (Netscape or JSON)
        cookies_dict: Direct cookie dict (alternative to file)
        base_url: Override base URL (magnific.com or freepik.com)
        poll_interval: Seconds between status polls
        poll_timeout: Max seconds to wait for generation
        rate_limit: Max requests per minute per client
        cloudinary_cloud_name: Cloudinary cloud name
        cloudinary_api_key: Cloudinary API key
        cloudinary_api_secret: Cloudinary API secret
        cloudinary_folder: Root folder for uploads (default: "magnific")
        cloudinary_enabled: Whether cloud storage is active (default: True)
        data_dir: Directory for asset registry JSON (default: "data")

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
        monitor = MagnificMonitor(_client)
        creation_registry = CreationRegistry()
        queue_manager = QueueManager(_client, creation_registry, enabled=False)

        # Initialize Cloudinary service (optional — gracefully disabled if not configured)
        cloudinary_service = None
        try:
            if cloudinary_enabled and cloudinary_cloud_name and cloudinary_api_key and cloudinary_api_secret:
                cloudinary_service = CloudinaryService(
                    cloud_name=cloudinary_cloud_name,
                    api_key=cloudinary_api_key,
                    api_secret=cloudinary_api_secret,
                    folder=cloudinary_folder,
                    enabled=True,
                )
            else:
                cloudinary_service = CloudinaryService(enabled=False)
                logger.info("Cloudinary: disabled (no credentials provided)")
        except Exception as e:
            logger.warning(f"Cloudinary initialization failed (non-fatal): {e}")
            cloudinary_service = CloudinaryService(enabled=False)

        # Initialize asset registry (always available)
        asset_registry = AssetRegistry(data_dir=data_dir)
        logger.info(f"Asset registry initialized at {data_dir}/assets.json")

        # Inject into route modules
        image_set_deps(_client, poller, uploader,
                       queue_manager=queue_manager, creation_registry=creation_registry,
                       cloudinary_service=cloudinary_service, asset_registry=asset_registry)
        video_set_deps(_client, poller, uploader,
                       queue_manager=queue_manager, creation_registry=creation_registry,
                       cloudinary_service=cloudinary_service, asset_registry=asset_registry)
        status_set_deps(_client, poller)
        monitor_set_deps(monitor)
        queue_set_deps(queue_manager, creation_registry)
        assets_set_deps(cloudinary_service=cloudinary_service, asset_registry=asset_registry)

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

    # CORS middleware — MUST be first (before rate limiter)
    # Note: per CORS spec, allow_credentials=True requires specific origins (not "*")
    # Starlette handles this by echoing the request Origin back when "*" is set,
    # but we explicitly list localhost origins for correctness.
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

    # Rate limiting middleware — after CORS
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit)

    # Register routes
    app.include_router(image_router)
    app.include_router(video_router)
    app.include_router(status_router)
    app.include_router(monitor_router)
    app.include_router(queue_router)
    app.include_router(assets_router)

    # Static files — serve generated downloads
    downloads_dir = os.path.join(os.path.dirname(__file__), "..", "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")

    return app
