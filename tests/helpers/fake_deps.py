"""Lightweight test doubles for production dependencies.

These are REAL objects with REAL methods — NOT unittest.mock objects.
They return canned data configured per test. This follows the PDCA working
agreement: "No unittest.mock" — use real lightweight implementations.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any


class FakeResponse:
    """A real response object that mimics curl_cffi response shape."""

    def __init__(self, status_code: int = 200, content: bytes = b""):
        self.status_code = status_code
        self.content = content
        self.headers: dict[str, str] = {}
        self.text: str = content.decode("utf-8", errors="replace") if content else ""

    def json(self) -> Any:
        import json
        return json.loads(self.text) if self.text else {}


class FakeSession:
    """A real session object that records calls and returns canned responses."""

    def __init__(self, get_response: Any = None):
        self._get_response = get_response or FakeResponse()
        self.get_calls: list[dict] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.get_calls.append({"url": url, **kwargs})
        return self._get_response


class FakeClient:
    """Lightweight real client that returns configured responses.

    Usage:
        client = FakeClient()
        client.post_responses = [
            {"request_tokens": ["tok123"], "family": "test"},
            {"creation": {"id": "42"}},
        ]
        result = client.post("/api/start-tti-v2")  # returns first response
    """

    def __init__(self, xsrf_token: str | None = "fake-token"):
        self._xsrf_token = xsrf_token
        self.post_responses: list[Any] = []
        self.get_responses: list[Any] = []
        self.post_form_responses: list[Any] = []
        self._post_call_count = 0
        self._get_call_count = 0
        self._post_form_call_count = 0
        self.post_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.post_form_calls: list[dict] = []

    @property
    def xsrf_token(self) -> str | None:
        return self._xsrf_token

    @xsrf_token.setter
    def xsrf_token(self, value: str | None):
        self._xsrf_token = value

    @property
    def session(self) -> FakeSession:
        """Provide a session-like object for direct session.get() calls."""
        if not hasattr(self, "_session"):
            self._session = FakeSession()
        return self._session

    @session.setter
    def session(self, value):
        self._session = value

    def post(self, path: str, json_data: dict | None = None,
             headers: dict | None = None, **kwargs) -> Any:
        self._post_call_count += 1
        self.post_calls.append({"path": path, "json_data": json_data, "headers": headers, **kwargs})
        if self.post_responses:
            return self.post_responses[self._post_call_count - 1] if self._post_call_count <= len(self.post_responses) else self.post_responses[-1]
        return {}

    def get(self, path: str, **kwargs) -> Any:
        self._get_call_count += 1
        self.get_calls.append({"path": path, **kwargs})
        if self.get_responses:
            return self.get_responses[self._get_call_count - 1] if self._get_call_count <= len(self.get_responses) else self.get_responses[-1]
        return {}

    def post_form(self, path: str, form_data: dict | None = None,
                  files: dict | None = None, **kwargs) -> Any:
        self._post_form_call_count += 1
        self.post_form_calls.append({"path": path, "form_data": form_data, "files": files, **kwargs})
        if self.post_form_responses:
            return self.post_form_responses[self._post_form_call_count - 1] if self._post_form_call_count <= len(self.post_form_responses) else self.post_form_responses[-1]
        return {}

    def download(self, url: str, output_path: str) -> str:
        return output_path

    def close(self):
        pass


class FakePoller:
    """Lightweight real poller that returns configured responses.

    Usage:
        poller = FakePoller()
        poller.poll_result = {"download_url": "https://example.com/img.png"}
        result = poller.poll_creation("42", creation_type="image")
    """

    def __init__(self, poll_interval: int = 5, poll_timeout: int = 180):
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.poll_result: dict[str, Any] = {}
        self.poll_calls: list[dict] = []

    def poll_creation(self, creation_id: str, creation_type: str = "image") -> dict:
        self.poll_calls.append({"creation_id": creation_id, "creation_type": creation_type})
        return self.poll_result

    def poll_creation_stream(self, creation_id: str, creation_type: str = "image"):
        """Sync generator — yields poll_result as a single event."""
        yield {"status": "completed", "elapsed": 0.1, "data": self.poll_result}

    async def async_poll_creation_stream(
        self, creation_id: str, creation_type: str = "image"
    ) -> AsyncGenerator[dict, None]:
        """Async generator — yields poll_result as a single event."""
        yield {"status": "completed", "elapsed": 0.1, "data": self.poll_result}

    def poll_image_by_family(self, creation_id: str, family: str) -> dict:
        return self.poll_result

    def download_file(self, url: str, output_path: str) -> str:
        return output_path


class FakeMonitor:
    """Lightweight real monitor that returns configured responses.

    Usage:
        monitor = FakeMonitor()
        monitor.queue_status_result = {"queued": 2, "processing": 1, ...}
        result = monitor.get_queue_status()
    """

    def __init__(self):
        self.queue_status_result: dict[str, Any] = {
            "queued": 0, "processing": 0,
            "queued_items": [], "processing_items": [],
            "total_active": 0, "checked_at": "",
        }
        self.list_creations_result: dict[str, Any] = {"data": [], "meta": {"total": 0}}
        self.creation_detail_result: dict[str, Any] = {}
        self.active_creations_result: list[dict] = []
        self.stats_result: dict[str, Any] = {
            "counts": {}, "total": 0, "checked_at": "",
        }
        self.limits_result: dict[str, Any] = {}
        self.get_queue_status_calls: int = 0
        self.list_creations_calls: int = 0
        self.get_creation_calls: list[str | int] = []
        self.get_active_creations_calls: int = 0
        self.get_stats_calls: int = 0
        self.get_limits_calls: int = 0

    def get_queue_status(self) -> dict:
        self.get_queue_status_calls += 1
        return self.queue_status_result

    def list_creations(self, status=None, page=1, per_page=10, sort="-createdAt") -> dict:
        self.list_creations_calls += 1
        return self.list_creations_result

    def get_creation(self, creation_id: str | int) -> dict:
        self.get_creation_calls.append(creation_id)
        return self.creation_detail_result

    def get_active_creations(self) -> list[dict]:
        self.get_active_creations_calls += 1
        return self.active_creations_result

    def get_stats(self) -> dict:
        self.get_stats_calls += 1
        return self.stats_result

    def get_limits(self) -> dict:
        self.get_limits_calls += 1
        return self.limits_result

    async def async_get_queue_status(self) -> dict:
        return self.get_queue_status()

    async def async_list_creations(self, **kwargs) -> dict:
        return self.list_creations(**kwargs)

    async def async_get_creation(self, creation_id: str | int) -> dict:
        return self.get_creation(creation_id)

    async def async_get_stats(self) -> dict:
        return self.get_stats()

    async def async_get_limits(self) -> dict:
        return self.get_limits()


class FakeUploader:
    """Lightweight real uploader that returns configured responses.

    Usage:
        uploader = FakeUploader()
        uploader.upload_temporal_result = {"path": "temp-files/abc123.jpg"}
        result = uploader.upload_temporal(base64_data="data:image/png;base64,...")
    """

    def __init__(self):
        self.upload_temporal_result: dict[str, Any] = {"path": "temp-files/test.jpg"}
        self.upload_frame_result: dict[str, Any] = {"frameUrl": "https://example.com/frame.jpg"}
        self.upload_reference_frame_result: str = "https://example.com/frame.jpg"
        self.upload_video_audio_result: dict[str, Any] = {"path": "temp-files/video.mp4"}
        self.upload_calls: list[dict] = []

    def upload_temporal(self, file_path: str | None = None,
                        base64_data: str | None = None,
                        filename: str = "reference.jpg") -> dict:
        self.upload_calls.append({"method": "upload_temporal", "file_path": file_path,
                                  "base64_data": base64_data, "filename": filename})
        return self.upload_temporal_result

    def upload_frame(self, image_base64: str | None = None,
                     file_path: str | None = None,
                     frame_type: str = "frame") -> dict:
        self.upload_calls.append({"method": "upload_frame", "image_base64": image_base64,
                                  "file_path": file_path, "frame_type": frame_type})
        return self.upload_frame_result

    def upload_start_frame(self, image_base64: str | None = None,
                           file_path: str | None = None) -> str:
        return self.upload_frame_result.get("startFrameUrl", "")

    def upload_end_frame(self, image_base64: str | None = None,
                         file_path: str | None = None) -> str:
        return self.upload_frame_result.get("endFrameUrl", "")

    def upload_reference_frame(self, image_base64: str | None = None,
                                file_path: str | None = None) -> str:
        self.upload_calls.append({"method": "upload_reference_frame",
                                  "image_base64": image_base64, "file_path": file_path})
        return self.upload_reference_frame_result

    def upload_video_audio(self, file_path: str) -> dict:
        self.upload_calls.append({"method": "upload_video_audio", "file_path": file_path})
        return self.upload_video_audio_result


class FakeQueueManager:
    """Lightweight real queue manager that returns configured responses.

    Usage:
        qm = FakeQueueManager()
        qm.clear_result = {"cleared": 2, "errors": 0, ...}
        result = qm.clear_external_queue()
    """

    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self.clear_result: dict[str, Any] = {
            "cleared": 0, "errors": 0, "skipped_ours": 0,
            "total_queued": 0, "enabled": enabled, "reason": "disabled",
            "cancelled_identifiers": [], "skipped_identifiers": [],
        }
        self.snapshot_result: dict[str, Any] = {
            "total_queued": 0, "ours_count": 0, "external_count": 0,
            "items": [], "auto_clear_enabled": enabled,
            "checked_at": "",
        }
        self.cancel_result: dict[str, Any] = {"success": True, "message": "Cancelled"}
        self.clear_external_queue_calls: int = 0
        self.cancel_creation_calls: list[str] = []
        self.get_queue_snapshot_calls: int = 0
        self.configure_calls: list[bool] = []

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def configure(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure_calls.append(enabled)

    def clear_external_queue(self) -> dict:
        self.clear_external_queue_calls += 1
        return self.clear_result

    def cancel_creation(self, identifier: str) -> dict:
        self.cancel_creation_calls.append(identifier)
        return self.cancel_result

    def get_queue_snapshot(self) -> dict:
        self.get_queue_snapshot_calls += 1
        return self.snapshot_result


class FakeCreationRegistry:
    """Lightweight real registry that tracks creation identifiers.

    Usage:
        reg = FakeCreationRegistry()
        reg._ours = {"abc123", "def456"}
        assert reg.is_ours("abc123")
    """

    def __init__(self):
        self._ours: set[str] = set()
        self.register_calls: list[tuple[str, dict | None]] = []
        self.unregister_calls: list[str] = []

    def register(self, identifier: str, metadata: dict | None = None) -> None:
        self._ours.add(identifier)
        self.register_calls.append((identifier, metadata))

    def is_ours(self, identifier: str) -> bool:
        return identifier in self._ours

    def unregister(self, identifier: str) -> None:
        self._ours.discard(identifier)
        self.unregister_calls.append(identifier)

    def list_all(self) -> list[dict]:
        return [{"identifier": i, "metadata": {}} for i in sorted(self._ours)]

    def count(self) -> int:
        return len(self._ours)

    def clear(self) -> None:
        self._ours.clear()


class FakeCloudinaryService:
    """Lightweight real Cloudinary test double — NOT a mock.

    Records calls and returns configurable responses.
    Disabled by default (is_enabled=False).

    Usage:
        svc = FakeCloudinaryService(enabled=True)
        svc.upload_result = {"url": "https://cloudinary.com/test/image.png", ...}
        result = svc.upload_from_url("https://cdn.example.com/img.png", "test/id")
    """

    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self.folder = "magnific-test"
        self.upload_from_url_result: dict[str, Any] = {
            "url": "https://res.cloudinary.com/test/magnific/image/model/id.png",
            "public_id": "magnific/image/model/id",
            "resource_type": "image",
            "bytes": 102400,
            "width": 1024,
            "height": 1024,
            "format": "png",
        }
        self.upload_from_bytes_result: dict[str, Any] = {}
        self.download_bytes_result: bytes = b"fake-image-data"
        self.download_as_base64_result: str = "data:image/png;base64,ZmFrZQ=="
        self.delete_result: dict[str, Any] = {"result": "ok", "public_id": ""}
        self.list_resources_result: dict[str, Any] = {"resources": [], "count": 0}
        self.upload_calls: list[dict] = []
        self.download_calls: list[str] = []
        self.delete_calls: list[dict] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def build_public_id(self, asset_type: str, model_slug: str,
                       creation_id: str, index: int = 0) -> str:
        return f"magnific-test/{asset_type}/{model_slug}/{creation_id}_{index}"

    def upload_from_url(self, url: str, public_id: str,
                        resource_type: str = "auto",
                        tags: list[str] | None = None,
                        context: dict | None = None) -> dict:
        self.upload_calls.append({
            "method": "upload_from_url", "url": url,
            "public_id": public_id, "resource_type": resource_type,
            "tags": tags, "context": context,
        })
        return self.upload_from_url_result

    def upload_from_bytes(self, data: bytes, public_id: str,
                         resource_type: str = "auto",
                         filename: str = "asset") -> dict:
        self.upload_calls.append({
            "method": "upload_from_bytes", "bytes": len(data),
            "public_id": public_id, "resource_type": resource_type,
        })
        return self.upload_from_bytes_result or self.upload_from_url_result

    def download_bytes(self, public_id: str) -> bytes:
        self.download_calls.append(public_id)
        return self.download_bytes_result

    def download_as_base64(self, public_id: str,
                          mime_type: str = "image/png") -> str:
        self.download_calls.append(public_id)
        return self.download_as_base64_result

    def delete(self, public_id: str, resource_type: str = "auto") -> dict:
        self.delete_calls.append({"public_id": public_id, "resource_type": resource_type})
        return self.delete_result

    def list_resources(self, prefix: str = "", resource_type: str = "image",
                      max_results: int = 30,
                      next_cursor: str | None = None) -> dict:
        return self.list_resources_result

    def is_cloudinary_url(self, url: str) -> bool:
        return "cloudinary.com" in (url or "")

    @staticmethod
    def extract_public_id_from_url(url: str) -> str | None:
        """Delegate to real CloudinaryService implementation."""
        if not url or "cloudinary.com" not in url:
            return None
        from core.cloudinary_service import CloudinaryService
        return CloudinaryService.extract_public_id_from_url(url)


class FakeAssetRegistry:
    """Lightweight real asset registry that records calls in-memory."""

    def __init__(self):
        self._assets: dict[str, Any] = {}
        self._id_counter = 0
        self.register_calls: list[dict] = []
        self.mark_used_calls: list[str] = []
        self.delete_calls: list[str] = []

    def register(self, **kwargs) -> Any:
        self._id_counter += 1
        asset_id = f"asset_{self._id_counter:06d}"
        record = type("Record", (), {
            "id": asset_id,
            **kwargs,
            "use_count": 0,
            "last_used_at": "",
            "to_dict": lambda: {**kwargs, "id": asset_id, "use_count": 0},
        })
        self._assets[asset_id] = record
        self.register_calls.append({"id": asset_id, **kwargs})
        return record

    def get(self, asset_id: str) -> Any:
        return self._assets.get(asset_id)

    def get_by_creation_id(self, creation_id: str) -> list:
        return [r for r in self._assets.values() if r.creation_id == creation_id]

    def get_by_cloudinary_url(self, url: str) -> Any:
        for r in self._assets.values():
            if getattr(r, "cloudinary_url", None) == url:
                return r
        return None

    def list_assets(self, **kwargs) -> list:
        return list(self._assets.values())

    def mark_used(self, asset_id: str) -> bool:
        self.mark_used_calls.append(asset_id)
        record = self._assets.get(asset_id)
        if record:
            record.use_count = getattr(record, "use_count", 0) + 1
            return True
        return False

    def delete(self, asset_id: str) -> bool:
        self.delete_calls.append(asset_id)
        if asset_id in self._assets:
            del self._assets[asset_id]
            return True
        return False

    def count(self, asset_type: str | None = None) -> int:
        if asset_type:
            return sum(1 for r in self._assets.values() if getattr(r, "asset_type", None) == asset_type)
        return len(self._assets)

    def stats(self) -> dict:
        return {
            "total": len(self._assets),
            "images": sum(1 for r in self._assets.values() if getattr(r, "asset_type", None) == "image"),
            "videos": sum(1 for r in self._assets.values() if getattr(r, "asset_type", None) == "video"),
            "total_bytes": sum(getattr(r, "bytes", 0) for r in self._assets.values()),
            "total_bytes_human": "1.0 MB",
            "total_uses": sum(getattr(r, "use_count", 0) for r in self._assets.values()),
            "model_breakdown": {},
        }
