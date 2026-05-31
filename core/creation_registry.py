"""CreationRegistry — in-memory tracking of project-originated creations.

Tracks creation identifiers to distinguish our project's operations from
external operations (other users on the same shared account). This is used
by QueueManager to decide which queued creations to cancel.

Design decisions:
    - Thread-safe via threading.Lock
    - In-memory only (lost on restart — safe default: treats all as external)
    - Empty/None identifiers silently rejected
    - Duplicate register overwrites metadata
    - unregister() is a no-op for nonexistent identifiers
"""

import threading
from datetime import datetime, timezone


class CreationRegistry:
    """In-memory registry of creations submitted by our project.

    Tracks creation identifiers with optional metadata (model, tool, timestamp)
    so QueueManager can distinguish "ours" from "external" when clearing the queue.

    Thread-safe via threading.Lock for concurrent access from multiple requests.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._creations: dict[str, dict] = {}
        self._lock = threading.Lock()

    def register(self, identifier: str, metadata: dict | None = None) -> None:
        """Register a creation identifier as originating from our project.

        Args:
            identifier: The creation identifier string from Magnific API.
            metadata: Optional dict with creation details (model, tool, etc.).
        """
        if not identifier:
            return

        with self._lock:
            self._creations[identifier] = {
                "identifier": identifier,
                "metadata": metadata or {},
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }

    def is_ours(self, identifier: str) -> bool:
        """Check if a creation identifier was registered by our project.

        Args:
            identifier: The creation identifier to check.

        Returns:
            True if the identifier was registered, False otherwise.
        """
        if not identifier:
            return False

        with self._lock:
            return identifier in self._creations

    def unregister(self, identifier: str) -> None:
        """Remove a creation from the registry (e.g., after completion).

        Args:
            identifier: The creation identifier to remove.
        """
        if not identifier:
            return

        with self._lock:
            self._creations.pop(identifier, None)

    def list_all(self) -> list[dict]:
        """Return all registered creations with their metadata.

        Returns:
            List of dicts, each with 'identifier', 'metadata', 'registered_at'.
        """
        with self._lock:
            return list(self._creations.values())

    def count(self) -> int:
        """Return the number of currently registered creations."""
        with self._lock:
            return len(self._creations)

    def clear(self) -> None:
        """Remove all registered creations."""
        with self._lock:
            self._creations.clear()
