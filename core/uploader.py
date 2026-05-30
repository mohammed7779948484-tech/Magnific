"""Upload engines for reference images, videos, and audio.

Supports three upload methods:
    1. temporal-storage — FormData upload (for start-tti-v2 references)
    2. upload-frame — Base64 JSON upload (for video frame references)
    3. CDN URL passthrough — Direct URL usage (no upload needed)
"""

import base64
import io
from typing import Any

from config.endpoints import Endpoints
from core.client import MagnificClient
from utils.file_helpers import FileHelpers
from utils.logger import setup_logger

logger = setup_logger("uploader")


class Uploader:
    """Handles all file upload operations for the Magnific API."""

    def __init__(self, client: MagnificClient):
        self.client = client

    def upload_temporal(self, file_path: str | None = None, base64_data: str | None = None, filename: str = "reference.jpg") -> dict:
        """Upload a file to temporal storage via FormData.

        Used for image generation references in start-tti-v2.
        The returned path is used as 'temporal:' format in start-tti-v2.

        Args:
            file_path: Path to local file (alternative to base64_data)
            base64_data: Base64 data URI (alternative to file_path)
            filename: Filename for the upload

        Returns:
            Dict with 'path' key (e.g. "temp-files/xxxxx.jpg")
        """
        if base64_data:
            raw_bytes = FileHelpers.base64_to_bytes(base64_data)
        elif file_path:
            raw_bytes = FileHelpers.base64_to_bytes(FileHelpers.file_to_base64(file_path))
        else:
            raise ValueError("Either file_path or base64_data must be provided")

        # Build multipart form data
        file_obj = io.BytesIO(raw_bytes)

        # Detect MIME type from filename
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".webp": "image/webp",
            ".mp4": "video/mp4", ".webm": "video/webm",
            ".mp3": "audio/mpeg", ".wav": "audio/wav",
        }
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        mime = mime_map.get(f".{ext}", "application/octet-stream")

        files = {"file": (filename, file_obj, mime)}

        logger.info(f"Uploading to temporal storage: {filename} ({len(raw_bytes):,} bytes)")

        result = self.client.post_form(
            "/api/temporal-storage",
            form_data={},
            files=files,
        )

        path = result.get("path", "")
        logger.info(f"Temporal upload successful: {path}")
        return result

    def upload_frame(
        self,
        image_base64: str | None = None,
        file_path: str | None = None,
        frame_type: str = "frame",
    ) -> dict:
        """Upload a frame image via upload-frame endpoint (base64 JSON).

        Used for video reference images. Returns a URL that can be used
        directly in video generation references.

        Args:
            image_base64: Base64 data URI of the image
            file_path: Path to local file (alternative to image_base64)
            frame_type: One of "start", "end", "frame", "sketch"

        Returns:
            Dict with 'startFrameUrl', 'endFrameUrl', or 'frameUrl'
        """
        # Get base64 data
        if image_base64:
            b64_uri = image_base64
        elif file_path:
            b64_uri = FileHelpers.file_to_base64(file_path)
        else:
            raise ValueError("Either image_base64 or file_path must be provided")

        # Build body based on frame type
        body: dict[str, Any] = {
            "startFrameImageBase64": None,
            "endFrameImageBase64": None,
            "frameImageBase64": None,
            "sketchImageBase64": None,
        }

        key_map = {
            "start": "startFrameImageBase64",
            "end": "endFrameImageBase64",
            "frame": "frameImageBase64",
            "sketch": "sketchImageBase64",
        }
        body[key_map[frame_type]] = b64_uri

        logger.info(f"Uploading frame ({frame_type}): {len(b64_uri):,} chars")

        result = self.client.post(
            "/api/video/generate/upload-frame",
            json_data=body,
        )

        logger.info(f"Frame upload successful: {list(result.keys())}")
        return result

    def upload_start_frame(self, image_base64: str | None = None, file_path: str | None = None) -> str:
        """Upload a start frame and return its URL.

        Args:
            image_base64: Base64 data URI
            file_path: Path to local file

        Returns:
            URL string for the uploaded start frame
        """
        result = self.upload_frame(image_base64=image_base64, file_path=file_path, frame_type="start")
        return result.get("startFrameUrl", "")

    def upload_end_frame(self, image_base64: str | None = None, file_path: str | None = None) -> str:
        """Upload an end frame and return its URL.

        Args:
            image_base64: Base64 data URI
            file_path: Path to local file

        Returns:
            URL string for the uploaded end frame
        """
        result = self.upload_frame(image_base64=image_base64, file_path=file_path, frame_type="end")
        return result.get("endFrameUrl", "")

    def upload_reference_frame(self, image_base64: str | None = None, file_path: str | None = None) -> str:
        """Upload a reference frame for video generation.

        Args:
            image_base64: Base64 data URI
            file_path: Path to local file

        Returns:
            URL string (frameUrl) for the uploaded reference
        """
        result = self.upload_frame(image_base64=image_base64, file_path=file_path, frame_type="frame")
        return result.get("frameUrl", "")

    def upload_video_audio(self, file_path: str) -> dict:
        """Upload a video or audio file via temporal storage.

        Args:
            file_path: Path to video/audio file

        Returns:
            Dict with 'path' or 'url' key
        """
        from pathlib import Path
        filename = Path(file_path).name
        return self.upload_temporal(file_path=file_path, filename=filename)

    @staticmethod
    def prepare_image_reference(
        label: str,
        base64_data: str | None = None,
        file_path: str | None = None,
        ref_type: str = "reference",
        category: str = "product",
    ) -> dict:
        """Prepare an image reference dict for render/v4.

        IMPORTANT: render/v4 requires base64 + id + label format.
        temporal: paths are BLOCKED by Cloudflare WAF (returns 500).
        URLs are REJECTED by API validation (returns 422).

        Args:
            label: Reference label (used as @label in prompt, must match id)
            base64_data: Base64 data URI of the image
            file_path: Path to local file (alternative to base64_data)
            ref_type: "reference" or "style"
            category: "character", "product", "image", "composition", "style"

        Returns:
            Dict ready for render/v4 image_references array
        """
        if base64_data:
            b64_uri = base64_data
        elif file_path:
            b64_uri = FileHelpers.file_to_base64(file_path)
        else:
            raise ValueError("Either base64_data or file_path must be provided")

        return {
            "id": label,
            "label": label,
            "image": b64_uri,
            "type": ref_type,
            "category": category,
            "frame": None,
        }

    @staticmethod
    def build_video_reference(ref_type: str, url: str, name: str) -> dict:
        """Build a video generation reference dict.

        Video references use URLs (not base64) — opposite of image references.

        Args:
            ref_type: "image", "video", or "audio"
            url: URL of the reference (CDN, upload-frame, or temporal)
            name: Reference name (used as @name in prompt)

        Returns:
            Dict for video generation references array
        """
        return {
            "type": ref_type,
            "url": url,
            "name": name,
        }
