"""Retry utility with exponential backoff for rate limiting."""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from core.exceptions import RateLimitError
from utils.logger import setup_logger

logger = setup_logger("retry")

F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    func: F | None = None,
    *,
    max_retries: int = 5,
    initial_delay: float = 15.0,
    exceptions: tuple[type[Exception], ...] = (RateLimitError,),
) -> F:
    """Decorator for retrying a function with exponential backoff.

    Can be used as @retry_with_backoff or @retry_with_backoff(max_retries=3).

    Args:
        func: The function to decorate (when used without parentheses).
        max_retries: Maximum number of attempts (default: 5).
        initial_delay: Base delay in seconds; actual wait is initial_delay * (attempt + 1).
        exceptions: Tuple of exception types to catch and retry on.
    """
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        wait = initial_delay * (attempt + 1)
                        logger.warning(
                            f"Rate limited, waiting {wait:.0f}s before retry "
                            f"({attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait)
                    else:
                        raise
            raise last_exc  # Should not reach here, but safety net
        return wrapper  # type: ignore

    if func is not None:
        return decorator(func)
    return decorator  # type: ignore
