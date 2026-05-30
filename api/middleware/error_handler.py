"""Global error handler for the API server."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.exceptions import (
    AuthenticationError,
    ContentRestrictedError,
    DeviceLimitError,
    GenerationError,
    MagnificError,
    PollingTimeoutError,
    RateLimitError,
    ValidationError,
)
from utils.logger import setup_logger

logger = setup_logger("error_handler")


def register_error_handlers(app: FastAPI):
    """Register exception handlers on the FastAPI app."""

    @app.exception_handler(MagnificError)
    async def magnific_error_handler(request: Request, exc: MagnificError):
        status_map = {
            AuthenticationError: 401,
            DeviceLimitError: 403,
            RateLimitError: 429,
            ContentRestrictedError: 455,
            ValidationError: 422,
            GenerationError: 500,
            PollingTimeoutError: 504,
        }

        status = status_map.get(type(exc), 500)
        logger.error(f"API error: {exc}")

        return JSONResponse(
            status_code=status,
            content={
                "success": False,
                "error": str(exc),
                "detail": exc.response_data if exc.response_data else None,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"},
        )
