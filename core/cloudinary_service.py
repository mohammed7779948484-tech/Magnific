"""Cloudinary cloud storage service for generated assets.

Handles uploading, downloading, listing, and deleting images/videos
stored in Cloudinary cloud. Automatically called after generation to
persist results, and used for reference reuse to avoid re-uploading.
"""

from __future__ import annotations

import io
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from utils.logger import setup_logger

logger = setup_logger("cloudinary")

# Thread-safe Cloudinary configuration lock
_config_lock = threading.Lock()
_configured = False


class CloudinaryError(Exception):
    """Raised when Cloudinary operations fail."""

    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(message)


# Exceptions that are transient and worth retrying
_RETRYABLE_EXCEPTIONS = (ConnectionError, OSError, TimeoutError)


class CloudinaryService:
    """Manages cloud storage of generated assets via Cloudinary.

    Features:
        - Upload images/videos from URL or bytes
        - Download assets from Cloudinary as bytes
        - List assets with pagination and filtering
        - Delete assets by public_id
        - Auto-generate public_ids with type/model/creation structure
        - Reference reuse: resolve Cloudinary URLs to base64/bytes

    Usage:
        svc = CloudinaryService(cloud_name="my-cloud", api_key="xxx", api_secret="yyy")
        result = svc.upload_from_url("https://cdn.magnific.com/image.png",
                                     public_id="image/flux-2/abc123")
        # result = {"url": "https://res.cloudinary.com/.../image.png", "public_id": "..."}

    Thread-safe: All operations are protected by internal locks.
    """

    def __init__(
        self,
        cloud_name: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        folder: str = "magnific",
        enabled: bool = True,
    ):
        """Initialize Cloudinary service.

        Args:
            cloud_name: Cloudinary cloud name
            api_key: Cloudinary API key
            api_secret: Cloudinary API secret
            folder: Root folder for uploads (default: "magnific")
            enabled: Whether cloud storage is active (default: True)
        """
        self.folder = folder
        self.enabled = enabled
        self._upload_lock = threading.Lock()

        if not enabled:
            logger.info("Cloudinary service created but DISABLED")
            return

        if not all([cloud_name, api_key, api_secret]):
            logger.warning("Cloudinary credentials incomplete — service DISABLED")
            self.enabled = False
            return

        try:
            import cloudinary
            import cloudinary.api
            import cloudinary.uploader

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True,
            )

            # Test configuration
            cloudinary.api.ping()
            logger.info(f"Cloudinary connected — cloud: {cloud_name}, folder: {folder}")
        except Exception as e:
            logger.error(f"Cloudinary connection failed: {e}")
            self.enabled = False
            raise CloudinaryError(f"Failed to connect to Cloudinary: {e}", e)

    def is_enabled(self) -> bool:
        """Check if Cloudinary service is active and configured."""
        return self.enabled

    @staticmethod
    def _call_with_retry(
        func: Callable[[], Any],
        max_retries: int = 3,
        description: str = "operation",
    ) -> Any:
        """Execute a callable with exponential backoff retry for transient errors.

        Retries on network/transient errors (ConnectionError, OSError, TimeoutError).
        Does NOT retry on permanent errors (ValueError, RuntimeError, TypeError).

        Args:
            func: Zero-argument callable to execute
            max_retries: Maximum number of attempts (default: 3)
            description: Human-readable description for logging

        Returns:
            The return value of func on success

        Raises:
            CloudinaryError: If all retries are exhausted or permanent error occurs
        """
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                return func()
            except (ValueError, RuntimeError, TypeError, KeyError) as e:
                # Permanent errors — do not retry
                logger.warning(f"Cloudinary {description} failed (permanent): {e}")
                raise CloudinaryError(f"{description} failed: {e}", e)
            except _RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s, 4s...
                    logger.warning(
                        f"Cloudinary {description} failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Cloudinary {description} failed after {max_retries} attempts: {e}"
                    )
            except Exception as e:
                # Other exceptions — treat as permanent
                logger.warning(f"Cloudinary {description} failed (unexpected): {e}")
                raise CloudinaryError(f"{description} failed: {e}", e)

        raise CloudinaryError(
            f"{description} failed after {max_retries} retries: {last_error}",
            last_error,
        )

    def build_public_id(
        self,
        asset_type: str,
        model_slug: str,
        creation_id: str,
        index: int = 0,
    ) -> str:
        """Build a structured public_id for an asset.

        Format: {folder}/{type}/{model}/{creation_id}_{index}
        Example: magnific/image/flux-2/abc123_0

        Args:
            asset_type: "image" or "video"
            model_slug: Model identifier (e.g. "flux-2", "seedance-2-pro")
            creation_id: Magnific creation ID
            index: Index for multiple outputs (default: 0)

        Returns:
            Structured public_id string
        """
        return f"{self.folder}/{asset_type}/{model_slug}/{creation_id}_{index}"

    def upload_from_url(
        self,
        url: str,
        public_id: str,
        resource_type: str = "auto",
        tags: list[str] | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload a file from a URL to Cloudinary.

        Downloads from the source URL and uploads to Cloudinary.
        Automatically detects resource type (image/video) if "auto".

        Args:
            url: Source URL to download from (e.g. Magnific CDN URL)
            public_id: Cloudinary public_id for the asset
            resource_type: "image", "video", or "auto" (default: "auto")
            tags: Optional list of tags to assign to the asset
            context: Optional key-value context metadata

        Returns:
            Dict with "url", "secure_url", "public_id", "resource_type",
                  "bytes", "width", "height" (for images), "duration" (for videos)

        Raises:
            CloudinaryError: If upload fails
        """
        if not self.enabled:
            return {}

        import cloudinary.uploader

        with self._upload_lock:
            try:
                logger.info(f"Uploading to Cloudinary from URL: {url[:80]}...")

                def _do_upload():
                    upload_opts: dict[str, Any] = {
                        "public_id": public_id,
                        "resource_type": resource_type,
                        "overwrite": True,
                        "use_filename": False,
                        "unique_filename": False,
                    }
                    if tags:
                        upload_opts["tags"] = tags
                    if context:
                        upload_opts["context"] = context
                    return cloudinary.uploader.upload(url, **upload_opts)

                result = self._call_with_retry(_do_upload, max_retries=3, description=f"upload from URL ({public_id})")

                cloudinary_url = result.get("secure_url", result.get("url", ""))
                logger.info(
                    f"Cloudinary upload successful: {public_id} "
                    f"({result.get('bytes', 0):,} bytes, type: {result.get('resource_type', '?')})"
                )

                return {
                    "url": cloudinary_url,
                    "public_id": result.get("public_id", public_id),
                    "resource_type": result.get("resource_type", resource_type),
                    "bytes": result.get("bytes", 0),
                    "format": result.get("format", ""),
                    "width": result.get("width"),
                    "height": result.get("height"),
                    "duration": result.get("duration"),
                    "created_at": result.get("created_at", ""),
                }
            except CloudinaryError:
                raise
            except Exception as e:
                logger.error(f"Cloudinary upload failed: {e}")
                raise CloudinaryError(f"Upload failed for {public_id}: {e}", e)

    def upload_from_bytes(
        self,
        data: bytes,
        public_id: str,
        resource_type: str = "auto",
        filename: str = "asset",
    ) -> dict[str, Any]:
        """Upload raw bytes to Cloudinary.

        Args:
            data: Raw file bytes
            public_id: Cloudinary public_id for the asset
            resource_type: "image", "video", or "auto"
            filename: Filename for format detection

        Returns:
            Same format as upload_from_url
        """
        if not self.enabled:
            return {}

        import cloudinary.uploader

        with self._upload_lock:
            try:
                logger.info(f"Uploading bytes to Cloudinary: {public_id} ({len(data):,} bytes)")
                file_obj = io.BytesIO(data)

                def _do_upload():
                    return cloudinary.uploader.upload(
                        file_obj,
                        public_id=public_id,
                        resource_type=resource_type,
                        overwrite=True,
                    )

                result = self._call_with_retry(_do_upload, max_retries=3, description=f"upload bytes ({public_id})")

                cloudinary_url = result.get("secure_url", result.get("url", ""))
                logger.info(f"Cloudinary bytes upload successful: {public_id}")

                return {
                    "url": cloudinary_url,
                    "public_id": result.get("public_id", public_id),
                    "resource_type": result.get("resource_type", resource_type),
                    "bytes": result.get("bytes", 0),
                    "format": result.get("format", ""),
                    "width": result.get("width"),
                    "height": result.get("height"),
                    "duration": result.get("duration"),
                    "created_at": result.get("created_at", ""),
                }
            except CloudinaryError:
                raise
            except Exception as e:
                logger.error(f"Cloudinary bytes upload failed: {e}")
                raise CloudinaryError(f"Bytes upload failed for {public_id}: {e}", e)

    def download_bytes(self, public_id: str) -> bytes:
        """Download an asset from Cloudinary as raw bytes.

        Useful for resolving Cloudinary URLs to base64 when
        using them as references for Magnific generation.

        Args:
            public_id: Cloudinary public_id of the asset

        Returns:
            Raw file bytes

        Raises:
            CloudinaryError: If download fails
        """
        if not self.enabled:
            raise CloudinaryError("Cloudinary service is not enabled")

        import cloudinary

        try:
            url = cloudinary.cloudinary_url(public_id, secure=True)[0]

            def _do_download():
                import urllib.request
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()

            data = self._call_with_retry(_do_download, max_retries=3, description=f"download ({public_id})")
            logger.info(f"Downloaded from Cloudinary: {public_id} ({len(data):,} bytes)")
            return data
        except CloudinaryError:
            raise
        except Exception as e:
            logger.error(f"Cloudinary download failed for {public_id}: {e}")
            raise CloudinaryError(f"Download failed for {public_id}: {e}", e)

    def download_as_base64(self, public_id: str, mime_type: str = "image/png") -> str:
        """Download an asset and return as base64 data URI.

        Convenience method for converting Cloudinary assets to base64
        for use as Magnific references.

        Args:
            public_id: Cloudinary public_id
            mime_type: MIME type for the data URI (e.g. "image/png", "video/mp4")

        Returns:
            Base64 data URI string (e.g. "data:image/png;base64,...")
        """
        import base64
        data = self.download_bytes(public_id)
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

    def delete(self, public_id: str, resource_type: str = "auto") -> dict:
        """Delete an asset from Cloudinary.

        Args:
            public_id: Cloudinary public_id to delete
            resource_type: "image", "video", or "auto"

        Returns:
            Dict with "result": "ok" or "not found"
        """
        if not self.enabled:
            return {"result": "not_enabled"}

        import cloudinary.api

        try:
            result = cloudinary.api.delete_resources(
                [public_id], resource_type=resource_type, invalidate=True
            )
            deleted = result.get("deleted", {})
            status = "ok" if public_id in deleted else "not_found"
            logger.info(f"Cloudinary delete: {public_id} -> {status}")
            return {"result": status, "public_id": public_id}
        except Exception as e:
            logger.error(f"Cloudinary delete failed for {public_id}: {e}")
            raise CloudinaryError(f"Delete failed for {public_id}: {e}", e)

    def list_resources(
        self,
        prefix: str = "",
        resource_type: str = "image",
        max_results: int = 30,
        next_cursor: str | None = None,
    ) -> dict[str, Any]:
        """List resources with optional prefix filtering.

        Args:
            prefix: Folder/prefix to filter by (e.g. "magnific/image/")
            resource_type: "image" or "video"
            max_results: Max items per page (1-100)
            next_cursor: Pagination cursor from previous response

        Returns:
            Dict with "resources" list, "count" (items in this page),
            and "next_cursor" (if more pages exist).
            Note: "count" is the number of items returned in this page,
            not the total across all pages (Cloudinary Admin API does not provide totals).
        """
        if not self.enabled:
            return {"resources": [], "count": 0}

        import cloudinary.api

        try:
            options = {
                "type": "upload",
                "prefix": prefix or f"{self.folder}/",
                "resource_type": resource_type,
                "max_results": min(max_results, 100),
                "sort_by": "created_at.desc",
            }
            if next_cursor:
                options["next_cursor"] = next_cursor

            result = cloudinary.api.resources(**options)
            resources = []
            for r in result.get("resources", []):
                resources.append({
                    "public_id": r.get("public_id", ""),
                    "url": r.get("secure_url", r.get("url", "")),
                    "format": r.get("format", ""),
                    "resource_type": resource_type,
                    "bytes": r.get("bytes", 0),
                    "width": r.get("width"),
                    "height": r.get("height"),
                    "duration": r.get("duration"),
                    "created_at": r.get("created_at", ""),
                })

            return {
                "resources": resources,
                "count": len(resources),
                "next_cursor": result.get("next_cursor"),
            }
        except CloudinaryError:
            raise
        except Exception as e:
            logger.error(f"Cloudinary list failed: {e}")
            raise CloudinaryError(f"Failed to list resources: {e}", e)

    def is_cloudinary_url(self, url: str, validate_cloud_name: bool = False) -> bool:
        """Check if a URL belongs to Cloudinary.

        Args:
            url: URL to check
            validate_cloud_name: If True, also verify the URL matches our cloud name

        Returns:
            True if the URL is from Cloudinary (and optionally matches our cloud)
        """
        if not url:
            return False
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        is_cloudinary = "cloudinary.com" in hostname
        if not is_cloudinary:
            return False
        if validate_cloud_name and hasattr(self, '_cloud_name'):
            # Check if URL path starts with /{cloud_name}/
            parts = parsed.path.split("/")
            return len(parts) > 1 and parts[1] == getattr(self, '_cloud_name', '')
        return True

    @staticmethod
    def extract_public_id_from_url(url: str) -> str | None:
        """Extract the Cloudinary public_id from a Cloudinary URL.

        Handles URLs with and without transformation parameters, and with
        or without version numbers.

        URL formats:
            .../upload/{public_id}.{format}
            .../upload/v{version}/{public_id}.{format}
            .../upload/{transformations}/v{version}/{public_id}.{format}
            .../upload/{transformations}/{public_id}.{format}

        Args:
            url: Cloudinary URL

        Returns:
            Public ID string or None if not a Cloudinary URL
        """
        if not url or "cloudinary.com" not in url:
            return None

        try:
            parsed = urlparse(url)
            path = parsed.path

            # Find /upload/ segment
            upload_idx = path.find("/upload/")
            if upload_idx < 0:
                return None

            # Everything after /upload/
            after_upload = path[upload_idx + len("/upload/"):]

            # Skip transformation segments: Cloudinary transformations use _ as separator
            # and contain parameter patterns like c_fill, w_300, h_200, q_auto, etc.
            # The public_id starts after the last transformation segment.
            # Strategy: split by '/' and skip segments that look like transformations.
            segments = after_upload.split("/")

            # Find where the public_id starts (after transformations and version)
            pub_id_start = 0
            for i, seg in enumerate(segments):
                # Version segment: v{digits}
                if re.match(r"^v\d+$", seg):
                    pub_id_start = i + 1
                    continue
                # Transformation segment: contains Cloudinary param patterns
                # Transformation segments have underscores and known prefixes
                if re.match(r"^([a-z]_\w+(,|$))", seg) or "," in seg:
                    pub_id_start = i + 1
                    continue

            # Join remaining segments as public_id
            public_id = "/".join(segments[pub_id_start:]) if pub_id_start < len(segments) else ""

            if not public_id:
                return None

            # Remove file extension (last .{ext} only)
            public_id = public_id.rsplit(".", 1)[0]
            return public_id
        except Exception:
            pass
        return None
