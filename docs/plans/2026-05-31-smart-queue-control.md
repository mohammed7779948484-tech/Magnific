# PLAN: Smart Queue Control System

> PDCA Cycle 6 — Plan Phase
> Date: 2026-05-31
> Author: AI Technical Expert
> Status: PENDING DO

---

## 1. Goal

Build a smart queue control system that automatically clears competing operations from the account queue before submitting new generations through our project. The system tracks which creations were submitted by our project (vs. by other users on the same shared account) and only cancels external operations — never our own. This ensures our project's generations get processed first when competing with other users on the account, while preserving the natural ordering of our own queued work.

---

## 2. Context & Findings

### 2.1 Magnific Cancel API (Confirmed via agent-browser)

| Endpoint | Method | Body | Response | Status |
|---|---|---|---|---|
| `/api/creations/cancel` | POST | `{"identifier": "l7mHl6sgv9"}` | `{"success": true, "message": "Generation cancelled successfully"}` | ✅ Tested & Confirmed |
| `/api/creations/cancel` | POST | `{"identifier": "processing_id"}` | `{"error": "Can only cancel queued generations or delayed processing generations"}` | ✅ Confirmed (400) |
| `/api/creations?status=queued` | GET | — | Paginated list of queued creations | ✅ Tested & Confirmed |
| `/api/creations?status=processing` | GET | — | Paginated list of processing creations | ✅ Tested & Confirmed |
| `/api/creations?status=delayed_processing` | GET | — | Paginated list of delayed creations | ✅ Tested & Confirmed |

### 2.2 Cancel Behavior Rules

- **Can cancel**: `queued` and `delayed_processing` statuses
- **Cannot cancel**: `processing` (already being processed by Magnific servers)
- **No batch cancel**: Must cancel one at a time by `identifier` (string)
- **No reorder/priority/fast-track**: These endpoints do NOT exist

### 2.3 Queue Architecture

Magnific processes ~8 concurrent generations. When all 8 slots are occupied, new submissions enter a FIFO queue with position tracking. The account supports multiple users (shared account), so operations from different sources can coexist in the same queue.

### 2.4 The Problem

When multiple users share the same Magnific account:
1. User A submits 5 video generations via the web UI → they enter the queue
2. Our project submits an image generation → it goes to position 6+ in the queue
3. Our generation waits behind User A's operations unnecessarily

### 2.5 The Solution

Before each generation submission from our project:
1. Fetch all currently queued creations (`GET /api/creations?status=queued`)
2. Identify which queued creations are ours (tracked in `CreationRegistry`)
3. Cancel all queued creations that are NOT ours
4. Submit our new generation → it becomes first in the cleared queue

**Critical rule**: If ALL queued creations are from our project, do NOT cancel anything. Our own queue order is valid and should be preserved.

---

## 3. Architecture

### 3.1 New Files

| File | Purpose |
|---|---|
| `core/queue_manager.py` | `QueueManager` class — smart queue clearing with ownership tracking |
| `core/creation_registry.py` | `CreationRegistry` class — in-memory tracking of project-originated creations |
| `api/routes/queue.py` | FastAPI router — queue control endpoints (cancel, inspect, configure) |
| `api/schemas/queue_schemas.py` | Pydantic schemas for queue operations |
| `tests/test_queue_manager.py` | Tests for QueueManager core logic |
| `tests/test_creation_registry.py` | Tests for CreationRegistry tracking |
| `tests/test_queue_routes.py` | Tests for queue control HTTP endpoints |

### 3.2 Modified Files

| File | Change |
|---|---|
| `api/server.py` | Register queue router + inject QueueManager and CreationRegistry into deps |
| `api/routes/image.py` | Hook `QueueManager.clear_external_queue()` before generation submission |
| `api/routes/video.py` | Hook `QueueManager.clear_external_queue()` before generation submission |
| `config/endpoints.py` | Add `CREATIONS_CANCEL = "/api/creations/cancel"` constant |
| `tests/helpers/fake_deps.py` | Add `FakeQueueManager` and `FakeCreationRegistry` classes |
| `core/monitor.py` | Add `cancel_creation()` and `list_queued_creations()` methods |

