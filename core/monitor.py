"""Magnific Monitor — wraps Magnific creations API for monitoring.

Provides methods to query queue status, creation lists, statistics,
and account limits. All methods delegate to MagnificClient.get().
"""

from datetime import datetime, timezone
from typing import Any

from utils.logger import setup_logger

logger = setup_logger("monitor")


class MagnificMonitor:
    """Monitors Magnific account creations, queue status, and usage.

    Wraps the Magnific creations API to provide structured access
    to queue positions, active generations, completion history,
    and account limits.
    """

    VALID_STATUSES = ("processing", "queued", "completed", "failed", "cancelled")

    def __init__(self, client: Any):
        """Initialize with a MagnificClient instance.

        Args:
            client: MagnificClient used for all HTTP requests.
        """
        self.client = client

    def get_queue_status(self) -> dict:
        """Fetch current queue snapshot: queued + processing items.

        Returns:
            Dict with 'queued', 'processing', 'queued_items', 'processing_items',
            'total_active', and 'checked_at' keys.
        """
        queued_data = self.client.get(
            "/api/creations",
            params={"status": "queued", "per_page": 50},
        )
        processing_data = self.client.get(
            "/api/creations",
            params={"status": "processing", "per_page": 50},
        )

        queued_items = []
        for item in queued_data.get("data", []):
            meta = item.get("metadata", {})
            queued_items.append({
                "id": item.get("id"),
                "tool": item.get("tool"),
                "model": meta.get("model"),
                "position": meta.get("position"),
                "expected_queued_time": meta.get("expectedQueuedTime"),
                "expected_generation_time": meta.get("expectedGenerationTime"),
                "prompt": meta.get("prompt"),
                "created_at": item.get("created_at"),
                "date_for_humans": item.get("date_for_humans"),
            })

        processing_items = []
        for item in processing_data.get("data", []):
            meta = item.get("metadata", {})
            processing_items.append({
                "id": item.get("id"),
                "tool": item.get("tool"),
                "model": meta.get("model"),
                "expected_generation_time": meta.get("expectedGenerationTime"),
                "prompt": meta.get("prompt"),
                "created_at": item.get("created_at"),
                "date_for_humans": item.get("date_for_humans"),
            })

        return {
            "queued": len(queued_items),
            "processing": len(processing_items),
            "queued_items": queued_items,
            "processing_items": processing_items,
            "total_active": len(queued_items) + len(processing_items),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_creations(
        self,
        status: str | None = None,
        page: int = 1,
        per_page: int = 10,
        sort: str = "-createdAt",
    ) -> dict:
        """List creations with optional filtering and pagination.

        Args:
            status: Filter by status (processing, queued, completed, failed, cancelled).
            page: Page number (1-based).
            per_page: Items per page (max 50).
            sort: Sort field (e.g. 'createdAt', '-createdAt').

        Returns:
            Dict with 'data' (list of creations) and 'meta' (pagination info).
        """
        params: dict[str, Any] = {
            "per_page": min(per_page, 50),
            "page": page,
            "sort": sort,
        }
        if status:
            params["status"] = status

        return self.client.get("/api/creations", params=params)

    def get_creation(self, creation_id: str | int) -> dict:
        """Fetch detailed info for a single creation.

        Args:
            creation_id: The creation ID to look up.

        Returns:
            Dict with full creation details.
        """
        return self.client.get(f"/api/creation/{creation_id}")

    def get_active_creations(self) -> list[dict]:
        """Get all currently active creations (processing + queued).

        Returns:
            Combined list of processing and queued creation dicts.
        """
        queued_data = self.client.get(
            "/api/creations",
            params={"status": "queued", "per_page": 50},
        )
        processing_data = self.client.get(
            "/api/creations",
            params={"status": "processing", "per_page": 50},
        )

        active = []
        active.extend(queued_data.get("data", []))
        active.extend(processing_data.get("data", []))
        return active

    def get_stats(self) -> dict:
        """Aggregate statistics across all creation statuses.

        Returns:
            Dict with 'counts' per status, 'total', and 'checked_at'.
        """
        counts = {}
        total = 0

        for status in self.VALID_STATUSES:
            resp = self.client.get(
                "/api/creations",
                params={"status": status, "per_page": 1},
            )
            count = resp.get("meta", {}).get("total", 0)
            counts[status] = count
            total += count

        return {
            "counts": counts,
            "total": total,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_limits(self) -> dict:
        """Fetch account limits and credit information.

        Returns:
            Dict with account limit details from Magnific API.
        """
        return self.client.get("/api/limits")
