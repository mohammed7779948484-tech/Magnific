"""Polling engine for creation status and download."""

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any, Generator

from config.endpoints import Endpoints
from core.client import MagnificClient
from core.exceptions import GenerationError, PollingTimeoutError
from utils.file_helpers import FileHelpers
from utils.logger import setup_logger

logger = setup_logger("poller")


class Poller:
    """Polls creation status and downloads completed content."""

    def __init__(
        self,
        client: MagnificClient,
        poll_interval: int = 5,
        poll_timeout: int = 180,
    ):
        self.client = client
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    def poll_creation(self, creation_id: str | int, creation_type: str = "image") -> dict:
        """Poll a creation until it completes or fails.

        Args:
            creation_id: The creation ID to poll
            creation_type: "image" or "video"

        Returns:
            Dict with creation details including URL when completed

        Raises:
            PollingTimeoutError: If creation doesn't complete within timeout
            GenerationError: If creation fails
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > self.poll_timeout:
                raise PollingTimeoutError(
                    f"Creation {creation_id} did not complete within {self.poll_timeout}s timeout",
                )

            try:
                result = self.client.get(f"/api/creation/{creation_id}")
            except Exception as e:
                logger.warning(f"Poll error for {creation_id}: {e}")
                time.sleep(self.poll_interval)
                continue

            status = result.get("status", "unknown")

            if status == "completed":
                # For video: URL is in metadata.url
                # For image: URL is in url field or metadata
                url = None
                if creation_type == "video":
                    url = result.get("metadata", {}).get("url")
                else:
                    url = result.get("url") or result.get("metadata", {}).get("url")

                if url:
                    logger.info(f"Creation {creation_id} completed! URL: {url[:80]}...")
                    return {**result, "download_url": url}
                else:
                    logger.warning(f"Creation {creation_id} completed but no URL found")

                return result

            elif status == "failed":
                error_msg = result.get("error") or result.get("message") or "Unknown error"
                raise GenerationError(
                    f"Creation {creation_id} failed: {error_msg}",
                    status_code=None,
                    response_data=result,
                )

            else:
                logger.info(f"Creation {creation_id} status: {status} (elapsed: {elapsed:.0f}s)")
                time.sleep(self.poll_interval)

    def poll_creation_stream(
        self, creation_id: str | int, creation_type: str = "image"
    ) -> Generator[dict, None, None]:
        """Poll a creation and yield status updates.

        Args:
            creation_id: The creation ID to poll
            creation_type: "image" or "video"

        Yields:
            Status update dicts with 'status' and optional 'progress' keys
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > self.poll_timeout:
                yield {"status": "timeout", "elapsed": elapsed}
                return

            try:
                result = self.client.get(f"/api/creation/{creation_id}")
            except Exception as e:
                yield {"status": "error", "message": str(e)}
                time.sleep(self.poll_interval)
                continue

            status = result.get("status", "unknown")
            yield {"status": status, "elapsed": elapsed, "data": result}

            if status in ("completed", "failed"):
                return

            time.sleep(self.poll_interval)

    async def async_poll_creation_stream(
        self, creation_id: str | int, creation_type: str = "image"
    ) -> AsyncGenerator[dict, None]:
        """Async version of poll_creation_stream for SSE endpoints.

        Uses asyncio.sleep instead of time.sleep to avoid blocking the event loop.
        Yields status updates progressively — the caller can iterate this
        in an async for loop without blocking.

        Args:
            creation_id: The creation ID to poll
            creation_type: "image" or "video"

        Yields:
            Status update dicts with 'status' and optional 'progress' keys
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > self.poll_timeout:
                yield {"status": "timeout", "elapsed": elapsed}
                return

            try:
                result = await asyncio.to_thread(
                    self.client.get, f"/api/creation/{creation_id}"
                )
            except Exception as e:
                yield {"status": "error", "message": str(e)}
                await asyncio.sleep(self.poll_interval)
                continue

            status = result.get("status", "unknown")
            yield {"status": status, "elapsed": elapsed, "data": result}

            if status in ("completed", "failed"):
                return

            await asyncio.sleep(self.poll_interval)

    def poll_image_by_family(self, creation_id: str | int, family: str) -> dict:
        """Poll image creation via creations list (alternative method).

        Args:
            creation_id: The creation ID
            family: The model family name

        Returns:
            Dict with image details when completed
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > self.poll_timeout:
                raise PollingTimeoutError(
                    f"Image {creation_id} not found in creations list within {self.poll_timeout}s",
                )

            try:
                result = self.client.get(
                    "/api/creations",
                    params={"family": family},
                )
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                time.sleep(self.poll_interval)
                continue

            creations = result.get("data", [])
            found = next((c for c in creations if str(c.get("id")) == str(creation_id)), None)

            if found:
                if found.get("status") == "completed":
                    url = found.get("url")
                    logger.info(f"Image {creation_id} completed! URL: {url[:80] if url else 'N/A'}...")
                    return {**found, "download_url": url}
                elif found.get("status") == "failed":
                    raise GenerationError(f"Image {creation_id} generation failed")
                else:
                    logger.info(f"Image {creation_id} status: {found.get('status')}")

            time.sleep(self.poll_interval)

    def download_file(self, url: str, output_path: str) -> str:
        """Download a file from URL.

        Args:
            url: CDN URL to download from
            output_path: Local path to save the file

        Returns:
            Absolute path of saved file
        """
        return self.client.download(url, output_path)
