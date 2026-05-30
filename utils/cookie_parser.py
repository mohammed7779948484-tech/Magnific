"""Parse cookies from Netscape format and JSON session files."""

import json
import os
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any

from .logger import setup_logger

logger = setup_logger("cookie_parser")

# Cookies that must be fresh — skip stale ones to avoid 403 conflicts
SKIP_COOKIES = {
    "ak_bmsc",          # Akamai bot management — session-bound
    "_ga",              # Google Analytics
    "_gid",             # Google Analytics
    "_gat",             # Google Analytics
    "intercom-id",      # Intercom
    "intercom-session",
    "posthog",
    "ph_",              # PostHog analytics
}


class CookieParser:
    """Parse and load cookies from various formats.

    Supported formats:
        - Netscape cookie file (txt) — like Cookie-Editor export
        - JSON session file — array of cookie objects
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Cookies file not found: {file_path}")

    def parse(self) -> list[dict[str, Any]]:
        """Auto-detect format and parse cookies.

        Returns:
            List of cookie dicts with keys: name, value, domain, path, httpOnly, secure
        """
        content = self.file_path.read_text(encoding="utf-8")

        # Try JSON first
        stripped = content.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            return self._parse_json(stripped)

        # Default: Netscape format
        return self._parse_netscape(content)

    def _parse_json(self, content: str) -> list[dict[str, Any]]:
        """Parse JSON-format cookies."""
        data = json.loads(content)

        # Handle both array and single-object formats
        if isinstance(data, dict):
            data = [data]

        cookies = []
        for c in data:
            name = c.get("name", "")
            if name in SKIP_COOKIES:
                logger.debug(f"Skipping stale cookie: {name}")
                continue

            cookies.append({
                "name": name,
                "value": str(c.get("value", "")),
                "domain": c.get("domain", ".freepik.com"),
                "path": c.get("path", "/"),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", True),
            })

        logger.info(f"Parsed {len(cookies)} cookies from JSON file")
        return cookies

    def _parse_netscape(self, content: str) -> list[dict[str, Any]]:
        """Parse Netscape cookie file format (tab or space separated).

        Format: domain  flag  path  secure  expiration  name  value
        """
        # Handle CRLF line endings (common with Windows Cookie-Editor export)
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        cookies = []
        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Handle #HttpOnly_ prefix (Netscape format for HttpOnly cookies)
            # e.g. "#HttpOnly_.magnific.com TRUE / TRUE 1780156063 GR_TOKEN ..."
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]  # strip prefix, rest is normal cookie
            elif line.startswith("#"):
                # Regular comment line — skip
                continue

            parts = line.split("\t") if "\t" in line else line.split()

            # Netscape format has at least 7 fields
            if len(parts) < 7:
                logger.debug(f"Skipping malformed line {line_num}: {line[:60]}")
                continue

            name = parts[5].strip()
            if name in SKIP_COOKIES:
                logger.debug(f"Skipping stale cookie: {name}")
                continue

            cookies.append({
                "name": name,
                "value": parts[6].strip(),
                "domain": parts[0].strip(),
                "path": parts[2].strip(),
                "httpOnly": bool(int(parts[1].strip()) if parts[1].strip().isdigit() else 0),
                "secure": parts[3].strip().upper() in ("TRUE", "YES", "1"),
            })

        logger.info(f"Parsed {len(cookies)} cookies from Netscape file")
        return cookies

    def to_curl_cffi_dict(self) -> dict[str, str]:
        """Parse cookies into a simple name->value dict for curl_cffi.

        Returns:
            Dict mapping cookie name to value
        """
        cookies = self.parse()
        return {c["name"]: c["value"] for c in cookies}