### 3.3 Design Decisions

1. **In-memory creation tracking (not persistent)**: The registry lives in process memory. On restart, all creations are treated as "external" (safe default — won't cancel anything). This follows the principle of minimal side effects.

2. **Opt-in queue clearing**: Queue clearing is OFF by default. Must be explicitly enabled via config or API. This prevents accidental cancellation of other users' work.

3. **Cancel before submit, not after**: We clear the queue BEFORE calling `start-tti-v2` / `render/v4`, not after. This ensures our creation enters an empty queue.

4. **Identifier-based tracking**: We track creation `identifier` (string like `"l7mHl6sgv9"`), not `id` (numeric). The cancel API requires `identifier`, and it's available immediately from the creation response.

5. **Reuse existing MagnificClient**: QueueManager uses the same authenticated client. The `cancel_creation()` method calls `client.post()`.

6. **Zero mocks in tests**: Following PDCA working agreements — all tests use FakeClient/FakeQueueManager/FakeCreationRegistry.

7. **Graceful degradation**: If queue clearing fails (network error, API change), log a warning and proceed with generation. Queue clearing is a best-effort optimization, not a hard requirement.

### 3.4 Dependency Flow

```
MagnificClient (existing)
    ├── POST /api/creations/cancel
    └── GET  /api/creations?status=queued
         │
         ▼
CreationRegistry (new — in-memory set of our creation identifiers)
    ├── register(identifier)      — called after successful submission
    ├── is_ours(identifier)       — check if creation is from our project
    ├── unregister(identifier)    — called after completion/failure
    ├── list_all()               — all tracked identifiers
    └── count()                  — number of tracked creations
         │
         ▼
QueueManager (new — orchestrates smart queue clearing)
    ├── clear_external_queue()           — fetch queued, cancel non-ours
    ├── cancel_creation(identifier)      — delegate to client.post
    ├── get_queue_snapshot()              — fetch queued + our/external classification
    └── is_enabled                       — on/off toggle
         │
         ▼
queue_router (new — 5 endpoints)
    ├── POST /api/queue/clear           — manually trigger queue clearing
    ├── GET  /api/queue/status          — queue snapshot with ownership tags
    ├── POST /api/queue/cancel/{id}      — cancel a specific queued creation
    ├── POST /api/queue/configure       — enable/disable auto-clearing
    └── GET  /api/queue/registry         — view tracked creations
```

### 3.5 Integration Points

The queue clearing hook integrates into the existing generation flow at a specific point:

```
Image Generation Flow (modified):
  1. Validate request
  2. ★ NEW: QueueManager.clear_external_queue() ← HERE
  3. start-tti-v2 → get request_token + family
  4. render/v4 → get creation_id + identifier
  5. ★ NEW: CreationRegistry.register(identifier)
  6. Poll for completion
  7. ★ NEW: CreationRegistry.unregister(identifier) on completion/failure
  8. Return result
```

---

## 4. Core Classes

### 4.1 CreationRegistry

```python
class CreationRegistry:
    """In-memory registry of creations submitted by our project.
    
    Tracks creation identifiers to distinguish our operations from
    external operations when deciding what to cancel from the queue.
    Thread-safe via threading.Lock.
    """
    
    def __init__(self):
        self._creations: dict[str, dict] = {}  # identifier -> metadata
        self._lock = threading.Lock()
    
    def register(self, identifier: str, metadata: dict | None = None) -> None
    def is_ours(self, identifier: str) -> bool
    def unregister(self, identifier: str) -> None
    def list_all(self) -> list[dict]
    def count(self) -> int
    def clear(self) -> None
```

**Key behavior:**
- `register()` stores the identifier with optional metadata (creation_id, tool, model, timestamp)
- `is_ours()` returns True only for explicitly registered identifiers
- `unregister()` removes after completion — keeps registry lean
- Thread-safe for concurrent access

### 4.2 QueueManager

```python
class QueueManager:
    """Smart queue management with ownership-aware clearing.
    
    Fetches the current queue from Magnific, classifies items as
    "ours" (registered) or "external" (not registered), and cancels
    external items to prioritize our generations.
    """
    
    def __init__(self, client: MagnificClient, registry: CreationRegistry, enabled: bool = False):
        self.client = client
        self.registry = registry
        self._enabled = enabled
    
    def clear_external_queue(self) -> dict
    def cancel_creation(self, identifier: str) -> dict
    def get_queue_snapshot(self) -> dict
    @property
    def is_enabled(self) -> bool
    def configure(self, enabled: bool) -> None
```

**Key behavior:**
- `clear_external_queue()` is the main method:
  1. Fetch all queued creations
  2. For each: if `registry.is_ours(identifier)` → skip, else → cancel
  3. Return summary of what was cancelled and what was skipped
  4. If `_enabled` is False → no-op (returns empty result)
- `cancel_creation()` wraps `client.post("/api/creations/cancel", {"identifier": ...})`
- `get_queue_snapshot()` returns queued items classified as ours/external

### 4.3 Smart Cancel Decision Tree

```
clear_external_queue():
  if NOT enabled → return {cleared: 0, skipped: 0, reason: "disabled"}

  queued = GET /api/creations?status=queued&per_page=100
  our_items = [c for c in queued if registry.is_ours(c.identifier)]
  external_items = [c for c in queued if NOT registry.is_ours(c.identifier)]

  if NOT external_items:
    return {cleared: 0, skipped: 0, our_count: len(our_items), reason: "all ours"}

  cancelled = 0
  errors = 0
  for item in external_items:
    try:
      client.post("/api/creations/cancel", {"identifier": item.identifier})
      cancelled += 1
    except:
      errors += 1

  return {cleared, errors, our_count: len(our_items), external_count: len(external_items)}
```

---

## 5. API Specification

### 5.1 POST /api/queue/clear

Manually trigger smart queue clearing (cancels all non-registered queued creations).

**Response:**
```json
{
  "success": true,
  "enabled": true,
  "cleared": 3,
  "errors": 0,
  "skipped_ours": 2,
  "total_queued": 5,
  "details": {
    "cancelled_identifiers": ["abc123", "def456", "ghi789"],
    "skipped_identifiers": ["ours_001", "ours_002"]
  },
  "timestamp": "2026-05-31T03:30:00Z"
}
```

### 5.2 GET /api/queue/status

Queue snapshot with ownership classification for each item.

**Response:**
```json
{
  "total_queued": 5,
  "ours": 2,
  "external": 3,
  "items": [
    {
      "id": 123,
      "identifier": "ours_001",
      "tool": "text-to-image",
      "model": "nano-banana-2",
      "position": 1,
      "is_ours": true,
      "created_at": "..."
    },
    {
      "id": 456,
      "identifier": "ext_abc",
      "tool": "video-generator",
      "model": "kling-2.0",
      "position": 2,
      "is_ours": false,
      "created_at": "..."
    }
  ],
  "processing_slots": 8,
  "processing_count": 3,
  "auto_clear_enabled": true,
  "checked_at": "2026-05-31T03:30:00Z"
}
```

### 5.3 POST /api/queue/cancel/{identifier}

Cancel a specific queued creation by its identifier.

**Response:**
```json
{
  "success": true,
  "identifier": "ext_abc",
  "message": "Generation cancelled successfully"
}
```

### 5.4 POST /api/queue/configure

Enable or disable automatic queue clearing before generation.

**Body:**
```json
{
  "auto_clear": true
}
```

**Response:**
```json
{
  "auto_clear": true,
  "message": "Automatic queue clearing enabled. Non-project queued creations will be cancelled before each generation."
}
```

### 5.5 GET /api/queue/registry

View all creations tracked by the project registry.

**Response:**
```json
{
  "count": 4,
  "creations": [
    {
      "identifier": "ours_001",
      "creation_id": 3071049939,
      "tool": "text-to-image",
      "model": "nano-banana-2",
      "registered_at": "2026-05-31T03:25:00Z",
      "status": "active"
    }
  ]
}
```

---

## 6. Implementation Steps (TDD)

### Step 1: CreationRegistry — core/creation_registry.py

**Test First:**
- `test_registry_register_and_check` — register identifier, verify `is_ours()` returns True
- `test_registry_not_registered_returns_false` — unregistered identifier returns False
- `test_registry_unregister` — register then unregister, verify `is_ours()` returns False
- `test_registry_list_all` — register multiple, verify list returns all with metadata
- `test_registry_count` — verify count matches registered items
- `test_registry_clear` — clear all, verify count is 0
- `test_registry_duplicate_register_overwrites` — register same identifier twice, keeps latest metadata
- `test_registry_empty_string_not_registered` — empty/None identifiers are ignored

**Implementation:**
- Thread-safe dict with `threading.Lock`
- `register(identifier, metadata=None)` → stores in dict
- `is_ours(identifier)` → True/False
- `unregister(identifier)` → removes from dict
- `list_all()` → list of `{identifier, metadata}`
- `count()` → len
- `clear()` → empty dict

**Acceptance Criteria:**
- Thread-safe for concurrent access
- Empty string and None identifiers rejected silently
- Metadata is optional (defaults to empty dict)

### Step 2: QueueManager — core/queue_manager.py

**Test First:**
- `test_clear_external_queue_cancels_non_registered` — 3 queued, 1 ours, 2 external → cancels 2, skips 1
- `test_clear_external_queue_all_ours_skips_all` — 3 queued, all ours → cancels 0
- `test_clear_external_queue_disabled_noop` — enabled=False → cancels 0, returns reason
- `test_clear_external_queue_empty_queue` — no queued items → cancels 0
- `test_cancel_creation_success` — calls client.post with correct body
- `test_cancel_creation_not_found` — 404 error handled gracefully
- `test_cancel_creation_already_processing` — 400 error handled gracefully
- `test_get_queue_snapshot_classifies_ours_external` — returns items with `is_ours` flag
- `test_configure_enable_disable` — toggle enabled state
- `test_clear_external_queue_api_error_partial` — some cancels fail, returns error count

**Implementation:**
- `QueueManager.__init__(client, registry, enabled=False)`
- `clear_external_queue()` → fetch queued, filter, cancel external, return summary
- `cancel_creation(identifier)` → `client.post()`
- `get_queue_snapshot()` → fetch + classify
- `is_enabled` property
- `configure(enabled)` → set state

**Acceptance Criteria:**
- All methods use `self.client.get()` or `self.client.post()`
- API errors during cancel are caught and counted (not raised)
- Returns structured dict with counts and details
- Respects `enabled` flag

### Step 3: Monitor Extension — core/monitor.py modifications

**Test First:**
- `test_monitor_cancel_creation` — verify correct POST body to cancel endpoint
- `test_monitor_list_queued_creations` — verify fetches with status=queued
- `test_monitor_cancel_handles_400` — processing status returns error dict
- `test_monitor_cancel_handles_404` — not found returns error dict

**Implementation:**
- Add `cancel_creation(identifier: str) -> dict` → `self.client.post("/api/creations/cancel", {"identifier": identifier})`
- Add `list_queued_creations(per_page=100) -> list[dict]` → `self.client.get("/api/creations", params={"status": "queued", "per_page": per_page})`

**Acceptance Criteria:**
- Existing 9 monitor tests still pass
- No changes to existing method signatures

### Step 4: Queue Schemas — api/schemas/queue_schemas.py

**Test First:**
- `test_queue_clear_response_schema` — valid/invalid data validation
- `test_queue_item_with_ownership_schema` — is_ours flag required
- `test_queue_configure_request_schema` — auto_clear must be boolean
- `test_registry_item_schema` — required fields validation

**Implementation:**
- `QueueItemWithOwnership(QueueItem)` — adds `is_ours: bool` and `identifier: str`
- `QueueClearResponse` — cleared, errors, skipped_ours, total_queued, details, timestamp
- `QueueStatusResponse` — total_queued, ours, external, items, processing_count, auto_clear_enabled
- `QueueCancelResponse` — success, identifier, message
- `QueueConfigureRequest` — auto_clear: bool
- `QueueConfigureResponse` — auto_clear, message
- `RegistryItem` — identifier, creation_id, tool, model, registered_at
- `RegistryResponse` — count, creations

### Step 5: Queue Routes — api/routes/queue.py

**Test First:**
- `test_queue_clear_endpoint` — POST /api/queue/clear returns correct structure
- `test_queue_status_endpoint` — GET /api/queue/status with is_ours classification
- `test_queue_cancel_specific_endpoint` — POST /api/queue/cancel/{identifier}
- `test_queue_configure_endpoint` — POST /api/queue/configure toggles auto_clear
- `test_queue_registry_endpoint` — GET /api/queue/registry shows tracked creations
- `test_queue_no_deps_503` — Returns 503 when deps not injected
- `test_queue_clear_disabled_returns_info` — When disabled, clear returns informative message

**Implementation:**
- Router with prefix `/api/queue`
- `set_deps(queue_manager, creation_registry)` for DI
- All endpoints use `asyncio.to_thread`
- Proper error handling

### Step 6: Integration with Image Route — api/routes/image.py

**Test First:**
- `test_image_generate_clears_external_queue_when_enabled` — with FakeQueueManager, verify clear_external_queue called before start-tti-v2
- `test_image_generate_registers_creation_after_submit` — verify register called with creation identifier after render/v4
- `test_image_generate_unregisters_on_completion` — verify unregister called after poll completes
- `test_image_generate_skips_clear_when_disabled` — when auto_clear=False, no clearing occurs

**Implementation:**
- Inject `QueueManager` and `CreationRegistry` via `set_deps()`
- Before `start-tti-v2`: call `queue_manager.clear_external_queue()` (if enabled)
- After `render/v4`: call `registry.register(identifier)` with creation identifier
- After poll completes/fails: call `registry.unregister(identifier)`
- Extract `identifier` from `render_result.get("creation", {}).get("identifier")` or fallback

### Step 7: Integration with Video Route — api/routes/video.py

**Test First:**
- `test_video_generate_clears_external_queue_when_enabled`
- `test_video_generate_registers_creation_after_submit`
- `test_video_generate_unregisters_on_completion`

**Implementation:**
- Same pattern as image route integration
- Extract identifier from video generation response

### Step 8: Server Integration — api/server.py

**Test First:**
- `test_queue_router_registered` — Verify queue routes accessible via app
- `test_queue_deps_injected_at_startup` — Verify QueueManager and CreationRegistry created

**Implementation:**
- Import and include queue_router
- Create `CreationRegistry()` in lifespan
- Create `QueueManager(client, registry, enabled=False)` in lifespan
- Call `queue_set_deps(queue_manager, creation_registry)` during startup

### Step 9: Config & Endpoints

**Test First:**
- `test_cancel_endpoint_constant` — Verify CREATIONS_CANCEL path defined

**Implementation:**
- Add to `config/endpoints.py`:
  - `CREATIONS_CANCEL = "/api/creations/cancel"`

### Step 10: FakeQueueManager & FakeCreationRegistry — tests/helpers/fake_deps.py

**Implementation:**
- `FakeCreationRegistry` — mirrors real registry with configurable state
- `FakeQueueManager` — mirrors real queue manager with configurable behavior
- Both track method calls for verification

---

## 7. Testing Strategy

### 7.1 Zero Mocks Policy (PDCA Working Agreement)

- Use `FakeClient`, `FakeQueueManager`, `FakeCreationRegistry`
- Test doubles are real lightweight objects with deterministic behavior
- All HTTP error codes tested via exception raising in test doubles

### 7.2 Test Categories

| Category | Count | Description |
|---|---|---|
| CreationRegistry | 8 | Register, unregister, check, thread safety |
| QueueManager Core | 10 | Clear, cancel, snapshot, configure |
| Monitor Extension | 4 | Cancel creation, list queued |
| Schemas | 4 | Pydantic validation |
| Queue Routes | 7 | HTTP endpoints, status codes |
| Image Integration | 4 | Hook verification |
| Video Integration | 3 | Hook verification |
| Server | 2 | Router registration, dep injection |
| Config | 1 | Endpoint constants |
| **Total New** | **43** | |

### 7.3 Regression Guard

- All 122 existing tests must still pass
- Total expected: 122 + 43 = **165 tests**

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Magnific removes cancel API | Low | High | QueueManager catches errors gracefully, auto-clear can be disabled |
| Cancel API rate limiting | Medium | Low | Sequential cancels with 200ms delay between requests |
| Registry lost on restart (in-memory) | High | Low | Safe default — treats all as external on restart |
| Cancel race condition (item starts processing) | Medium | Low | API returns 400, caught and counted as error |
| Accidental cancel of user's work | Low | High | Auto-clear is OFF by default; manual clear shows preview |
| Image/video routes broken by hooks | Low | High | QueueManager/clearing is optional and fails silently |
| Identifier not in render/v4 response | Medium | Low | Fallback to creation_id; register gracefully if no identifier found |

---

## 9. Files Summary

### New Files (7)

1. `core/creation_registry.py` — ~80 lines
2. `core/queue_manager.py` — ~120 lines
3. `api/routes/queue.py` — ~150 lines
4. `api/schemas/queue_schemas.py` — ~80 lines
5. `tests/test_creation_registry.py` — ~120 lines
6. `tests/test_queue_manager.py` — ~200 lines
7. `tests/test_queue_routes.py` — ~250 lines

### Modified Files (6)

1. `api/server.py` — Add ~15 lines (import + register + inject)
2. `api/routes/image.py` — Add ~20 lines (hooks before/after generation)
3. `api/routes/video.py` — Add ~20 lines (hooks before/after generation)
4. `config/endpoints.py` — Add ~1 line (cancel constant)
5. `core/monitor.py` — Add ~25 lines (cancel_creation + list_queued)
6. `tests/helpers/fake_deps.py` — Add ~80 lines (FakeQueueManager + FakeCreationRegistry)

### Total Estimated LOC: ~800 lines (new) + ~161 lines (modified)

---

## 10. Success Criteria

1. All 43 new tests pass
2. All 122 existing tests still pass
3. Zero mocks in any test
4. Auto-clear is OFF by default
5. Manual queue clear shows preview before canceling
6. Image/video routes register creations in the registry
7. Image/video routes unregister on completion
8. External queue clearing works when enabled
9. No breaking changes to existing endpoints
10. Server starts and serves all routes on port 8090

---

## 11. Dependency Order

```
Step 1: CreationRegistry (no deps)
Step 2: QueueManager (depends on Step 1)
Step 3: Monitor extension (no new deps, extends existing)
Step 4: Schemas (no deps)
Step 5: Queue Routes (depends on Steps 2, 4)
Step 6: Image integration (depends on Steps 2, 5)
Step 7: Video integration (depends on Steps 2, 5)
Step 8: Server integration (depends on Steps 5, 6, 7)
Step 9: Config (no deps)
Step 10: Test helpers (depends on Steps 1, 2)
```

**Parallelizable**: Steps 1 + 3 + 4 + 9 can be done in parallel.
