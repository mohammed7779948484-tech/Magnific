# PLAN: Magnific Monitoring Endpoints System

> PDCA Cycle 5 — Plan Phase
> Date: 2026-05-31
> Author: AI Technical Expert
> Status: PENDING DO

---

## 1. Goal

Build a professional monitoring system that provides real-time visibility into the Magnific account's active generations, queue positions, credit consumption, and creation history. The system leverages Magnific's internal `GET /api/creations` API (with status filtering, pagination, and rich metadata) to expose a clean REST interface for external monitoring dashboards and automation tools.

---

## 2. Context & Findings

### 2.1 Magnific Internal API (Discovered)

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/creations?status=processing` | GET | Yes | Currently generating jobs |
| `/api/creations?status=queued` | GET | Yes | Queued jobs (with position, expectedQueuedTime, expectedGenerationTime) |
| `/api/creations?status=completed` | GET | Yes | Completed jobs |
| `/api/creations?status=failed` | GET | Yes | Failed jobs |
| `/api/creations?status=cancelled` | GET | Yes | Cancelled jobs |
| `/api/creation/{id}` | GET | Yes | Single creation detail (flattened) |
| `/api/v2/ai-models` | GET | No | Full model catalog (138 models) |
| `/api/video/ai-models` | GET | No | Video models grouped by provider |
| `/api/limits` | GET | Yes | User limits/quotas |
| `/api/creations/stats` | GET | Yes | Statistics endpoint |

### 2.2 Pagination (Laravel-style)

- `per_page` + `page` — Primary pagination
- Response includes `meta: {total, current_page, last_page, per_page}` and `links: {first, last, prev, next}`
- Also accepts: `limit`/`offset`, `pageSize`, `skip`/`take`

### 2.3 Sorting

- `sort=createdAt` / `sort=-createdAt` (descending)
- `order=desc` / `order=asc`
- `orderBy=createdAt`

### 2.4 Metadata Structure (per creation)

```json
{
  "id": 123456,
  "status": "queued|processing|completed|failed|cancelled",
  "tool": "text-to-image|video-generator|upscaler",
  "url": "https://pikaso.cdnpk.net/...",
  "created_at": "2026-01-30T...",
  "date_for_humans": "2 hours ago",
  "metadata": {
    "model": "imagen-nano-banana-2",
    "position": 1,
    "fast_track": false,
    "multiplier": 1,
    "expectedQueuedTime": 30,
    "expectedGenerationTime": 45,
    "creditLedgerTotals": { ... },
    "prompt": "a red apple...",
    "aspectRatio": "1:1",
    "resolution": "2k",
    "width": 2048,
    "height": 2048,
    "family": "bytedance"
  }
}
```

### 2.5 Key Insight

Magnific has NO rate limit — it uses internal queueing. ~8 concurrent requests processed simultaneously, excess requests enter an internal queue with position tracking and expected wait times. Our local rate limiter (20 req/min) is sufficient to prevent connection pressure.

---

## 3. Architecture

### 3.1 New Files

| File | Purpose |
|---|---|
| `core/monitor.py` | `MagnificMonitor` class — wraps all creations API calls |
| `api/routes/monitor.py` | FastAPI router — 7 monitoring endpoints |
| `api/schemas/monitor_schemas.py` | Pydantic schemas for requests/responses |
| `tests/test_monitor_route.py` | Full test coverage (no mocks, real patterns) |

### 3.2 Modified Files

| File | Change |
|---|---|
| `api/server.py` | Register monitor router + inject Monitor into deps |
| `config/endpoints.py` | Add monitoring endpoint constants |
| `api/routes/__init__.py` | Export monitor router (optional) |

### 3.3 Design Decisions

1. **No caching layer** — Magnific's data changes in real-time; caching would introduce staleness. All requests go directly to Magnific API.
2. **No queue management** — User explicitly said: no need for our own queue, just monitoring.
3. **Reuse existing MagnificClient** — The monitor uses the same authenticated HTTP session as the rest of the app.
4. **Zero mocks in tests** — Following PDCA working agreements: test real behavior, not mock behavior.
5. **SSE streaming** — Monitor stream polls all active creations and emits events when status changes.
6. **Minimal changes to existing code** — Follow PDCA working agreement #1 (prioritize minimal changes).

### 3.4 Dependency Injection Pattern

Follow existing project pattern:
```python
# api/routes/monitor.py
_client: MagnificClient | None = None
_monitor: MagnificMonitor | None = None

