"""Rate limiting middleware for the local API."""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from utils.logger import setup_logger

logger = setup_logger("rate_limiter")

# Default rate limits
DEFAULT_RATE_LIMIT = 10  # requests per minute
DEFAULT_RATE_WINDOW = 60  # seconds


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = DEFAULT_RATE_LIMIT, window: int = DEFAULT_RATE_WINDOW):
        self.max_requests = max_requests
        self.window = window
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed under rate limits.

        Args:
            key: Identifier (e.g. client IP)

        Returns:
            True if request is within limits
        """
        now = time.time()
        cutoff = now - self.window

        # Clean old entries
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

    def reset(self, key: str | None = None):
        """Reset rate limit for a key or all keys."""
        if key:
            self.requests.pop(key, None)
        else:
            self.requests.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for rate limiting."""

    def __init__(self, app, max_requests: int = DEFAULT_RATE_LIMIT):
        super().__init__(app)
        self.limiter = RateLimiter(max_requests=max_requests)
        # Exempt paths from rate limiting
        self.exempt_paths = {"/api/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Use client IP as key
        client_ip = request.client.host if request.client else "unknown"

        if not self.limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Rate limit exceeded",
                    "detail": f"Max {self.limiter.max_requests} requests per {self.limiter.window}s",
                },
            )

        return await call_next(request)
