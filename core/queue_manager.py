"""QueueManager — smart queue management with ownership-aware clearing.

Fetches the current queue from Magnific API, classifies items as "ours"
(registered in CreationRegistry) or "external" (not registered), and
cancels external items to prioritize our project's generations.

Design decisions:
    - OFF by default (opt-in queue clearing)
    - Cancel before submit, not after
    - Graceful degradation: errors during cancel are logged, not raised
    - Returns structured dicts with counts and details
    - Uses MagnificClient for all HTTP calls
"""

from datetime import datetime, timezone

from core.client import MagnificClient
from core.creation_registry import CreationRegistry
from utils.logger import setup_logger

logger = setup_logger("queue_manager")


class QueueManager:
    """Smart queue management with ownership-aware clearing.

    Orchestrates queue clearing by:
    1. Fetching all queued creations from Magnific API
    2. Classifying each as "ours" (registered) or "external" (not registered)
    3. Cancelling only external items
    4. Returning a summary of what was cancelled and what was skipped
    """

    def __init__(
        self,
        client: MagnificClient,
        registry: CreationRegistry,
        enabled: bool = False,
    ):
        """Initialize QueueManager.

        Args:
            client: MagnificClient used for HTTP requests.
            registry: CreationRegistry for tracking our creations.
            enabled: Whether auto-clearing is enabled (default: False).
        """
        self.client = client
        self.registry = registry
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        """Whether automatic queue clearing is enabled."""
        return self._enabled

    def configure(self, enabled: bool) -> None:
        """Enable or disable automatic queue clearing.

        Args:
            enabled: True to enable, False to disable.
        """
        self._enabled = enabled
        logger.info(f"Queue clearing {'enabled' if enabled else 'disabled'}")

    def clear_external_queue(self) -> dict:
        """Clear all non-registered queued creations from the account queue.

        The smart cancel logic:
        1. If disabled → no-op
        2. Fetch all queued creations
        3. If all are ours → skip all (natural ordering preserved)
        4. If external items exist → cancel each one individually
        5. Return summary with counts and details

        Returns:
            Dict with keys: cleared, errors, skipped_ours, total_queued,
            enabled, reason, cancelled_identifiers, skipped_identifiers.
        """
        if not self._enabled:
            return {
                "cleared": 0,
                "errors": 0,
                "skipped_ours": 0,
                "total_queued": 0,
                "enabled": False,
                "reason": "disabled",
                "cancelled_identifiers": [],
                "skipped_identifiers": [],
            }

        # Fetch queued creations from Magnific
        queued_data = self.client.get(
            "/api/creations",
            params={"status": "queued", "per_page": 100},
        )
        queued_items = queued_data.get("data", []) if queued_data else []

        # Classify items
        our_items = []
        external_items = []
        for item in queued_items:
            identifier = item.get("identifier", "")
            if self.registry.is_ours(identifier):
                our_items.append(item)
            else:
                external_items.append(item)

        # If all ours, skip everything (preserve natural ordering)
        if not external_items:
            return {
                "cleared": 0,
                "errors": 0,
                "skipped_ours": len(our_items),
                "total_queued": len(queued_items),
                "enabled": True,
                "reason": "all_ours",
                "cancelled_identifiers": [],
                "skipped_identifiers": [item.get("identifier") for item in our_items],
            }

        # Cancel external items
        cleared = 0
        errors = 0
        cancelled_identifiers = []

        for item in external_items:
            identifier = item.get("identifier", "")
            try:
                result = self.cancel_creation(identifier)
                if result.get("success"):
                    cleared += 1
                    cancelled_identifiers.append(identifier)
                else:
                    errors += 1
                    logger.warning(f"Failed to cancel {identifier}: {result}")
            except Exception as e:
                errors += 1
                logger.warning(f"Error cancelling {identifier}: {e}")

        return {
            "cleared": cleared,
            "errors": errors,
            "skipped_ours": len(our_items),
            "total_queued": len(queued_items),
            "enabled": True,
            "reason": "cleared" if cleared > 0 else "no_external",
            "cancelled_identifiers": cancelled_identifiers,
            "skipped_identifiers": [item.get("identifier") for item in our_items],
        }

    def cancel_creation(self, identifier: str) -> dict:
        """Cancel a single queued creation by its identifier.

        Args:
            identifier: The creation identifier to cancel.

        Returns:
            Dict from Magnific cancel API response.
        """
        return self.client.post(
            "/api/creations/cancel",
            json_data={"identifier": identifier},
        )

    def get_queue_snapshot(self) -> dict:
        """Fetch and classify the current queue with ownership tags.

        Returns:
            Dict with total_queued, ours_count, external_count, items (with is_ours),
            and checked_at.
        """
        queued_data = self.client.get(
            "/api/creations",
            params={"status": "queued", "per_page": 100},
        )
        queued_items = queued_data.get("data", []) if queued_data else []

        items = []
        ours_count = 0
        external_count = 0

        for item in queued_items:
            identifier = item.get("identifier", "")
            is_ours = self.registry.is_ours(identifier)
            if is_ours:
                ours_count += 1
            else:
                external_count += 1

            items.append({
                "id": item.get("id"),
                "identifier": identifier,
                "tool": item.get("tool"),
                "model": item.get("metadata", {}).get("model"),
                "is_ours": is_ours,
                "created_at": item.get("created_at"),
            })

        return {
            "total_queued": len(queued_items),
            "ours_count": ours_count,
            "external_count": external_count,
            "items": items,
            "auto_clear_enabled": self._enabled,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
