"""Custom exceptions for the Magnific API client."""


class MagnificError(Exception):
    """Base exception for all Magnific API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None):
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        if self.response_data:
            msg = self.response_data.get("message") or self.response_data.get("error")
            if msg:
                parts.append(f": {msg}")
        return " ".join(parts)


class AuthenticationError(MagnificError):
    """Session expired or authentication failure (401, 419)."""

    pass


class DeviceLimitError(MagnificError):
    """Too many devices registered (403 with device limit message)."""

    pass


class RateLimitError(MagnificError):
    """Rate limit exceeded (429)."""

    pass


class ContentRestrictedError(MagnificError):
    """Content blocked by safety filters (455, 456)."""

    pass


class ValidationError(MagnificError):
    """Invalid parameters (422)."""

    pass


class PollingTimeoutError(MagnificError):
    """Generation did not complete within timeout period."""

    pass


class GenerationError(MagnificError):
    """Generation failed during processing."""

    pass
