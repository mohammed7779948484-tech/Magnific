"""Tests for api/schemas/monitor_schemas.py.

Called Shots:
1. test_queue_overview_schema_validation — Valid QueueOverview data passes
2. test_creation_summary_schema — CreationSummary with all optional fields
3. test_monitor_stats_schema — MonitorStats with counts
4. test_pagination_bounds — per_page > 50 raises ValidationError

No unittest.mock usage. Tests validate Pydantic schema behavior.
"""

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Called Shot 1: QueueOverview validation
# ---------------------------------------------------------------------------

def test_queue_overview_schema_validation():
    """QueueOverview should accept valid data with all fields."""
    from api.schemas.monitor_schemas import QueueOverview

    data = {
        "queued": 3,
        "processing": 1,
        "queued_items": [
            {
                "id": 101,
                "tool": "text-to-image",
                "model": "imagen-nano-banana-2",
                "position": 1,
                "expected_queued_time": 30,
                "expected_generation_time": 45,
                "prompt": "a sunset",
                "created_at": "2026-01-30T10:00:00Z",
                "date_for_humans": "5 min ago",
            }
        ],
        "processing_items": [],
        "total_active": 4,
        "checked_at": "2026-01-30T10:05:00Z",
    }
    overview = QueueOverview(**data)
    assert overview.queued == 3
    assert overview.processing == 1
    assert overview.total_active == 4
    assert len(overview.queued_items) == 1
    assert overview.queued_items[0].position == 1


# ---------------------------------------------------------------------------
# Called Shot 2: CreationSummary schema
# ---------------------------------------------------------------------------

def test_creation_summary_schema():
    """CreationSummary should handle optional fields gracefully."""
    from api.schemas.monitor_schemas import CreationSummary

    # Minimal data
    minimal = CreationSummary(id=1, status="completed")
    assert minimal.id == 1
    assert minimal.tool is None
    assert minimal.url is None

    # Full data
    full = CreationSummary(
        id=42,
        status="queued",
        tool="text-to-image",
        model="imagen-nano-banana-2",
        prompt="a cat",
        url="https://example.com/img.png",
        created_at="2026-01-30T10:00:00Z",
        date_for_humans="5 min ago",
        resolution="2k",
        aspect_ratio="1:1",
        width=2048,
        height=2048,
    )
    assert full.model == "imagen-nano-banana-2"
    assert full.resolution == "2k"


# ---------------------------------------------------------------------------
# Called Shot 3: MonitorStats schema
# ---------------------------------------------------------------------------

def test_monitor_stats_schema():
    """MonitorStats should accept counts dict and total."""
    from api.schemas.monitor_schemas import MonitorStats

    stats = MonitorStats(
        counts={"processing": 2, "queued": 5, "completed": 100, "failed": 3, "cancelled": 1},
        total=111,
        checked_at="2026-01-30T10:05:00Z",
    )
    assert stats.counts["queued"] == 5
    assert stats.total == 111


# ---------------------------------------------------------------------------
# Called Shot 4: Pagination bounds validation
# ---------------------------------------------------------------------------

def test_pagination_bounds():
    """per_page > 50 should raise ValidationError."""
    from api.schemas.monitor_schemas import PaginationParams

    with pytest.raises(ValidationError):
        PaginationParams(per_page=51)

    # per_page = 50 should be fine
    params = PaginationParams(per_page=50)
    assert params.per_page == 50

    # page < 1 should raise
    with pytest.raises(ValidationError):
        PaginationParams(page=0)

    # page = 1 should be fine
    params = PaginationParams(page=1)
    assert params.page == 1


# ---------------------------------------------------------------------------
# Called Shot 5: MonitorHealthResponse schema
# ---------------------------------------------------------------------------

def test_monitor_health_schema():
    """MonitorHealthResponse should default to 'ok' status."""
    from api.schemas.monitor_schemas import MonitorHealthResponse

    health = MonitorHealthResponse()
    assert health.status == "ok"

    health_down = MonitorHealthResponse(status="error", detail="client not available")
    assert health_down.status == "error"
