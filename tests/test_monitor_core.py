"""Tests for core/monitor.py — MagnificMonitor class.

Called Shots:
1. test_monitor_init — MagnificMonitor accepts a client parameter
2. test_monitor_get_queue_status — Fetches queued + processing, returns structured dict
3. test_monitor_list_creations_with_pagination — Passes per_page and page as query params
4. test_monitor_list_creations_with_status_filter — Passes status filter to API
5. test_monitor_get_creation_detail — Fetches single creation by ID
6. test_monitor_get_active_creations — Combines processing + queued into one list
7. test_monitor_get_stats — Aggregates counts per status
8. test_monitor_get_limits — Fetches account limits
9. test_monitor_client_propagation — All methods use self.client.get()

No unittest.mock usage. Tests use FakeClient from tests.helpers.
"""

import pytest

from tests.helpers.fake_deps import FakeClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_with_responses(get_responses: list) -> FakeClient:
    """Create a FakeClient pre-loaded with GET responses."""
    client = FakeClient(xsrf_token="fake-token")
    client.get_responses = get_responses
    return client


# ---------------------------------------------------------------------------
# Called Shot 1: MagnificMonitor init
# ---------------------------------------------------------------------------

def test_monitor_init():
    """MagnificMonitor should accept a client parameter and store it."""
    client = FakeClient(xsrf_token="fake-token")
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)
    assert monitor.client is client


# ---------------------------------------------------------------------------
# Called Shot 2: get_queue_status
# ---------------------------------------------------------------------------

def test_monitor_get_queue_status():
    """get_queue_status should fetch queued and processing items separately."""
    queued_response = {
        "data": [
            {
                "id": 101,
                "status": "queued",
                "tool": "text-to-image",
                "created_at": "2026-01-30T10:00:00Z",
                "date_for_humans": "5 minutes ago",
                "metadata": {
                    "position": 1,
                    "expectedQueuedTime": 30,
                    "expectedGenerationTime": 45,
                    "prompt": "a sunset",
                },
            }
        ],
    }
    processing_response = {
        "data": [
            {
                "id": 202,
                "status": "processing",
                "tool": "video-generator",
                "created_at": "2026-01-30T09:50:00Z",
                "date_for_humans": "15 minutes ago",
                "metadata": {
                    "expectedGenerationTime": 212,
                    "prompt": "a cat dancing",
                },
            }
        ],
    }

    client = _make_client_with_responses([queued_response, processing_response])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.get_queue_status()

    assert "queued" in result
    assert "processing" in result
    assert "queued_items" in result
    assert "processing_items" in result
    assert "total_active" in result
    assert result["queued"] == 1
    assert result["processing"] == 1
    assert result["total_active"] == 2
    assert len(result["queued_items"]) == 1
    assert result["queued_items"][0]["position"] == 1
    assert result["processing_items"][0]["expected_generation_time"] == 212


# ---------------------------------------------------------------------------
# Called Shot 3: list_creations with pagination
# ---------------------------------------------------------------------------

def test_monitor_list_creations_with_pagination():
    """list_creations should pass per_page and page as query params."""
    response = {
        "data": [{"id": 1, "status": "completed"}],
        "meta": {"total": 100, "current_page": 2, "last_page": 10, "per_page": 5},
    }

    client = _make_client_with_responses([response])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.list_creations(page=2, per_page=5)

    # Verify the API was called with correct params
    assert len(client.get_calls) == 1
    call = client.get_calls[0]
    assert call["path"] == "/api/creations"
    assert call["params"] == {"per_page": 5, "page": 2, "sort": "-createdAt"}
    assert result["meta"]["current_page"] == 2


# ---------------------------------------------------------------------------
# Called Shot 4: list_creations with status filter
# ---------------------------------------------------------------------------

