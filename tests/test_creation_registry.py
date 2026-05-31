"""Tests for CreationRegistry — in-memory tracking of project-originated creations.

Called Shot Protocol:
    Each test documents: test name, behavior under test, expected failure reason.
    All tests use TDD RED-GREEN-REFACTOR discipline. No mocks — real objects only.

Test Sequencing:
    1. Degenerate/zero case: empty registry returns False
    2. Happy path: register, check, unregister
    3. Exception cases: empty/None identifiers
    4. Edge cases: duplicate register, clear, count, list
"""

import pytest
from core.creation_registry import CreationRegistry


# ─── Called Shot 1: Degenerate/zero case ───────────────────────────────────
# Test: test_registry_not_registered_returns_false
# Behavior: Unregistered identifier returns False from is_ours()
# Expected failure: ImportError (module doesn't exist yet)

class TestRegistryRegisterAndCheck:
    """Tests for register(), is_ours(), and unregister() core behavior."""

    def test_registry_not_registered_returns_false(self):
        """Empty registry — is_ours() returns False for any identifier."""
        registry = CreationRegistry()
        assert registry.is_ours("nonexistent_id") is False

    # Called Shot 2: Happy path — register then check
    # Test: test_registry_register_and_check
    # Behavior: Register an identifier, is_ours() returns True
    # Expected failure: If registry exists but method missing → AttributeError

    def test_registry_register_and_check(self):
        """Register identifier → is_ours() returns True."""
        registry = CreationRegistry()
        registry.register("abc123")
        assert registry.is_ours("abc123") is True

    # Called Shot 3: Register then unregister
    # Test: test_registry_unregister
    # Behavior: After unregister, is_ours() returns False
    # Expected failure: If unregister not implemented → AttributeError

    def test_registry_unregister(self):
        """Register then unregister → is_ours() returns False."""
        registry = CreationRegistry()
        registry.register("abc123")
        registry.unregister("abc123")
        assert registry.is_ours("abc123") is False

    # Called Shot 4: Unregister nonexistent — no crash
    # Test: test_registry_unregister_nonexistent_no_error
    # Behavior: Unregistering a non-registered identifier is a silent no-op
    # Expected failure: If unregister raises → test fails

    def test_registry_unregister_nonexistent_no_error(self):
        """Unregistering nonexistent identifier doesn't raise."""
        registry = CreationRegistry()
        registry.unregister("nonexistent")  # Should not raise
        assert registry.count() == 0

    # Called Shot 5: Register with metadata
    # Test: test_registry_register_with_metadata
    # Behavior: Metadata is stored alongside the identifier
    # Expected failure: If metadata not stored → KeyError or None

    def test_registry_register_with_metadata(self):
        """Register with metadata → list_all() returns metadata."""
        registry = CreationRegistry()
        registry.register("abc123", metadata={"model": "nano-banana-2", "tool": "image"})
        items = registry.list_all()
        assert len(items) == 1
        assert items[0]["identifier"] == "abc123"
        assert items[0]["metadata"]["model"] == "nano-banana-2"

    # Called Shot 6: Duplicate register overwrites
    # Test: test_registry_duplicate_register_overwrites
    # Behavior: Registering same identifier twice keeps latest metadata
    # Expected failure: If not overwriting → stale metadata returned

    def test_registry_duplicate_register_overwrites(self):
        """Duplicate register → latest metadata wins, count stays 1."""
        registry = CreationRegistry()
        registry.register("abc123", metadata={"v": 1})
        registry.register("abc123", metadata={"v": 2})
        assert registry.count() == 1
        items = registry.list_all()
        assert items[0]["metadata"]["v"] == 2


class TestRegistryEdgeCases:
    """Tests for edge cases: empty string, None, clear, count, list."""

    # Called Shot 7: Empty/None identifiers are ignored
    # Test: test_registry_empty_string_not_registered
    # Behavior: register("") and register(None) are silently ignored
    # Expected failure: If no validation → count increases

    def test_registry_empty_string_not_registered(self):
        """Empty string and None identifiers are silently rejected."""
        registry = CreationRegistry()
        registry.register("")
        registry.register(None)  # type: ignore[arg-type]
        assert registry.count() == 0
        assert registry.is_ours("") is False

    # Called Shot 8: list_all on empty registry
    # Test: test_registry_list_all_empty
    # Behavior: list_all() returns empty list when no items registered
    # Expected failure: Should pass if list_all returns []

    def test_registry_list_all_empty(self):
        """Empty registry → list_all() returns empty list."""
        registry = CreationRegistry()
        assert registry.list_all() == []

    # Called Shot 9: Count accuracy
    # Test: test_registry_count
    # Behavior: count() returns exact number of registered items
    # Expected failure: If count logic wrong → mismatch

    def test_registry_count(self):
        """count() matches number of registered identifiers."""
        registry = CreationRegistry()
        assert registry.count() == 0
        registry.register("a")
        assert registry.count() == 1
        registry.register("b")
        assert registry.count() == 2
        registry.unregister("a")
        assert registry.count() == 1

    # Called Shot 10: Clear all
    # Test: test_registry_clear
    # Behavior: clear() removes all registered items
    # Expected failure: If clear doesn't empty → count > 0

    def test_registry_clear(self):
        """clear() removes all items, count becomes 0."""
        registry = CreationRegistry()
        registry.register("a")
        registry.register("b")
        registry.register("c")
        assert registry.count() == 3
        registry.clear()
        assert registry.count() == 0
        assert registry.is_ours("a") is False
