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