def set_deps(client: MagnificClient, monitor: MagnificMonitor):
    global _client, _monitor
    _client = client
    _monitor = monitor
```

### 3.5 Class Diagram

```
MagnificClient (existing)
    ├── GET /api/creations?status=...&per_page=...&page=...
    ├── GET /api/creation/{id}
    ├── GET /api/v2/ai-models
    └── GET /api/limits
         |
         v
MagnificMonitor (new)
    ├── get_queue_status() -> QueueOverview
    ├── list_creations(status, page, per_page, sort) -> PaginatedCreations
    ├── get_creation(id) -> CreationDetail
    ├── get_stats() -> MonitorStats
    ├── get_limits() -> AccountLimits
    └── get_active_creations() -> list[CreationSummary]
         |
         v
monitor_router (new -- 7 endpoints)
    ├── GET /api/monitor/queue
    ├── GET /api/monitor/creations
    ├── GET /api/monitor/creations/{id}
    ├── GET /api/monitor/stats
    ├── GET /api/monitor/stream
    ├── GET /api/monitor/limits
    └── GET /api/monitor/health
```

---

## 4. API Specification

### 4.1 GET /api/monitor/queue

Returns a snapshot of the current queue state: how many items are processing, queued, and recently completed.

**Response:**
```json
{
  "processing": 3,
  "queued": 5,
  "queued_items": [
    {
      "id": 123,
      "tool": "text-to-image",
      "model": "imagen-nano-banana-2",
      "position": 1,
      "expected_queued_time": 30,
      "expected_generation_time": 45,
      "prompt": "a sunset...",
      "created_at": "2026-01-30T10:00:00Z",
      "date_for_humans": "5 minutes ago"
    }
  ],
  "processing_items": [
    {
      "id": 456,
      "tool": "video-generator",
      "model": "seedance-2.0",
      "prompt": "a cat dancing...",
      "expected_generation_time": 212,
      "created_at": "2026-01-30T09:50:00Z",
      "date_for_humans": "15 minutes ago"
    }
  ],
  "total_active": 8,
  "checked_at": "2026-01-30T10:05:00Z"
}
```

### 4.2 GET /api/monitor/creations

Paginated list of creations with optional filters.

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `status` | str | None | Filter by status: processing, queued, completed, failed, cancelled |
| `page` | int | 1 | Page number |
| `per_page` | int | 10 | Items per page (max 50) |
| `sort` | str | "-createdAt" | Sort field: createdAt, -createdAt |

**Response:**
```json
{
  "data": [
    {
      "id": 123,
      "status": "completed",
      "tool": "text-to-image",
      "model": "imagen-nano-banana-2",
      "prompt": "a sunset...",
      "url": "https://pikaso.cdnpk.net/...",
      "created_at": "2026-01-30T10:00:00Z",
      "date_for_humans": "5 minutes ago",
      "credits_used": {},
      "resolution": "2k",
      "aspect_ratio": "1:1",
      "width": 2048,
      "height": 2048
    }
  ],
  "meta": {
    "total": 150,
    "current_page": 1,
    "last_page": 15,
    "per_page": 10
  }
}
```

### 4.3 GET /api/monitor/creations/{creation_id}

Detailed view of a single creation.

**Response:** Full creation object from Magnific API.

### 4.4 GET /api/monitor/stats

Aggregate statistics across all creations.

**Response:**
```json
{
  "counts": {
    "processing": 3,
    "queued": 5,
    "completed": 142,
    "failed": 3,
    "cancelled": 2
  },
  "total": 155,
  "models_used": {
    "imagen-nano-banana-2": 45,
    "seedance-2.0": 30,
    "flux-2-pro": 25
  },
  "tools_used": {
    "text-to-image": 100,
    "video-generator": 55
  },
  "recent_failures": [
    {
      "id": 789,
      "error": "Generation failed",
      "model": "gpt-2",
      "created_at": "..."
    }
  ],
  "checked_at": "2026-01-30T10:05:00Z"
}
```

### 4.5 GET /api/monitor/stream

SSE stream that monitors all active (processing + queued) creations and emits events when their status changes.

**Events:**
```
event: status_change
data: {"id": 123, "old_status": "queued", "new_status": "processing", "position": null}

