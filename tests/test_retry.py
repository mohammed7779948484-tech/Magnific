"""Tests for utils/retry.py — retry_with_backoff decorator."""

from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import AuthenticationError, RateLimitError
from utils.retry import retry_with_backoff


class TestRetrySucceedsOnFirstTry:
    """Called Shot 1: If the function succeeds on first call, return result immediately."""

    def test_retry_succeeds_on_first_try(self):
        mock_fn = MagicMock(return_value="success")
        decorated = retry_with_backoff(mock_fn)

        result = decorated()

        assert result == "success"
        assert mock_fn.call_count == 1


class TestRetryOnRateLimitError:
    """Called Shot 2: If RateLimitError is raised, retry with exponential backoff."""

    def test_retry_on_rate_limit_error(self):
        mock_fn = MagicMock(
            side_effect=[RateLimitError("429"), "success"]
        )
        decorated = retry_with_backoff(mock_fn)

        result = decorated()

        assert result == "success"
        assert mock_fn.call_count == 2


class TestRetryExhaustsAllAttempts:
    """Called Shot 3: If all retries fail, raise the last exception."""

    def test_retry_exhausts_all_attempts(self):
        mock_fn = MagicMock(
            side_effect=RateLimitError("429")
        )
        decorated = retry_with_backoff(mock_fn, max_retries=3)

        with pytest.raises(RateLimitError):
            decorated()

        assert mock_fn.call_count == 3


class TestRetryOnlyCatchesRateLimit:
    """Called Shot 4: Other exceptions (like AuthenticationError) are NOT retried."""

    def test_retry_only_catches_rate_limit(self):
        mock_fn = MagicMock(
            side_effect=AuthenticationError("401")
        )
        decorated = retry_with_backoff(mock_fn)

        with pytest.raises(AuthenticationError):
            decorated()

        assert mock_fn.call_count == 1


class TestRetryBackoffDelaysIncrease:
    """Called Shot 5: Each retry waits longer (exponential backoff)."""

    @patch("utils.retry.time.sleep")
    def test_retry_backoff_delays_increase(self, mock_sleep):
        mock_fn = MagicMock(
            side_effect=[
                RateLimitError("429"),
                RateLimitError("429"),
                "success",
            ]
        )
        decorated = retry_with_backoff(mock_fn, max_retries=3, initial_delay=15.0)

        result = decorated()

        assert result == "success"
        assert mock_fn.call_count == 3

        # Verify exponential backoff: delay * (attempt + 1)
        # Attempt 0 fails → sleep(15.0 * 1) = 15.0
        # Attempt 1 fails → sleep(15.0 * 2) = 30.0
        # Attempt 2 succeeds → no sleep
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [15.0, 30.0]


class TestRetryWithCustomMaxRetries:
    """Called Shot 6: max_retries parameter controls number of attempts."""

    def test_retry_with_custom_max_retries(self):
        mock_fn = MagicMock(
            side_effect=RateLimitError("429")
        )
        decorated = retry_with_backoff(mock_fn, max_retries=2)

        with pytest.raises(RateLimitError):
            decorated()

        assert mock_fn.call_count == 2


class TestRetryWithCustomDelay:
    """Called Shot 7: Initial delay parameter controls backoff base."""

    @patch("utils.retry.time.sleep")
    def test_retry_with_custom_delay(self, mock_sleep):
        mock_fn = MagicMock(
            side_effect=[
                RateLimitError("429"),
                "success",
            ]
        )
        decorated = retry_with_backoff(mock_fn, max_retries=2, initial_delay=10.0)

        result = decorated()

        assert result == "success"

        # First attempt fails → sleep(10.0 * 1) = 10.0
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [10.0]


class TestRetryWithoutArguments:
    """Bonus: Verify @retry_with_backoff works without parentheses."""

    def test_retry_without_parentheses(self):
        @retry_with_backoff
        def my_func():
            return "hello"

        assert my_func() == "hello"
