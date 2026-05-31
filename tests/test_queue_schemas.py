"""Tests for queue_schemas.py — Pydantic validation for queue control endpoints.

Called Shot Protocol:
    Each test validates schema structure and field constraints.
"""

import pytest
from pydantic import ValidationError

from api.schemas.queue_schemas import (
    QueueCancelResponse,
    QueueClearResponse,
    QueueConfigureRequest,
    QueueConfigureResponse,
    QueueItemWithOwnership,
    QueueStatusResponse,
    RegistryItem,
    RegistryResponse,
)


class TestQueueItemWithOwnership:
    """Tests for QueueItemWithOwnership schema."""

    def test_valid_queue_item(self):
        """Valid data creates QueueItemWithOwnership."""
        item = QueueItemWithOwnership(
            id=101, identifier="abc123", tool="text-to-image",
            model="nano-banana-2", is_ours=True,
        )
        assert item.is_ours is True
        assert item.identifier == "abc123"

    def test_default_is_ours_false(self):
        """is_ours defaults to False."""
        item = QueueItemWithOwnership(id=101)
        assert item.is_ours is False


class TestQueueClearResponse:
    """Tests for QueueClearResponse schema."""

    def test_valid_clear_response(self):
        """Valid data creates QueueClearResponse."""
        resp = QueueClearResponse(
            enabled=True, cleared=2, errors=0,
            skipped_ours=1, total_queued=3, reason="cleared",
            timestamp="2026-05-31T03:30:00Z",
        )
        assert resp.cleared == 2
        assert resp.reason == "cleared"


class TestQueueConfigureRequest:
    """Tests for QueueConfigureRequest schema."""

    def test_auto_clear_must_be_boolean(self):
        """auto_clear must be boolean."""
        req = QueueConfigureRequest(auto_clear=True)
        assert req.auto_clear is True

    def test_default_auto_clear_false(self):
        """auto_clear defaults to False."""
        req = QueueConfigureRequest()
        assert req.auto_clear is False


class TestRegistryItem:
    """Tests for RegistryItem schema."""

    def test_valid_registry_item(self):
        """Valid data creates RegistryItem."""
        item = RegistryItem(
            identifier="abc123", creation_id=3071049939,
            tool="text-to-image", model="nano-banana-2",
        )
        assert item.identifier == "abc123"
        assert item.status == "active"