event: completed
data: {"id": 456, "url": "https://...", "model": "imagen-nano-banana-2"}

event: failed
data: {"id": 789, "error": "Generation failed"}

event: heartbeat
data: {"active_count": 8, "timestamp": "..."}
```

### 4.6 GET /api/monitor/limits

Account limits and credit information from /api/limits.

### 4.7 GET /api/monitor/health

Quick health check for the monitor subsystem — verifies client is available and Magnific is reachable.

---

## 5. Implementation Steps (TDD)

### Step 1: core/monitor.py -- MagnificMonitor Class

**Test First:**
- `test_monitor_get_queue_status` — Verifies correct parsing of queued + processing items
- `test_monitor_list_creations_with_pagination` — Verifies pagination params passed correctly
- `test_monitor_list_creations_with_status_filter` — Verifies status filter
- `test_monitor_get_creation_detail` — Verifies single creation fetch
- `test_monitor_get_active_creations` — Verifies combining processing + queued
- `test_monitor_get_stats` — Verifies aggregation of counts across statuses

**Implementation:**
- `MagnificMonitor.__init__(client: MagnificClient)`
- `get_queue_status() -> dict` — Fetches queued + processing, extracts metadata
- `list_creations(status=None, page=1, per_page=10, sort="-createdAt") -> dict`
- `get_creation(creation_id: str | int) -> dict`
- `get_active_creations() -> list[dict]` — Processing + queued combined
- `get_stats() -> dict` — Counts per status, models used, tools used, recent failures
- `get_limits() -> dict` — Account limits

**Acceptance Criteria:**
- All methods use `self.client.get()` (never raw requests)
- Parameters are passed as query params to the API
- Response is returned as-is (no transformation in core layer)

### Step 2: api/schemas/monitor_schemas.py -- Pydantic Models

**Test First:**
- `test_queue_overview_schema_validation` — Valid/invalid data
- `test_creation_summary_schema` — Required fields validation
- `test_monitor_stats_schema` — Counts structure validation
- `test_pagination_params_schema` — Bounds validation (per_page max 50, page min 1)

**Implementation:**
- `QueueItem` — creation in queue with position/time fields
- `ProcessingItem` — creation being processed
- `QueueOverview` — full queue snapshot
- `CreationSummary` — flattened creation for list view
- `MonitorStats` — aggregate statistics
- `PaginationParams` — validated query parameters
- `PaginatedResponse[T]` — generic paginated response with meta

**Acceptance Criteria:**
- All schemas use Pydantic v2
- Optional fields have sensible defaults
- Validation messages are clear

### Step 3: api/routes/monitor.py -- 7 Monitoring Endpoints

**Test First:**
- `test_monitor_queue_endpoint` — GET /api/monitor/queue returns correct structure
- `test_monitor_creations_endpoint` — GET /api/monitor/creations with filters
- `test_monitor_creation_detail_endpoint` — GET /api/monitor/creations/{id}
- `test_monitor_stats_endpoint` — GET /api/monitor/stats
- `test_monitor_stream_endpoint` — GET /api/monitor/stream yields SSE events
- `test_monitor_health_endpoint` — GET /api/monitor/health
- `test_monitor_limits_endpoint` — GET /api/monitor/limits
- `test_monitor_no_client_503` — Returns 503 when deps not injected
- `test_monitor_creations_pagination_validation` — per_page > 50 returns 422
- `test_monitor_invalid_status_filter` — Invalid status returns 422

**Implementation:**
- Router with prefix `/api/monitor`
- `set_deps(client, monitor)` for dependency injection
- All endpoints use `asyncio.to_thread` for sync client calls
- SSE stream uses `async_poll_active_creations_stream()` method
- Proper error handling with typed HTTP responses

**Acceptance Criteria:**
- All 7 endpoints return correct status codes
- 422 for invalid query parameters
- 503 when dependencies not available
- SSE stream sends heartbeat every 15 seconds
- All endpoints follow existing project patterns

### Step 4: Server Integration

**Test First:**
- `test_monitor_router_registered` — Verify monitor routes are accessible via the app
- `test_monitor_deps_injected_at_startup` — Verify Monitor is created during lifespan

**Implementation:**
- Import and include monitor_router in `create_app()`
- Create `MagnificMonitor` instance in lifespan
- Call `monitor_set_deps(client, monitor)` during startup
- Add to `__init__.py` exports (optional)

**Acceptance Criteria:**
- Monitor endpoints accessible at `/api/monitor/*`
- Monitor uses the same MagnificClient as image/video routes
- No breaking changes to existing endpoints

### Step 5: Config & Endpoints

**Test First:**
- `test_monitor_endpoint_constants` — Verify all endpoint paths are defined

**Implementation:**
- Add to `config/endpoints.py`:
  - `CREATIONS_LIST = "/api/creations"` (already exists)
  - `CREATION_DETAIL` (already exists)
  - `AI_MODELS` (already exists)
  - `ACCOUNT_LIMITS = "/api/limits"`

**Acceptance Criteria:**
- All endpoint paths are constants in one place
- No hardcoded URLs in monitor or route code

### Step 6: Final Integration Tests

- `test_full_monitor_workflow` — Queue -> List -> Detail -> Stats
- `test_monitor_concurrent_access` — Multiple concurrent monitor requests
- `test_monitor_error_handling` — Magnific 401/429/500 mapped correctly
- Run full test suite: all 98+ existing tests still pass + new tests

---

## 6. Testing Strategy

### 6.1 Zero Mocks Policy (PDCA Working Agreement)

Following the project's established pattern (98 tests, zero mocks):
- Use `tests/helpers/create_test_app.py` to create test FastAPI apps
- Use `tests/helpers/fake_deps.py` for dependency injection with test doubles
- Test doubles are NOT mocks — they are real classes that return deterministic data
- All HTTP error codes tested via exception raising in test doubles

### 6.2 Test Categories

| Category | Count | Description |
|---|---|---|
| Core (monitor.py) | 6 | MagnificMonitor methods |
| Schemas | 4 | Pydantic validation |
| Routes | 10 | HTTP endpoints, status codes, validation |
| Integration | 3 | Full workflow, concurrency, errors |
| Server | 2 | Router registration, dep injection |
| **Total** | **25** | New tests |

### 6.3 Called Shot Protocol (PDCA DO)

Before every test:
1. State the test name
2. State the behavior under test
3. State the expected failure reason

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Magnific API changes response structure | Low | High | Monitor returns raw API data; schemas handle optional fields |
| /api/limits endpoint doesn't exist or returns 404 | Medium | Low | Handle gracefully, return "unavailable" status |
| /api/creations/stats endpoint doesn't exist | Medium | Low | Build stats from individual status queries instead |
| SSE stream causes memory leak | Low | Medium | Use proper async generators with cleanup |
| Concurrent monitor requests overload Magnific | Low | Low | Local rate limiter already protects this |

---

## 8. Files Summary

### New Files (4)

1. `core/monitor.py` -- ~120 lines
2. `api/routes/monitor.py` -- ~200 lines
3. `api/schemas/monitor_schemas.py` -- ~100 lines
4. `tests/test_monitor_route.py` -- ~350 lines

### Modified Files (2)

1. `api/server.py` -- Add ~10 lines (import + register + inject)
2. `config/endpoints.py` -- Add ~3 lines (limits constant)

### Total Estimated LOC: ~780 lines (new) + ~13 lines (modified)

---

## 9. Success Criteria

1. All 25 new tests pass
2. All 98 existing tests still pass
3. Zero mocks in any test
4. All 7 monitor endpoints return correct responses
5. SSE stream sends heartbeats and status change events
6. No breaking changes to existing image/video/status endpoints
7. Server starts and serves all routes on port 8090
