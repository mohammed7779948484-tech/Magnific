"""Tests for Cloudinary cloud storage service and asset registry."""

import json
import os
import tempfile

import pytest

from core.asset_registry import AssetRegistry, AssetRecord
from tests.helpers.fake_deps import (
    FakeClient, FakePoller, FakeUploader, FakeQueueManager,
    FakeCreationRegistry,
)


# ─── AssetRegistry Tests ────────────────────────────────────────────


class TestAssetRegistry:
    """Test suite for the local JSON-based asset registry."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a temporary registry for testing."""
        return AssetRegistry(data_dir=str(tmp_path))

    def test_creates_data_directory_and_file(self, tmp_path):
        """Registry should create data directory and assets.json on init."""
        reg = AssetRegistry(data_dir=str(tmp_path))
        assert (tmp_path / "assets.json").exists()

    def test_register_basic_asset(self, registry):
        """Registering an asset should create a record with auto-generated ID."""
        record = registry.register(
            asset_type="image",
            model="flux-2",
            creation_id="abc123",
            public_id="magnific/image/flux-2/abc123_0",
            cloudinary_url="https://res.cloudinary.com/test/magnific/image/flux-2/abc123_0.png",
            original_url="https://cdn.magnific.com/abc123.png",
            bytes=102400,
            width=1024,
            height=1024,
            format="png",
            prompt="A beautiful sunset",
        )

        assert record.id.startswith("asset_")
        assert record.asset_type == "image"
        assert record.model == "flux-2"
        assert record.creation_id == "abc123"
        assert record.use_count == 0
        assert record.prompt == "A beautiful sunset"

    def test_register_increments_id_counter(self, registry):
        """Each registration should increment the ID counter."""
        r1 = registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )
        r2 = registry.register(
            asset_type="video", model="seedance-2-pro", creation_id="2",
            public_id="p2", cloudinary_url="url2",
        )

        assert r1.id == "asset_000001"
        assert r2.id == "asset_000002"

    def test_get_by_id(self, registry):
        """Should retrieve an asset by its ID."""
        record = registry.register(
            asset_type="image", model="flux-2", creation_id="abc",
            public_id="p1", cloudinary_url="url1",
        )

        found = registry.get(record.id)
        assert found is not None
        assert found.cloudinary_url == "url1"

    def test_get_nonexistent_returns_none(self, registry):
        """Getting a non-existent ID returns None."""
        assert registry.get("asset_999999") is None

    def test_get_by_creation_id(self, registry):
        """Should find assets by Magnific creation ID."""
        registry.register(
            asset_type="image", model="flux-2", creation_id="creation-42",
            public_id="p1", cloudinary_url="url1",
        )
        registry.register(
            asset_type="image", model="flux-2", creation_id="creation-42",
            public_id="p2", cloudinary_url="url2",
        )

        results = registry.get_by_creation_id("creation-42")
        assert len(results) == 2

    def test_get_by_cloudinary_url(self, registry):
        """Should find an asset by its Cloudinary URL."""
        url = "https://res.cloudinary.com/test/magnific/image/model/id.png"
        registry.register(
            asset_type="image", model="flux-2", creation_id="abc",
            public_id="p1", cloudinary_url=url,
        )

        found = registry.get_by_cloudinary_url(url)
        assert found is not None
        assert found.id.startswith("asset_")

    def test_list_assets_all(self, registry):
        """Listing without filters returns all assets."""
        registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )
        registry.register(
            asset_type="video", model="seedance-2-pro", creation_id="2",
            public_id="p2", cloudinary_url="url2",
        )

        assets = registry.list_assets()
        assert len(assets) == 2

    def test_list_assets_filter_by_type(self, registry):
        """Filtering by asset_type should return only matching assets."""
        registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )
        registry.register(
            asset_type="image", model="gpt-2", creation_id="2",
            public_id="p2", cloudinary_url="url2",
        )
        registry.register(
            asset_type="video", model="seedance-2-pro", creation_id="3",
            public_id="p3", cloudinary_url="url3",
        )

        images = registry.list_assets(asset_type="image")
        videos = registry.list_assets(asset_type="video")

        assert len(images) == 2
        assert len(videos) == 1

    def test_list_assets_filter_by_model(self, registry):
        """Filtering by model slug should return only matching assets."""
        registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )
        registry.register(
            asset_type="image", model="gpt-2", creation_id="2",
            public_id="p2", cloudinary_url="url2",
        )

        flux_assets = registry.list_assets(model="flux-2")
        assert len(flux_assets) == 1
        assert flux_assets[0].model == "flux-2"

    def test_list_assets_pagination(self, registry):
        """Pagination with limit and offset should work correctly."""
        for i in range(5):
            registry.register(
                asset_type="image", model="flux-2", creation_id=str(i),
                public_id=f"p{i}", cloudinary_url=f"url{i}",
            )

        page1 = registry.list_assets(limit=2, offset=0)
        page2 = registry.list_assets(limit=2, offset=2)
        page3 = registry.list_assets(limit=2, offset=4)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

    def test_mark_used_increments_count(self, registry):
        """mark_used should increment use_count and set last_used_at."""
        record = registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )

        assert record.use_count == 0

        registry.mark_used(record.id)
        updated = registry.get(record.id)
        assert updated.use_count == 1
        assert updated.last_used_at != ""

        registry.mark_used(record.id)
        registry.mark_used(record.id)
        updated = registry.get(record.id)
        assert updated.use_count == 3

    def test_mark_used_nonexistent_returns_false(self, registry):
        """mark_used on nonexistent asset returns False."""
        assert registry.mark_used("asset_999999") is False

    def test_delete(self, registry):
        """Deleting an asset removes it from the registry."""
        record = registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )

        assert registry.get(record.id) is not None
        assert registry.delete(record.id) is True
        assert registry.get(record.id) is None

    def test_delete_nonexistent_returns_false(self, registry):
        assert registry.delete("asset_999999") is False

    def test_count(self, registry):
        """Count should return correct number of assets."""
        registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1",
        )
        registry.register(
            asset_type="video", model="seedance-2-pro", creation_id="2",
            public_id="p2", cloudinary_url="url2",
        )

        assert registry.count() == 2
        assert registry.count(asset_type="image") == 1
        assert registry.count(asset_type="video") == 1

    def test_stats(self, registry):
        """Stats should return aggregate information."""
        registry.register(
            asset_type="image", model="flux-2", creation_id="1",
            public_id="p1", cloudinary_url="url1", bytes=1024000,
            prompt="test prompt",
        )
        registry.register(
            asset_type="video", model="seedance-2-pro", creation_id="2",
            public_id="p2", cloudinary_url="url2", bytes=5120000,
        )
        # Mark one as used
        r1 = registry.get("asset_000001")
        registry.mark_used(r1.id)

        stats = registry.stats()
        assert stats["total"] == 2
        assert stats["images"] == 1
        assert stats["videos"] == 1
        assert stats["total_bytes"] == 6144000
        assert stats["total_uses"] == 1
        assert stats["model_breakdown"]["flux-2"] == 1
        assert stats["model_breakdown"]["seedance-2-pro"] == 1

    def test_persistence_across_instances(self, tmp_path):
        """Registry should persist data to disk and reload correctly."""
        reg1 = AssetRegistry(data_dir=str(tmp_path))
        reg1.register(
            asset_type="image", model="flux-2", creation_id="42",
            public_id="p1", cloudinary_url="url1",
            prompt="test persistence",
        )

        # Create a new registry instance loading the same file
        reg2 = AssetRegistry(data_dir=str(tmp_path))
        assert reg2.count() == 1

        record = reg2.get("asset_000001")
        assert record is not None
        assert record.prompt == "test persistence"
        assert record.model == "flux-2"

    def test_to_dict_and_from_dict_roundtrip(self):
        """AssetRecord serialization/deserialization should be lossless."""
        record = AssetRecord(
            id="asset_000001",
            asset_type="image",
            model="flux-2",
            creation_id="abc123",
            public_id="magnific/image/flux-2/abc123_0",
            cloudinary_url="https://example.com/image.png",
            original_url="https://cdn.magnific.com/abc.png",
            resource_type="image",
            bytes=204800,
            width=2048,
            height=1024,
            duration=None,
            format="png",
            prompt="A cat",
            created_at="2025-01-01T00:00:00Z",
            last_used_at="",
            use_count=5,
            tags=["cat", "animal"],
        )

        data = record.to_dict()
        restored = AssetRecord.from_dict(data)

        assert restored.id == record.id
        assert restored.asset_type == record.asset_type
        assert restored.tags == ["cat", "animal"]
        assert restored.use_count == 5
        assert restored.width == 2048


