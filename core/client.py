"""HTTP client with curl_cffi TLS fingerprint impersonation.

Handles all HTTP communication with the Magnific/Freepik API,
bypassing Cloudflare and Akamai bot management via Chrome TLS fingerprint.
"""

import time
from typing import Any

from curl_cffi.requests import Session

from config.endpoints import Endpoints
from config.user_agent import UserAgents
from core.exceptions import (
    AuthenticationError,
    ContentRestrictedError,
    DeviceLimitError,
    MagnificError,
    RateLimitError,
    ValidationError,
)
from utils.logger import setup_logger

logger = setup_logger("client")


def _prefix_path(path: str) -> str:
    """Auto-add API prefix to paths starting with /api/."""
    if path.startswith("/api/"):
        return Endpoints._p(path)
    return path


class MagnificClient:
    """HTTP client with Cloudflare/Akamai bypass via curl_cffi.

    Uses Chrome TLS/JA3 fingerprint impersonation to bypass
    Cloudflare's bot detection. Maintains a persistent session with
    all cookies automatically managed.
    """

    def __init__(self, cookies: dict[str, str] | None = None, base_url: str | None = None):
        """Initialize the HTTP client.

        Args:
            cookies: Optional dict of cookie name->value pairs to preload
            base_url: Override base URL (auto-detects API prefix)
        """
        if base_url:
            Endpoints.set_base_url(base_url)

        self.session = Session(impersonate=UserAgents.IMPERSONATE)
        self.session.headers.update({
            "User-Agent": UserAgents.DEFAULT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": Endpoints.BASE_URL,
            "Referer": f"{Endpoints.BASE_URL}/",
            "Sec-Ch-Ua": '"Chromium";v="136", "Not.A/Brand";v="99"',  # noqa: E501
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })

        if cookies:
            self.session.cookies.update(cookies)

        self._xsrf_token: str | None = None

    @property
    def xsrf_token(self) -> str | None:
        return self._xsrf_token

    @xsrf_token.setter
    def xsrf_token(self, value: str | None):
        self._xsrf_token = value

    def _common_headers(self) -> dict[str, str]:
        """Build common API request headers."""
        headers = {
            "X-Requested-With": "XMLHttpRequest",
        }
        if self._xsrf_token:
            headers["X-XSRF-TOKEN"] = self._xsrf_token
        return headers

    def get(self, path: str, **kwargs) -> dict[str, Any] | str | list:
        """Send GET request.

        Args:
            path: API path — auto-prefixed if starts with /api/
                  Examples: "/api/start-tti-v2", "/user/api/devices/identify"
            **kwargs: Additional arguments passed to session.get()

        Returns:
            Parsed JSON response

        Raises:
            MagnificError: On API errors
        """
        url = Endpoints.url(_prefix_path(path))
        headers = {**self._common_headers(), **kwargs.pop("headers", {})}

        logger.debug(f"GET {url}")
        response = self.session.get(url, headers=headers, **kwargs)

        return self._handle_response(response)

    def post(
        self,
        path: str,
        json_data: dict | None = None,
        data: Any = None,
        files: dict | None = None,
        **kwargs,
    ) -> dict[str, Any] | str | list:
        """Send POST request.

        Args:
            path: Relative API path (auto-prefixed if starts with /api/)
            json_data: JSON body (sets Content-Type: application/json)
            data: Form data or raw body
            files: Files for multipart upload
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response or raw text

        Raises:
            MagnificError: On API errors
        """
        url = Endpoints.url(_prefix_path(path))
        headers = {**self._common_headers(), **kwargs.pop("headers", {})}

        logger.debug(f"POST {url}")
        response = self.session.post(
            url,
            json=json_data,
            data=data,
            files=files,
            headers=headers,
            **kwargs,
        )

        return self._handle_response(response)

    def post_form(self, path: str, form_data: dict, files: dict | None = None, **kwargs) -> dict:
        """Send POST with multipart/form-data.

        Used for temporal-storage uploads. Does NOT set Content-Type
        (let curl_cffi handle the boundary automatically).

        Args:
            path: Relative API path (auto-prefixed if starts with /api/)
            form_data: Form fields
            files: Files to upload {"file": ("filename", bytes, "mime/type")}
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response
        """
        url = Endpoints.url(_prefix_path(path))
        headers = self._common_headers()
        # Do NOT set Content-Type for multipart — let the library handle boundary

        logger.debug(f"POST (form) {url}")
        response = self.session.post(url, data=form_data, files=files, headers=headers, **kwargs)

        return self._handle_response(response)

    def post_raw(self, path: str, body: bytes | str, content_type: str = "application/json", **kwargs) -> dict | str | list:
        """Send POST with raw body.

        Args:
            path: Relative API path (auto-prefixed if starts with /api/)
            body: Raw body content
            content_type: Content-Type header
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response or raw text
        """
        url = Endpoints.url(_prefix_path(path))
        headers = {
            **self._common_headers(),
            "Content-Type": content_type,
        }

        logger.debug(f"POST (raw) {url}")
        response = self.session.post(url, data=body, headers=headers, **kwargs)

        return self._handle_response(response)

    def download(self, url: str, output_path: str) -> str:
        """Download a file from URL.

        Args:
            url: Full URL to download from
            output_path: Local file path to save to

        Returns:
            Absolute path of saved file
        """
        logger.debug(f"Downloading: {url[:100]}...")
        headers = {
            "Referer": f"{Endpoints.BASE_URL}/",
            "User-Agent": UserAgents.DEFAULT,
        }
        response = self.session.get(url, headers=headers)

        if response.status_code != 200:
            raise MagnificError(f"Download failed: HTTP {response.status_code}", status_code=response.status_code)

        from utils.file_helpers import FileHelpers
        return FileHelpers.save_bytes(response.content, output_path)

    def _handle_response(self, response) -> dict[str, Any] | str | list:
        """Handle API response and raise appropriate errors.

        Args:
            response: curl_cffi response object

        Returns:
            Parsed JSON dict, list, or raw text string

        Raises:
            Various MagnificError subclasses based on status code
        """
        status = response.status_code

        # Success
        if status in (200, 204, 201):
            if status == 204:
                return {}
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    return response.json()
                except Exception:
                    return response.text
            return response.text

        # Parse error body
        try:
            error_data = response.json()
        except Exception:
            error_data = {"message": response.text[:500] if response.text else "Unknown error"}

        error_msg = error_data.get("message") or error_data.get("error") or str(error_data)[:200]

        # Map status codes to exception types
        if status == 401:
            raise AuthenticationError(f"Unauthorized: {error_msg}", status_code=status, response_data=error_data)
        elif status == 403:
            if "device" in error_msg.lower():
                raise DeviceLimitError(f"Device limit: {error_msg}", status_code=status, response_data=error_data)
            raise MagnificError(f"Forbidden: {error_msg}", status_code=status, response_data=error_data)
        elif status == 419:
            raise AuthenticationError(f"Session expired (CSRF): {error_msg}", status_code=status, response_data=error_data)
        elif status == 422:
            raise ValidationError(f"Validation error: {error_msg}", status_code=status, response_data=error_data)
        elif status == 429:
            raise RateLimitError(f"Rate limited: {error_msg}", status_code=status, response_data=error_data)
        elif status in (455, 456):
            raise ContentRestrictedError(f"Content restricted: {error_msg}", status_code=status, response_data=error_data)
        elif status >= 500:
            raise MagnificError(f"Server error: {error_msg}", status_code=status, response_data=error_data)
        else:
            raise MagnificError(f"HTTP {status}: {error_msg}", status_code=status, response_data=error_data)

    def close(self):
        """Close the underlying session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
