"""Tests for QueueManager — smart queue clearing with ownership-awareness.

Called Shot Protocol:
    Each test documents: test name, behavior under test, expected failure reason.
    All tests use TDD RED-GREEN-REFACTOR discipline. No mocks — real objects only.

Test Sequencing:
    1. Degenerate/zero case: disabled manager → no-op
    2. Happy path: clear external items, skip ours
    3. Exception cases: API errors, processing status
    4. Edge cases: empty queue, all ours, configure toggle
"""

import pytest
from core.creation_registry import CreationRegistry
from core.queue_manager import QueueManager
from tests.helpers.fake_deps import FakeClient


def _make_registry_with_ours(*identifiers: str) -> CreationRegistry:
    """Helper: create registry with pre-registered identifiers."""
    reg = CreationRegistry()
    for ident in identifiers:
        reg.register(ident)
    return reg


class TestClearExternalQueue:
    """Tests for clear_external_queue() — the core smart-cancel logic."""

    # Called Shot 1: Disabled → no-op
    # Test: test_clear_external_queue_disabled_noop
    # Behavior: When enabled=False, clear does nothing and returns reason
    # Expected failure: ImportError (module doesn't exist)

    def test_clear_external_queue_disabled_noop(self):
        """Disabled manager → clear returns reason='disabled', cleared=0."""
        client = FakeClient()
        registry = CreationRegistry()
        manager = QueueManager(client, registry, enabled=False)
        result = manager.clear_external_queue()
        assert result["cleared"] == 0
        assert result["reason"] == "disabled"
        assert result["enabled"] is False
        assert len(client.post_calls) == 0  # No API calls made

    # Called Shot 2: Cancel non-registered, skip registered
    # Test: test_clear_external_queue_cancels_non_registered
    # Behavior: 3 queued (1 ours, 2 external) → cancels 2, skips 1
    # Expected failure: QueueManager.clear_external_queue not implemented

    def test_clear_external_queue_cancels_non_registered(self):
        """3 queued (1 ours, 2 external) → cancels 2 external, skips ours."""
        client = FakeClient()
        # Cancel API returns success for each call
        client.post_responses = [
            {"success": True, "message": "Cancelled"},
            {"success": True, "message": "Cancelled"},
        ]
        registry = _make_registry_with_ours("ours_001")
        manager = QueueManager(client, registry, enabled=True)

        # Simulate queued items from Magnific API
        client.get_responses = [{
            "data": [
                {"id": 101, "identifier": "ours_001", "status": "queued"},
                {"id": 102, "identifier": "ext_abc", "status": "queued"},
                {"id": 103, "identifier": "ext_def", "status": "queued"},
            ],
        }]

        result = manager.clear_external_queue()

        assert result["cleared"] == 2
        assert result["errors"] == 0
        assert result["skipped_ours"] == 1
        assert result["total_queued"] == 3
        # Verify cancel calls made for external items only
        assert len(client.post_calls) == 2
        cancel_ids = {call["json_data"]["identifier"] for call in client.post_calls}
        assert cancel_ids == {"ext_abc", "ext_def"}

    # Called Shot 3: All ours → skip all, cancel 0
    # Test: test_clear_external_queue_all_ours_skips_all
    # Behavior: When all queued items are registered → cancels nothing

    def test_clear_external_queue_all_ours_skips_all(self):
        """All queued items are ours → cancels 0, returns reason='all_ours'."""
        client = FakeClient()
        registry = _make_registry_with_ours("ours_001", "ours_002")
        manager = QueueManager(client, registry, enabled=True)

        client.get_responses = [{
            "data": [
                {"id": 101, "identifier": "ours_001", "status": "queued"},
                {"id": 102, "identifier": "ours_002", "status": "queued"},
            ],
        }]

        result = manager.clear_external_queue()

        assert result["cleared"] == 0
        assert result["skipped_ours"] == 2
        assert result["reason"] == "all_ours"
        assert len(client.post_calls) == 0  # No cancels

    # Called Shot 4: Empty queue
    # Test: test_clear_external_queue_empty_queue
    # Behavior: No queued items → cancels 0

    def test_clear_external_queue_empty_queue(self):
        """No queued items → cancels 0."""
        client = FakeClient()
        registry = CreationRegistry()
        manager = QueueManager(client, registry, enabled=True)

        client.get_responses = [{"data": []}]

        result = manager.clear_external_queue()

        assert result["cleared"] == 0
        assert result["total_queued"] == 0
        assert len(client.post_calls) == 0

    # Called Shot 5: Partial cancel errors
    # Test: test_clear_external_queue_api_error_partial
    # Behavior: Some cancels fail → errors counted, others succeed

    def test_clear_external_queue_api_error_partial(self):
        """Some cancels fail (500 error) → errors counted, others succeed."""
        client = FakeClient()
        client.post_responses = [
            {"success": True, "message": "Cancelled"},
            Exception("API Error 500"),  # This cancel fails
            {"success": True, "message": "Cancelled"},
        ]
        registry = CreationRegistry()
        manager = QueueManager(client, registry, enabled=True)

        client.get_responses = [{
            "data": [
                {"id": 201, "identifier": "ext_a", "status": "queued"},
                {"id": 202, "identifier": "ext_b", "status": "queued"},
                {"id": 203, "identifier": "ext_c", "status": "queued"},
            ],
        }]

        result = manager.clear_external_queue()

        assert result["cleared"] == 2
        assert result["errors"] == 1
        assert result["total_queued"] == 3


