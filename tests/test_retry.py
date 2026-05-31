"""Tests for utils/retry.py — retry_with_backoff decorator.

NO MOCKS. Uses real functions with side_effect tracking via closures,
and real short sleeps (0.001s) instead of patching time.sleep.
"""

import time

import pytest

from core.exceptions import AuthenticationError, RateLimitError
from utils.retry import retry_with_backoff


# ── Helper: creates a real function that tracks calls and yields side effects ──

def _make_fn(results, call_log):
    """Create a real callable that returns items from results in order.

    Args:
        results: List of values to return or Exception instances to raise.
            If the list has exactly one Exception, it raises forever (sticky).
        call_log: A mutable list to record each call (caller appends).

    Returns:
        A plain function object — not a mock.
    """
    def _fn():
        call_log.append(None)
        if not results:
            raise RuntimeError("_make_fn results exhausted — unexpected call")
        item = results[0]
        if isinstance(item, Exception):
            # Always-raise mode: single item stays, raise every time
            if len(results) == 1:
                raise item
            # Multi-item: consume and raise
            results.pop(0)
            raise item
        results.pop(0)
        return item
    return _fn


class TestRetrySucceedsOnFirstTry:
    """Called Shot 1: If the function succeeds on first call, return result immediately."""

    def test_retry_succeeds_on_first_try(self):
        call_log: list = []
        fn = _make_fn(["success"], call_log)
        decorated = retry_with_backoff(fn)

        result = decorated()

        assert result == "success"
        assert len(call_log) == 1


class TestRetryOnRateLimitError:
    """Called Shot 2: If RateLimitError is raised, retry with exponential backoff."""

    def test_retry_on_rate_limit_error(self):
        call_log: list = []
        fn = _make_fn([RateLimitError("429"), "success"], call_log)
        decorated = retry_with_backoff(fn)

        result = decorated()

        assert result == "success"
        assert len(call_log) == 2


class TestRetryExhaustsAllAttempts:
    """Called Shot 3: If all retries fail, raise the last exception."""

    def test_retry_exhausts_all_attempts(self):
        call_log: list = []
        fn = _make_fn([RateLimitError("429")], call_log)
        # Use short delay so test doesn't take 90 seconds
        decorated = retry_with_backoff(fn, max_retries=3, initial_delay=0.001)

        with pytest.raises(RateLimitError):
            decorated()

        assert len(call_log) == 3


class TestRetryOnlyCatchesRateLimit:
    """Called Shot 4: Other exceptions (like AuthenticationError) are NOT retried."""

    def test_retry_only_catches_rate_limit(self):
        call_log: list = []
        fn = _make_fn([AuthenticationError("401")], call_log)
        decorated = retry_with_backoff(fn)

        with pytest.raises(AuthenticationError):
            decorated()

        assert len(call_log) == 1


class TestRetryBackoffDelaysIncrease:
    """Called Shot 5: Each retry waits longer (exponential backoff).

    Uses real sleep with 0.001s initial_delay so the test runs fast but
    verifies the actual sleep mechanism works.
    """

    def test_retry_backoff_delays_increase(self):
        call_log: list = []
        fn = _make_fn(
            [RateLimitError("429"), RateLimitError("429"), "success"],
            call_log,
        )
        decorated = retry_with_backoff(fn, max_retries=3, initial_delay=0.001)

        start = time.monotonic()
        result = decorated()
        elapsed = time.monotonic() - start

        assert result == "success"
        assert len(call_log) == 3

        # Verify exponential backoff timing:
        # Attempt 0 fails → sleep(0.001 * 1) = 0.001
        # Attempt 1 fails → sleep(0.001 * 2) = 0.002
        # Attempt 2 succeeds → no sleep
        # Total sleep ≈ 0.003s. Allow generous tolerance for CI jitter.
        expected_min = 0.0015  # at least some sleep happened
        assert elapsed >= expected_min, (
            f"Expected ~0.003s of sleep, got {elapsed:.4f}s — backoff not working"
        )


class TestRetryWithCustomMaxRetries:
    """Called Shot 6: max_retries parameter controls number of attempts."""

    def test_retry_with_custom_max_retries(self):
        call_log: list = []
        fn = _make_fn([RateLimitError("429")], call_log)
        # Use short delay so test doesn't take 30 seconds
        decorated = retry_with_backoff(fn, max_retries=2, initial_delay=0.001)

        with pytest.raises(RateLimitError):
            decorated()

        assert len(call_log) == 2


class TestRetryWithCustomDelay:
    """Called Shot 7: Initial delay parameter controls backoff base.

    Uses real sleep with 0.001s initial_delay.
    """

    def test_retry_with_custom_delay(self):
        call_log: list = []
        fn = _make_fn([RateLimitError("429"), "success"], call_log)
        decorated = retry_with_backoff(fn, max_retries=2, initial_delay=0.001)

        start = time.monotonic()
        result = decorated()
        elapsed = time.monotonic() - start

        assert result == "success"
        # First attempt fails → sleep(0.001 * 1) = 0.001s
        assert elapsed >= 0.0005, (
            f"Expected ~0.001s of sleep, got {elapsed:.4f}s"
        )


class TestRetryWithoutArguments:
    """Bonus: Verify @retry_with_backoff works without parentheses."""

    def test_retry_without_parentheses(self):
        @retry_with_backoff
        def my_func():
            return "hello"

        assert my_func() == "hello"
