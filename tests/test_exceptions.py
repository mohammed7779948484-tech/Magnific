"""Tests for core/exceptions.py — Custom exception hierarchy."""

import pytest

from core.exceptions import (
    MagnificError,
    AuthenticationError,
    DeviceLimitError,
    RateLimitError,
    ContentRestrictedError,
    ValidationError,
    PollingTimeoutError,
    GenerationError,
)


class TestMagnificErrorProperties:
    """Called Shot 1: MagnificError has status_code and response_data."""

    def test_magnific_error_properties(self):
        err = MagnificError("Something went wrong", status_code=500, response_data={"error": "internal"})
        assert err.status_code == 500
        assert err.response_data == {"error": "internal"}
        assert str(err.args[0]) == "Something went wrong"

    def test_magnific_error_defaults(self):
        err = MagnificError("Simple error")
        assert err.status_code is None
        assert err.response_data == {}


class TestExceptionHierarchy:
    """Called Shot 2: All exceptions inherit from MagnificError."""

    def test_exception_hierarchy(self):
        assert issubclass(AuthenticationError, MagnificError)
        assert issubclass(DeviceLimitError, MagnificError)
        assert issubclass(RateLimitError, MagnificError)
        assert issubclass(ContentRestrictedError, MagnificError)
        assert issubclass(ValidationError, MagnificError)
        assert issubclass(PollingTimeoutError, MagnificError)
        assert issubclass(GenerationError, MagnificError)

    def test_subclass_instances_are_magnific_error(self):
        err = AuthenticationError("Session expired", status_code=401)
        assert isinstance(err, MagnificError)
        assert isinstance(err, Exception)


class TestErrorStrFormat:
    """Called Shot 3: __str__ includes message, HTTP code, and detail."""

    def test_error_str_format(self):
        err = MagnificError("Bad request", status_code=400, response_data={"message": "Invalid input"})
        s = str(err)
        assert "Bad request" in s
        assert "HTTP 400" in s
        assert "Invalid input" in s

    def test_error_str_no_code(self):
        err = MagnificError("Generic error")
        s = str(err)
        assert s == "Generic error"

    def test_error_str_code_only(self):
        err = MagnificError("Error", status_code=404)
        s = str(err)
        assert "Error" in s
        assert "HTTP 404" in s

    def test_error_str_response_data_error_key(self):
        err = MagnificError("Error", status_code=403, response_data={"error": "Forbidden"})
        s = str(err)
        assert "Forbidden" in s
