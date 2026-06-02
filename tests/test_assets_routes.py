"""Tests for asset management API routes."""

import os
import pytest

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api.middleware.error_handler import register_error_handlers
from api.middleware.rate_limiter import RateLimitMiddleware
from api.routes.assets import router as assets_router, set_deps as assets_set_deps
from core.asset_registry import AssetRegistry


class FakeCloudinaryService:
    """Lightweight Cloudinary test double — NOT a mock."""

    def __init__(self):
        self.enabled = True
        self.folder = "magnific-test"
        self.uploads = []
        self.deletes = []

    def is_enabled(self) -> bool:
        return self.enabled

    def upload_from_url(self, url, public_id, resource_type="auto"):
        self.uploads.append({"url": url, "public_id": public_id, "resource_type": resource_type})
        return {
            "url": f"https://res.cloudinary.com/test/{public_id}.png",
            "public_id": public_id,
            "resource_type": resource_type,
            "bytes": 102400,
            "width": 1024,
            "height": 1024,
            "format": "png",
        }

    def upload_from_bytes(self, data, public_id, resource_type="auto", filename="asset"):
        self.uploads.append({"bytes": len(data), "public_id": public_id})
        return self.upload_from_url("", public_id, resource_type)

    def delete(self, public_id, resource_type="auto"):
        self.deletes.append({"public_id": public_id, "resource_type": resource_type})
        return {"result": "ok", "public_id": public_id}

    def download_bytes(self, public_id):
        return b"fake-image-data"

    def download_as_base64(self, public_id, mime_type="image/png"):
        return "data:image/png;base64,ZmFrZS1pbWFnZS1kYXRh"

    def is_cloudinary_url(self, url):
        return "cloudinary.com" in (url or "")

    @staticmethod
    def extract_public_id_from_url(url):
        if not url or "cloudinary.com" not in url:
            return None
        parts = url.split("/upload/")
        if len(parts) > 1:
            return parts[-1].rsplit(".", 1)[0]
        return None


def _build_assets_test_app(tmp_path):
    """Create a minimal FastAPI app with only asset routes for testing."""
    cloudinary_svc = FakeCloudinaryService()
    asset_reg = AssetRegistry(data_dir=str(tmp_path))

    # Register test assets
    asset_reg.register(
        asset_type="image", model="flux-2", creation_id="img-001",
        public_id="magnific/image/flux-2/img-001_0",
        cloudinary_url="https://res.cloudinary.com/test/magnific/image/flux-2/img-001_0.png",
        original_url="https://cdn.magnific.com/img-001.png",
        bytes=102400, width=1024, height=1024, format="png",
        prompt="A sunset over mountains",
    )
    asset_reg.register(
        asset_type="video", model="seedance-2-pro", creation_id="vid-001",
        public_id="magnific/video/seedance-2-pro/vid-001_0",
        cloudinary_url="https://res.cloudinary.com/test/magnific/video/seedance-2-pro/vid-001_0.mp4",
        original_url="https://cdn.magnific.com/vid-001.mp4",
        bytes=5120000, duration=5.0, format="mp4",
        prompt="A cat walking",
    )

    # Set deps on the assets route module
    assets_set_deps(cloudinary_service=cloudinary_svc, asset_registry=asset_reg)

    app = FastAPI(title="Assets Test", version="1.0.0-test")
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, max_requests=999)
    app.include_router(assets_router)

    return app, cloudinary_svc, asset_reg


