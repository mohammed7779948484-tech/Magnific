"""Local asset registry — JSON-based metadata store for cloud-stored assets.

Tracks generated assets (images/videos) that are stored in Cloudinary,
including their Cloudinary URLs, Magnific metadata, and usage history.
Enables quick lookup and reuse of assets as references without
re-downloading from Magnific or re-uploading from client devices.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.logger import setup_logger

logger = setup_logger("asset_registry")

DEFAULT_REGISTRY_PATH = "data/assets.json"


class AssetRecord:
    """Metadata for a single stored asset."""

    __slots__ = (
        "id", "asset_type", "model", "creation_id", "public_id",
        "cloudinary_url", "original_url", "resource_type", "bytes",
        "width", "height", "duration", "format", "prompt",
        "created_at", "last_used_at", "use_count", "tags",
    )

    def __init__(
        self,
        id: str,
        asset_type: str,
        model: str,
        creation_id: str,
        public_id: str,
        cloudinary_url: str,
        original_url: str = "",
        resource_type: str = "image",
        bytes: int = 0,
        width: int | None = None,
        height: int | None = None,
        duration: float | None = None,
        format: str = "",
        prompt: str = "",
        created_at: str = "",
        last_used_at: str = "",
        use_count: int = 0,
        tags: list[str] | None = None,
    ):
        self.id = id
        self.asset_type = asset_type  # "image" or "video"
        self.model = model
        self.creation_id = creation_id
        self.public_id = public_id
        self.cloudinary_url = cloudinary_url
        self.original_url = original_url  # Magnific CDN URL
        self.resource_type = resource_type
        self.bytes = bytes
        self.width = width
        self.height = height
        self.duration = duration
        self.format = format
        self.prompt = prompt
        self.created_at = created_at
        self.last_used_at = last_used_at
        self.use_count = use_count
        self.tags = tags or []

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "asset_type": self.asset_type,
            "model": self.model,
            "creation_id": self.creation_id,
            "public_id": self.public_id,
            "cloudinary_url": self.cloudinary_url,
            "original_url": self.original_url,
            "resource_type": self.resource_type,
            "bytes": self.bytes,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "format": self.format,
            "prompt": self.prompt,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetRecord":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__slots__})

    def mark_used(self) -> None:
        """Record that this asset was used as a reference."""
        self.use_count += 1
        self.last_used_at = datetime.now(timezone.utc).isoformat()


class AssetRegistry:
    """JSON-based registry for tracking cloud-stored assets.

    Stores metadata about each asset in a local JSON file so that:
        1. Assets can be quickly listed/searched without Cloudinary API calls
        2. Usage history is tracked (how often reused as reference)
        3. Assets can be found by model, type, creation_id, or tags

    Thread-safe: All read/write operations are protected by a lock.

    Usage:
        registry = AssetRegistry(data_dir="data")
        registry.register(AssetRecord(...))
        assets = registry.list_assets(asset_type="image", model="flux-2")
    """

    def __init__(self, data_dir: str = "data"):
        """Initialize registry with data directory.

        Args:
            data_dir: Directory for the assets.json file (default: "data")
        """
        self._data_dir = Path(data_dir)
        self._file_path = self._data_dir / "assets.json"
        self._lock = threading.Lock()
        self._assets: dict[str, AssetRecord] = {}
        self._id_counter = 0

        # Ensure data directory exists
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._load()

    def _load(self) -> None:
        """Load assets from JSON file."""
        if not self._file_path.exists():
            logger.info(f"No existing registry at {self._file_path} — starting fresh")
            self._save()
            return

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._assets = {}
            for record_data in data.get("assets", []):
                record = AssetRecord.from_dict(record_data)
                self._assets[record.id] = record

            self._id_counter = data.get("id_counter", 0)
            logger.info(f"Loaded {len(self._assets)} assets from registry")
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            self._assets = {}
            self._id_counter = 0

    def _save(self) -> None:
        """Persist assets to JSON file."""
        try:
            data = {
                "id_counter": self._id_counter,
                "assets": [record.to_dict() for record in self._assets.values()],
            }
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _next_id(self) -> str:
        """Generate next unique ID."""
        self._id_counter += 1
        return f"asset_{self._id_counter:06d}"

    def register(
        self,
        asset_type: str,
        model: str,
        creation_id: str,
        public_id: str,
        cloudinary_url: str,
        original_url: str = "",
        resource_type: str = "image",
        bytes: int = 0,
        width: int | None = None,
        height: int | None = None,
        duration: float | None = None,
        format: str = "",
        prompt: str = "",
        tags: list[str] | None = None,
    ) -> AssetRecord:
        """Register a new asset in the registry.

        Args:
            asset_type: "image" or "video"
            model: Model slug used for generation
            creation_id: Magnific creation ID
            public_id: Cloudinary public ID
            cloudinary_url: Cloudinary secure URL
            original_url: Original Magnific CDN URL
            resource_type: Cloudinary resource type
            bytes: File size in bytes
            width: Image width (images only)
            height: Image height (images only)
            duration: Video duration in seconds (videos only)
            format: File format (png, jpg, mp4, etc.)
            prompt: The prompt used for generation
            tags: Custom tags for categorization

        Returns:
            The created AssetRecord
        """
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            record = AssetRecord(
                id=self._next_id(),
                asset_type=asset_type,
                model=model,
                creation_id=creation_id,
                public_id=public_id,
                cloudinary_url=cloudinary_url,
                original_url=original_url,
                resource_type=resource_type,
                bytes=bytes,
                width=width,
                height=height,
                duration=duration,
                format=format,
                prompt=prompt,
                created_at=now,
                tags=tags or [],
            )
            self._assets[record.id] = record
            self._save()
            logger.info(f"Registered asset {record.id}: {public_id}")
            return record

    def get(self, asset_id: str) -> AssetRecord | None:
        """Get an asset by ID.

        Args:
            asset_id: Asset ID (e.g. "asset_000001")

        Returns:
            AssetRecord or None if not found
        """
        return self._assets.get(asset_id)

    def get_by_creation_id(self, creation_id: str) -> list[AssetRecord]:
        """Find all assets for a given Magnific creation ID.

        Args:
            creation_id: Magnific creation ID

        Returns:
            List of matching AssetRecord objects
        """
        return [
            r for r in self._assets.values()
            if r.creation_id == str(creation_id)
        ]

    def get_by_cloudinary_url(self, url: str) -> AssetRecord | None:
        """Find an asset by its Cloudinary URL.

        Useful for checking if an asset is already stored before
        attempting to resolve it as a reference.

        Args:
            url: Cloudinary URL

        Returns:
            AssetRecord or None if not found
        """
        for record in self._assets.values():
            if record.cloudinary_url == url:
                return record
        return None

    def list_assets(
        self,
        asset_type: str | None = None,
        model: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AssetRecord]:
        """List assets with optional filtering.

        Args:
            asset_type: Filter by "image" or "video" (None = all)
            model: Filter by model slug (None = all)
            tag: Filter by tag (None = all)
            limit: Max results (default: 50)
            offset: Skip N results (default: 0)

        Returns:
            List of AssetRecord objects, sorted by creation time (newest first)
        """
        results = list(self._assets.values())

        if asset_type:
            results = [r for r in results if r.asset_type == asset_type]
        if model:
            results = [r for r in results if r.model == model]
        if tag:
            results = [r for r in results if tag in r.tags]

        # Sort newest first
        results.sort(key=lambda r: r.created_at, reverse=True)

        return results[offset:offset + limit]

    def mark_used(self, asset_id: str) -> bool:
        """Mark an asset as used (increment use_count).

        Args:
            asset_id: Asset ID

        Returns:
            True if found and updated, False otherwise
        """
        with self._lock:
            record = self._assets.get(asset_id)
            if record:
                record.mark_used()
                self._save()
                return True
            return False

    def delete(self, asset_id: str) -> bool:
        """Remove an asset from the registry.

        Does NOT delete from Cloudinary — use CloudinaryService.delete()
        separately if needed.

        Args:
            asset_id: Asset ID to remove

        Returns:
            True if found and deleted, False otherwise
        """
        with self._lock:
            if asset_id in self._assets:
                del self._assets[asset_id]
                self._save()
                logger.info(f"Deleted asset {asset_id} from registry")
                return True
            return False

    def count(self, asset_type: str | None = None) -> int:
        """Count assets, optionally filtered by type.

        Args:
            asset_type: "image", "video", or None for all

        Returns:
            Number of assets
        """
        if asset_type:
            return sum(1 for r in self._assets.values() if r.asset_type == asset_type)
        return len(self._assets)

    def stats(self) -> dict[str, Any]:
        """Get aggregate statistics about stored assets.

        Returns:
            Dict with counts, sizes, and model breakdowns
        """
        assets = list(self._assets.values())
        images = [r for r in assets if r.asset_type == "image"]
        videos = [r for r in assets if r.asset_type == "video"]

        model_counts: dict[str, int] = {}
        for r in assets:
            model_counts[r.model] = model_counts.get(r.model, 0) + 1

        total_bytes = sum(r.bytes for r in assets)
        total_uses = sum(r.use_count for r in assets)

        return {
            "total": len(assets),
            "images": len(images),
            "videos": len(videos),
            "total_bytes": total_bytes,
            "total_bytes_human": _bytes_to_human(total_bytes),
            "total_uses": total_uses,
            "model_breakdown": model_counts,
        }


def _bytes_to_human(n: int) -> str:
    """Convert bytes to human-readable string."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    else:
        return f"{n / (1024 * 1024 * 1024):.2f} GB"
