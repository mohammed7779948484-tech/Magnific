"""Authentication and security bypass module.

Handles XSRF token refresh, device identification, and session management.
"""

from urllib.parse import unquote

from config.endpoints import Endpoints
from core.client import MagnificClient
from core.exceptions import AuthenticationError, DeviceLimitError
from utils.logger import setup_logger

logger = setup_logger("auth")


class Authenticator:
    """Manages authentication flow: XSRF refresh + device identify.

    Flow:
        1. GET {prefix}/sanctum/csrf-cookie → Sets fresh XSRF-TOKEN cookie
        2. POST /user/api/devices/identify → Registers device
    """

    def __init__(self, client: MagnificClient):
        self.client = client

    def refresh_xsrf(self) -> str:
        """Refresh the XSRF-TOKEN via CSRF cookie endpoint.

        Makes a GET request to the CSRF endpoint. The server sets a new
        XSRF-TOKEN cookie in the response. We then read it from the session
        cookies and decode it.

        Returns:
            Decoded XSRF token value

        Raises:
            AuthenticationError: If refresh fails
        """
        logger.info("Refreshing XSRF-TOKEN...")

        # Delete old XSRF token if present
        if "XSRF-TOKEN" in self.client.session.cookies:
            del self.client.session.cookies["XSRF-TOKEN"]

        # GET csrf-cookie — server sets new XSRF-TOKEN cookie
        self.client.get(Endpoints.csrf_cookie())

        # Read the new token from session cookies
        raw_xsrf = self.client.session.cookies.get("XSRF-TOKEN")
        if not raw_xsrf:
            raise AuthenticationError("Failed to refresh XSRF-TOKEN: no cookie received")

        # Decode URI-encoded value
        decoded_xsrf = unquote(raw_xsrf)

        # Store in client for use in headers
        self.client.xsrf_token = decoded_xsrf

        logger.info(f"XSRF-TOKEN refreshed successfully ({len(decoded_xsrf)} chars)")
        return decoded_xsrf

    def identify_device(self) -> dict:
        """Register device with the Freepik API.

        Required before any generation requests. Without device identification,
        API calls return 403 Forbidden.

        Returns:
            Response dict with {"success": true, "disabled": false}

        Raises:
            DeviceLimitError: If too many devices are registered
            AuthenticationError: If device identification fails
        """
        logger.info("Registering device...")

        result = self.client.post(
            Endpoints.DEVICE_IDENTIFY,
            json_data={},
        )

        if result.get("success"):
            logger.info("Device registered successfully")
        elif result.get("disabled"):
            logger.warning("Device registered but disabled — may have limits")
        else:
            logger.warning(f"Device registration returned: {result}")

        return result

    def authenticate(self) -> str:
        """Run the full authentication flow.

        Performs both XSRF refresh and device identification in sequence.

        Returns:
            The decoded XSRF token
        """
        xsrf = self.refresh_xsrf()
        self.identify_device()
        return xsrf

    def is_authenticated(self) -> bool:
        """Check if the session has a valid XSRF token.

        Returns:
            True if XSRF token is present
        """
        return self.client.xsrf_token is not None and len(self.client.xsrf_token) > 0