class TestAssetsEndpoints:
    """Test the /api/assets endpoints."""

    @pytest.fixture
    def app_and_services(self, tmp_path):
        return _build_assets_test_app(tmp_path)

    @pytest.fixture
    def client(self, app_and_services):
        app = app_and_services[0]
        return TestClient(app)

    def test_get_config(self, client):
        """GET /api/assets/config returns Cloudinary status."""
        resp = client.get("/api/assets/config")
        assert resp.status_code == 200

        data = resp.json()
        assert data["enabled"] is True
        assert data["folder"] == "magnific-test"

    def test_list_all_assets(self, client):
        """GET /api/assets lists all stored assets."""
        resp = client.get("/api/assets")
        assert resp.status_code == 200

        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert len(data["assets"]) == 2

    def test_list_filter_by_type_image(self, client):
        """GET /api/assets?asset_type=image filters to images only."""
        resp = client.get("/api/assets?asset_type=image")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 1
        assert data["assets"][0]["asset_type"] == "image"
        assert data["assets"][0]["model"] == "flux-2"

    def test_list_filter_by_type_video(self, client):
        """GET /api/assets?asset_type=video filters to videos only."""
        resp = client.get("/api/assets?asset_type=video")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 1
        assert data["assets"][0]["asset_type"] == "video"

    def test_list_filter_by_model(self, client):
        """GET /api/assets?model=flux-2 filters to that model."""
        resp = client.get("/api/assets?model=flux-2")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 1

    def test_get_single_asset(self, client):
        """GET /api/assets/{asset_id} returns detailed asset info."""
        resp = client.get("/api/assets/asset_000001")
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"] == "asset_000001"
        assert data["asset_type"] == "image"
        assert data["prompt"] == "A sunset over mountains"

    def test_get_nonexistent_asset(self, client):
        """GET /api/assets/{bad_id} returns 404."""
        resp = client.get("/api/assets/asset_999999")
        assert resp.status_code == 404

    def test_get_stats(self, client):
        """GET /api/assets/stats returns aggregate statistics."""
        resp = client.get("/api/assets/stats")
        assert resp.status_code == 200

        data = resp.json()
        assert data["success"] is True
        stats = data["stats"]
        assert stats["total"] == 2
        assert stats["images"] == 1
        assert stats["videos"] == 1
        assert "total_bytes_human" in stats

    def test_mark_asset_used(self, client):
        """POST /api/assets/{id}/use increments use_count."""
        resp = client.post("/api/assets/asset_000001/use")
        assert resp.status_code == 200

        data = resp.json()
        assert data["success"] is True

        # Verify use_count incremented
        resp = client.get("/api/assets/asset_000001")
        assert resp.json()["use_count"] == 1

    def test_mark_nonexistent_used(self, client):
        """POST /api/assets/{bad_id}/use returns 404."""
        resp = client.post("/api/assets/asset_999999/use")
        assert resp.status_code == 404

    def test_delete_asset_registry_only(self, client):
        """DELETE /api/assets/{id} removes from registry only (default)."""
        resp = client.delete("/api/assets/asset_000001")
        assert resp.status_code == 200

        data = resp.json()
        assert data["success"] is True
        assert data["registry_deleted"] is True
        assert data["cloudinary_deleted"] is False

    def test_delete_asset_with_cloud(self, client, app_and_services):
        """DELETE /api/assets/{id}?delete_from_cloud=true also deletes from Cloudinary."""
        resp = client.delete("/api/assets/asset_000001?delete_from_cloud=true")
        assert resp.status_code == 200

        data = resp.json()
        assert data["success"] is True
        assert data["cloudinary_deleted"] is True
        assert data["registry_deleted"] is True

    def test_empty_registry(self, tmp_path):
        """Empty registry should return empty lists."""
        empty_reg = AssetRegistry(data_dir=str(tmp_path / "empty"))
        assets_set_deps(cloudinary_service=FakeCloudinaryService(), asset_registry=empty_reg)

        app = FastAPI(title="Empty Test", version="1.0.0-test")
        app.include_router(assets_router)

        client = TestClient(app)
        resp = client.get("/api/assets")
        assert resp.json()["total"] == 0

    def test_pagination(self, client):
        """Pagination should work with limit and offset."""
        resp = client.get("/api/assets?limit=1&offset=0")
        data = resp.json()
        assert len(data["assets"]) == 1
        assert data["total"] == 2

        resp = client.get("/api/assets?limit=1&offset=1")
        data = resp.json()
        assert len(data["assets"]) == 1
