"""Tests for queue routes — queue control HTTP endpoints.

Called Shot Protocol:
    Each test documents: test name, behavior, expected failure.
    All tests use TDD RED-GREEN-REFACTOR. No mocks — FakeQueueManager + FakeCreationRegistry.
"""

import pytest
from fastapi.testclient import TestClient

from api.schemas.queue_schemas import (
    QueueCancelResponse,
    QueueClearResponse,
    QueueConfigureResponse,
    QueueStatusResponse,
    RegistryResponse,
)
from tests.helpers.create_test_app import create_test_app
from tests.helpers.fake_deps import (
    FakeCreationRegistry,
    FakeQueueManager,
)


def _inject_queue_deps(qm: FakeQueueManager, reg: FakeCreationRegistry):
    """Inject queue deps into the queue route module."""
    from api.routes import queue as q_mod
    q_mod.set_deps(qm, reg)


def _app_with_queue(qm=None, reg=None):
    """Create test app with queue deps injected."""
    from tests.helpers.create_test_app import create_test_app
    from api.routes.queue import router as queue_router, set_deps as queue_set_deps

    qm = qm or FakeQueueManager(enabled=False)
    reg = reg or FakeCreationRegistry()

    app = create_test_app()
    app.include_router(queue_router)
    queue_set_deps(qm, reg)
    return app, qm, reg


# ─── Called Shot 1: POST /api/queue/clear ────────────────────────────────────
# Test: test_queue_clear_endpoint
# Behavior: POST /api/queue/clear triggers clear_external_queue and returns result
# Expected failure: 404 (route not registered yet)

class TestQueueClearEndpoint:
    """Tests for POST /api/queue/clear."""

    def test_queue_clear_endpoint(self):
        """POST /api/queue/clear returns clear result with counts."""
        qm = FakeQueueManager(enabled=True)
        qm.clear_result = {
            "cleared": 2, "errors": 0, "skipped_ours": 1,
            "total_queued": 3, "enabled": True, "reason": "cleared",
            "cancelled_identifiers": ["ext_a", "ext_b"],
            "skipped_identifiers": ["ours_001"],
        }
        app, _, _ = _app_with_queue(qm=qm)
        client = TestClient(app)

        resp = client.post("/api/queue/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] == 2
        assert data["errors"] == 0
        assert data["skipped_ours"] == 1
        assert qm.clear_external_queue_calls == 1

    def test_queue_clear_disabled_returns_info(self):
        """When disabled, clear returns informative message."""
        qm = FakeQueueManager(enabled=False)
        qm.clear_result = {
            "cleared": 0, "errors": 0, "skipped_ours": 0,
            "total_queued": 0, "enabled": False, "reason": "disabled",
            "cancelled_identifiers": [], "skipped_identifiers": [],
        }
        app, _, _ = _app_with_queue(qm=qm)
        client = TestClient(app)

        resp = client.post("/api/queue/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reason"] == "disabled"


# ─── Called Shot 2: GET /api/queue/status ────────────────────────────────────
# Test: test_queue_status_endpoint

class TestQueueStatusEndpoint:
    """Tests for GET /api/queue/status."""

    def test_queue_status_endpoint(self):
        """GET /api/queue/status returns queue snapshot with ownership."""
        qm = FakeQueueManager(enabled=True)
        qm.snapshot_result = {
            "total_queued": 3,
            "ours_count": 1,
            "external_count": 2,
            "items": [
                {"id": 101, "identifier": "ours_001", "is_ours": True},
                {"id": 102, "identifier": "ext_a", "is_ours": False},
            ],
            "auto_clear_enabled": True,
            "checked_at": "2026-05-31T03:30:00Z",
        }
        app, _, _ = _app_with_queue(qm=qm)
        client = TestClient(app)

        resp = client.get("/api/queue/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_queued"] == 3
        assert data["ours"] == 1
        assert data["external"] == 2
        assert qm.get_queue_snapshot_calls == 1


# ─── Called Shot 3: POST /api/queue/cancel/{identifier} ─────────────────────
# Test: test_queue_cancel_specific_endpoint

class TestQueueCancelSpecificEndpoint:
    """Tests for POST /api/queue/cancel/{identifier}."""

    def test_queue_cancel_specific_endpoint(self):
        """POST /api/queue/cancel/{identifier} cancels specific creation."""
        qm = FakeQueueManager(enabled=True)
        qm.cancel_result = {"success": True, "message": "Generation cancelled successfully"}
        app, _, _ = _app_with_queue(qm=qm)
        client = TestClient(app)

        resp = client.post("/api/queue/cancel/ext_abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["identifier"] == "ext_abc"
        assert qm.cancel_creation_calls == ["ext_abc"]


# ─── Called Shot 4: POST /api/queue/configure ───────────────────────────────
# Test: test_queue_configure_endpoint

class TestQueueConfigureEndpoint:
    """Tests for POST /api/queue/configure."""

    def test_queue_configure_endpoint(self):
        """POST /api/queue/configure toggles auto_clear."""
        qm = FakeQueueManager(enabled=False)
        app, _, _ = _app_with_queue(qm=qm)
        client = TestClient(app)

        resp = client.post("/api/queue/configure", json={"auto_clear": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_clear"] is True
        assert qm.configure_calls == [True]


# ─── Called Shot 5: GET /api/queue/registry ─────────────────────────────────
# Test: test_queue_registry_endpoint

class TestQueueRegistryEndpoint:
    """Tests for GET /api/queue/registry."""

    def test_queue_registry_endpoint(self):
        """GET /api/queue/registry shows tracked creations."""
        reg = FakeCreationRegistry()
        reg.register("abc123", metadata={"model": "nano-banana-2"})
        reg.register("def456")
        app, _, _ = _app_with_queue(reg=reg)
        client = TestClient(app)

        resp = client.get("/api/queue/registry")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["creations"]) == 2


# ─── Called Shot 6: No deps → 503 ───────────────────────────────────────────
# Test: test_queue_no_deps_503

class TestQueueNoDeps:
    """Tests for 503 when deps not injected."""

    def test_queue_no_deps_503(self):
        """Returns 503 when queue manager not injected."""
        # Create app without queue deps
        app = create_test_app()
        from api.routes.queue import router as queue_router
        # Reset queue module globals to simulate no deps
        import api.routes.queue as q_mod
        q_mod._queue_manager = None
        q_mod._registry = None
        app.include_router(queue_router)
        # Don't inject deps
        client = TestClient(app)

        resp = client.post("/api/queue/clear")
        assert resp.status_code == 503

        resp = client.get("/api/queue/status")
        assert resp.status_code == 503

        resp = client.get("/api/queue/registry")
        assert resp.status_code == 503
