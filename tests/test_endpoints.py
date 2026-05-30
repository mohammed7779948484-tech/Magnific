"""Tests for config/endpoints.py — Endpoints class."""

import threading
import time

import pytest

from config.endpoints import Endpoints


@pytest.fixture(autouse=True)
def reset_endpoints():
    """Reset Endpoints class variables before each test."""
    Endpoints.BASE_URL = "https://www.magnific.com"
    Endpoints.API_PREFIX = "/app"
    yield
    Endpoints.BASE_URL = "https://www.magnific.com"
    Endpoints.API_PREFIX = "/app"


class TestDefaultBaseUrlAndPrefix:
    """Called Shot 1: Default is magnific.com with /app prefix."""

    def test_default_base_url_and_prefix(self):
        assert Endpoints.BASE_URL == "https://www.magnific.com"
        assert Endpoints.API_PREFIX == "/app"


class TestSetBaseUrlFreepik:
    """Called Shot 2: Setting freepik.com changes prefix to /pikaso."""

    def test_set_base_url_freepik(self):
        Endpoints.set_base_url("https://www.freepik.com")
        assert Endpoints.BASE_URL == "https://www.freepik.com"
        assert Endpoints.API_PREFIX == "/pikaso"


class TestUrlBuilding:
    """Called Shot 3: url() combines BASE_URL + path correctly."""

    def test_url_building(self):
        full = Endpoints.url("/api/ai-models")
        assert full == "https://www.magnific.com/api/ai-models"

        full2 = Endpoints.url("/sanctum/csrf-cookie")
        assert full2 == "https://www.magnific.com/sanctum/csrf-cookie"


class TestPrefixPath:
    """Called Shot 4: _p() adds API prefix to paths starting with /api/."""

    def test_prefix_path(self):
        result = Endpoints._p("/api/ai-models")
        assert result == "/app/api/ai-models"

        result2 = Endpoints._p("/sanctum/csrf-cookie")
        assert result2 == "/app/sanctum/csrf-cookie"

    def test_creation_detail_uses_prefix(self):
        result = Endpoints.creation_detail("abc-123")
        assert result == "/app/api/creation/abc-123"


class TestEndpointsResetRestoresDefaults:
    """Called Shot: reset() restores default BASE_URL and API_PREFIX."""

    def test_endpoints_reset_restores_defaults(self):
        Endpoints.set_base_url("https://freepik.com")
        assert Endpoints.BASE_URL == "https://freepik.com"
        assert Endpoints.API_PREFIX == "/pikaso"

        Endpoints.reset()
        assert Endpoints.BASE_URL == "https://www.magnific.com"
        assert Endpoints.API_PREFIX == "/app"


class TestConcurrentSetBaseUrlSafe:
    """Called Shot: Multiple threads calling set_base_url don't corrupt state."""

    def test_concurrent_set_base_url_safe(self):
        """Concurrent set_base_url calls must not produce mixed state.

        Either BASE_URL/API_PREFIX are magnific values or freepik values,
        never a mix like magnific URL + /pikaso prefix.
        """
        magnific_url = "https://www.magnific.com"
        freepik_url = "https://www.freepik.com"
        num_threads = 20
        iterations_per_thread = 50

        barrier = threading.Barrier(num_threads)
        errors = []

        def set_url(url):
            barrier.wait()
            for _ in range(iterations_per_thread):
                Endpoints.set_base_url(url)

        threads = [
            threading.Thread(target=set_url, args=(magnific_url,))
            for _ in range(num_threads // 2)
        ] + [
            threading.Thread(target=set_url, args=(freepik_url,))
            for _ in range(num_threads // 2)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all threads finish, state must be consistent
        assert (Endpoints.BASE_URL, Endpoints.API_PREFIX) in [
            (magnific_url, "/app"),
            (freepik_url, "/pikaso"),
        ], (
            f"Corrupted state: BASE_URL={Endpoints.BASE_URL!r}, "
            f"API_PREFIX={Endpoints.API_PREFIX!r}"
        )