def test_monitor_list_creations_with_status_filter():
    """list_creations should pass status filter to API."""
    response = {
        "data": [{"id": 1, "status": "failed"}],
        "meta": {"total": 3, "current_page": 1, "last_page": 1, "per_page": 10},
    }

    client = _make_client_with_responses([response])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.list_creations(status="failed")

    call = client.get_calls[0]
    assert call["params"]["status"] == "failed"
    assert result["data"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Called Shot 5: get_creation_detail
# ---------------------------------------------------------------------------

def test_monitor_get_creation_detail():
    """get_creation should fetch a single creation by ID."""
    creation = {
        "id": 42,
        "status": "completed",
        "tool": "text-to-image",
        "url": "https://example.com/img.png",
        "created_at": "2026-01-30T10:00:00Z",
        "metadata": {"prompt": "test"},
    }

    client = _make_client_with_responses([creation])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.get_creation(42)

    assert result["id"] == 42
    assert result["status"] == "completed"
    # Verify correct endpoint was called
    assert client.get_calls[0]["path"] == "/api/creation/42"


# ---------------------------------------------------------------------------
# Called Shot 6: get_active_creations
# ---------------------------------------------------------------------------

def test_monitor_get_active_creations():
    """get_active_creations should combine processing + queued into one list."""
    queued_response = {
        "data": [
            {"id": 10, "status": "queued"},
            {"id": 11, "status": "queued"},
        ],
    }
    processing_response = {
        "data": [
            {"id": 20, "status": "processing"},
        ],
    }

    client = _make_client_with_responses([queued_response, processing_response])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.get_active_creations()

    assert len(result) == 3
    ids = [c["id"] for c in result]
    assert 10 in ids
    assert 11 in ids
    assert 20 in ids


# ---------------------------------------------------------------------------
# Called Shot 7: get_stats
# ---------------------------------------------------------------------------

def test_monitor_get_stats():
    """get_stats should query each status and aggregate counts.

    Responses must match VALID_STATUSES iteration order:
    processing, queued, completed, failed, cancelled.
    """
    processing_resp = {"data": [{"id": 2}, {"id": 3}], "meta": {"total": 2}}
    queued_resp = {"data": [{"id": 1}], "meta": {"total": 5}}
    completed_resp = {"data": [{"id": 4}], "meta": {"total": 100}}
    failed_resp = {"data": [{"id": 5}], "meta": {"total": 3}}
    cancelled_resp = {"data": [], "meta": {"total": 1}}

    client = _make_client_with_responses([
        processing_resp, queued_resp, completed_resp, failed_resp, cancelled_resp,
    ])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.get_stats()

    assert "counts" in result
    assert result["counts"]["processing"] == 2
    assert result["counts"]["queued"] == 5
    assert result["counts"]["completed"] == 100
    assert result["counts"]["failed"] == 3
    assert result["counts"]["cancelled"] == 1
    assert result["total"] == 111


# ---------------------------------------------------------------------------
# Called Shot 8: get_limits
# ---------------------------------------------------------------------------

def test_monitor_get_limits():
    """get_limits should fetch /api/limits and return the response."""
    limits_data = {"credits": 500, "used": 120, "remaining": 380}
    client = _make_client_with_responses([limits_data])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.get_limits()

    assert result["credits"] == 500
    assert client.get_calls[0]["path"] == "/api/limits"


# ---------------------------------------------------------------------------
# Called Shot 9: client propagation
# ---------------------------------------------------------------------------

def test_monitor_client_propagation():
    """All MagnificMonitor methods should use self.client.get()."""
    client = FakeClient(xsrf_token="fake-token")
    client.get_responses = [
        {"data": []},  # get_queue_status — queued
        {"data": []},  # get_queue_status — processing
        {"data": [], "meta": {"total": 0}},  # list_creations
        {"id": 1},  # get_creation
        {"data": []},  # get_active — queued
        {"data": []},  # get_active — processing
        {"data": [], "meta": {"total": 0}},  # stats — queued
        {"data": [], "meta": {"total": 0}},  # stats — processing
        {"data": [], "meta": {"total": 0}},  # stats — completed
        {"data": [], "meta": {"total": 0}},  # stats — failed
        {"data": [], "meta": {"total": 0}},  # stats — cancelled
        {},  # limits
    ]

    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    monitor.get_queue_status()
    monitor.list_creations()
    monitor.get_creation(1)
    monitor.get_active_creations()
    monitor.get_stats()
    monitor.get_limits()

    # All 12 calls should have gone through client.get
    assert client._get_call_count == 12
    # All calls should have path starting with /api/
    for call in client.get_calls:
        assert call["path"].startswith("/api/")


# ---------------------------------------------------------------------------
# Called Shot 10: cancel_creation
# ---------------------------------------------------------------------------

def test_monitor_cancel_creation():
    """cancel_creation should POST to /api/creations/cancel with identifier."""
    client = FakeClient(xsrf_token="fake-token")
    client.post_responses = [
        {"success": True, "message": "Generation cancelled successfully"},
    ]
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.cancel_creation("l7mHl6sgv9")

    assert result["success"] is True
    assert len(client.post_calls) == 1
    assert client.post_calls[0]["path"] == "/api/creations/cancel"
    assert client.post_calls[0]["json_data"]["identifier"] == "l7mHl6sgv9"


# ---------------------------------------------------------------------------
# Called Shot 11: cancel_creation handles 400 (processing status)
# ---------------------------------------------------------------------------

def test_monitor_cancel_creation_handles_400():
    """cancel_creation with processing status returns error dict from API."""
    client = FakeClient(xsrf_token="fake-token")
    client.post_responses = [
        {"error": "Can only cancel queued generations or delayed processing generations"},
    ]
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.cancel_creation("processing_id")

    assert "error" in result
    assert len(client.post_calls) == 1


# ---------------------------------------------------------------------------
# Called Shot 12: list_queued_creations
# ---------------------------------------------------------------------------

def test_monitor_list_queued_creations():
    """list_queued_creations should fetch with status=queued."""
    response = {
        "data": [
            {"id": 101, "identifier": "abc123", "status": "queued"},
            {"id": 102, "identifier": "def456", "status": "queued"},
        ],
        "meta": {"total": 2, "current_page": 1, "last_page": 1, "per_page": 100},
    }
    client = _make_client_with_responses([response])
    from core.monitor import MagnificMonitor
    monitor = MagnificMonitor(client=client)

    result = monitor.list_queued_creations()

    assert len(result) == 2
    assert result[0]["identifier"] == "abc123"
    call = client.get_calls[0]
    assert call["path"] == "/api/creations"
    assert call["params"]["status"] == "queued"
    assert call["params"]["per_page"] == 100