# ─── CloudinaryService Tests (with disabled mode) ─────────────────


class TestCloudinaryServiceDisabled:
    """Test CloudinaryService when disabled (no credentials)."""

    def test_disabled_service_creation(self):
        """Creating a disabled service should not fail."""
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False)
        assert svc.is_enabled() is False

    def test_disabled_service_with_partial_credentials(self):
        """Service should auto-disable when credentials are incomplete."""
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(cloud_name="test")
        assert svc.is_enabled() is False

    def test_upload_from_url_returns_empty_when_disabled(self):
        """Upload should return empty dict when service is disabled."""
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False)
        result = svc.upload_from_url("https://example.com/image.png", "test/id")
        assert result == {}

    def test_upload_from_bytes_returns_empty_when_disabled(self):
        """Upload should return empty dict when service is disabled."""
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False)
        result = svc.upload_from_bytes(b"fake data", "test/id")
        assert result == {}

    def test_download_raises_when_disabled(self):
        """Download should raise CloudinaryError when service is disabled."""
        from core.cloudinary_service import CloudinaryService, CloudinaryError

        svc = CloudinaryService(enabled=False)
        with pytest.raises(CloudinaryError):
            svc.download_bytes("test/id")

    def test_delete_returns_not_enabled_when_disabled(self):
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False)
        result = svc.delete("test/id")
        assert result["result"] == "not_enabled"

    def test_list_returns_empty_when_disabled(self):
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False)
        result = svc.list_resources()
        assert result["resources"] == []
        assert result["total"] == 0

    def test_is_cloudinary_url_detects(self):
        """Should correctly identify Cloudinary URLs."""
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False)

        assert svc.is_cloudinary_url("https://res.cloudinary.com/test/image/upload/v123/magnific/image.png") is True
        assert svc.is_cloudinary_url("https://cdn.magnific.com/image.png") is False
        assert svc.is_cloudinary_url("") is False
        assert svc.is_cloudinary_url(None) is False

    def test_extract_public_id_from_url(self):
        """Should extract public_id from Cloudinary URL."""
        from core.cloudinary_service import CloudinaryService

        url = "https://res.cloudinary.com/mycloud/image/upload/v123456/magnific/image/flux-2/abc123_0.png"
        public_id = CloudinaryService.extract_public_id_from_url(url)
        assert public_id == "magnific/image/flux-2/abc123_0"

    def test_extract_public_id_non_cloudinary_returns_none(self):
        """Should return None for non-Cloudinary URLs."""
        from core.cloudinary_service import CloudinaryService

        assert CloudinaryService.extract_public_id_from_url("https://example.com/image.png") is None
        assert CloudinaryService.extract_public_id_from_url("") is None

    def test_build_public_id(self):
        """Should build structured public IDs correctly."""
        from core.cloudinary_service import CloudinaryService

        svc = CloudinaryService(enabled=False, folder="magnific")

        assert svc.build_public_id("image", "flux-2", "abc123") == "magnific/image/flux-2/abc123_0"
        assert svc.build_public_id("video", "seedance-2-pro", "xyz789", index=2) == "magnific/video/seedance-2-pro/xyz789_2"
