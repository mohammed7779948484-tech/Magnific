"""File handling utilities — base64, chunks, downloads."""

import base64
import os
import re
from pathlib import Path
from typing import BinaryIO

from .logger import setup_logger

logger = setup_logger("file_helpers")

# Maximum size for single base64 upload (before using chunked)
MAX_INLINE_BASE64_BYTES = 1 * 1024 * 1024  # 1MB


class FileHelpers:
    """Utility methods for file operations."""

    @staticmethod
    def file_to_base64(file_path: str | Path) -> str:
        """Convert a file to a base64 data URI.

        Args:
            file_path: Path to the file

        Returns:
            Base64 data URI string (e.g. "data:image/jpeg;base64,...")
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
            ".mp4": "video/mp4", ".webm": "video/webm",
            ".mp3": "audio/mpeg", ".wav": "audio/wav",
            ".ogg": "audio/ogg",
        }

        ext = file_path.suffix.lower()
        mime = mime_map.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime};base64,{b64_data}"

    @staticmethod
    def base64_to_bytes(data_uri: str) -> bytes:
        """Extract raw bytes from a base64 data URI.

        Args:
            data_uri: Data URI string (e.g. "data:image/jpeg;base64,...")

        Returns:
            Raw bytes
        """
        match = re.match(r"data:[^;]+;base64,(.+)", data_uri)
        if not match:
            raise ValueError("Invalid base64 data URI format")

        return base64.b64decode(match.group(1))

    @staticmethod
    def save_bytes(data: bytes, output_path: str | Path) -> str:
        """Save bytes to a file and return the absolute path.

        Args:
            data: Raw bytes to save
            output_path: Output file path

        Returns:
            Absolute path of saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(data)

        abs_path = str(output_path.resolve())
        logger.info(f"Saved file: {abs_path} ({len(data):,} bytes)")
        return abs_path

    @staticmethod
    def parse_reference_input(ref_str: str) -> dict:
        """Parse a reference input string like 'file.jpg|label' or 'https://...|label'.

        Args:
            ref_str: Reference string in format "source|name"

        Returns:
            Dict with 'source' and 'name' keys
        """
        if "|" in ref_str:
            source, name = ref_str.rsplit("|", 1)
            return {"source": source.strip(), "name": name.strip()}
        return {"source": ref_str.strip(), "name": None}

    @staticmethod
    def is_url(s: str) -> bool:
        """Check if a string is a URL."""
        return s.startswith("http://") or s.startswith("https://")

    @staticmethod
    def is_base64_data_uri(s: str) -> bool:
        """Check if a string is a base64 data URI."""
        return s.startswith("data:")