class TestCancelCreation:
    """Tests for cancel_creation() — single item cancellation."""

    # Called Shot 6: Successful cancel
    # Test: test_cancel_creation_success
    # Behavior: Calls client.post with correct body

    def test_cancel_creation_success(self):
        """Cancel a creation → correct POST body, returns success."""
        client = FakeClient()
        client.post_responses = [{"success": True, "message": "Cancelled"}]
        registry = CreationRegistry()
        manager = QueueManager(client, registry, enabled=True)

        result = manager.cancel_creation("ext_abc")

        assert result["success"] is True
        assert len(client.post_calls) == 1
        assert client.post_calls[0]["path"] == "/api/creations/cancel"
        assert client.post_calls[0]["json_data"]["identifier"] == "ext_abc"


class TestQueueSnapshot:
    """Tests for get_queue_snapshot() — queue classification with ownership."""

    # Called Shot 7: Classify ours vs external
    # Test: test_get_queue_snapshot_classifies_ours_external
    # Behavior: Returns items with is_ours flag

    def test_get_queue_snapshot_classifies_ours_external(self):
        """Queue snapshot classifies items as ours/external."""
        client = FakeClient()
        registry = _make_registry_with_ours("ours_001")
        manager = QueueManager(client, registry, enabled=True)

        client.get_responses = [{
            "data": [
                {"id": 101, "identifier": "ours_001", "status": "queued",
                 "metadata": {"model": "nano-banana-2"}},
                {"id": 102, "identifier": "ext_abc", "status": "queued",
                 "metadata": {"model": "kling-2.0"}},
            ],
        }]

        result = manager.get_queue_snapshot()

        assert result["total_queued"] == 2
        assert result["ours_count"] == 1
        assert result["external_count"] == 1
        items = result["items"]
        assert items[0]["is_ours"] is True
        assert items[1]["is_ours"] is False


class TestConfigure:
    """Tests for configure() — enable/disable toggle."""

    # Called Shot 8: Toggle enabled state
    # Test: test_configure_enable_disable
    # Behavior: configure() toggles is_enabled property

    def test_configure_enable_disable(self):
        """configure(True) enables, configure(False) disables."""
        client = FakeClient()
        registry = CreationRegistry()
        manager = QueueManager(client, registry, enabled=False)

        assert manager.is_enabled is False

        manager.configure(True)
        assert manager.is_enabled is True

        manager.configure(False)
        assert manager.is_enabled is False
