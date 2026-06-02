# PDCA Plan — Cloudinary Cloud Storage V2 (Refactor & Fix)

**Date**: 2026-06-02
**PDCA Cycle**: 9
**Branch**: `feature/multi-account-smart-routing`
**Previous Commit**: `baa3131` (173 tests + 44 Cloudinary tests = 217 passing)
**Author**: Mohammed + AI Assistant

---

## PHASE 1: ANALYSIS & RESEARCH FINDINGS

### 1.1 Current Implementation Summary

| Layer | File | Status |
|-------|------|--------|
| Core Service | `core/cloudinary_service.py` (423 lines) | Needs Refactor |
| Asset Registry | `core/asset_registry.py` (410 lines) | Good, Minor Fixes |
| Assets API | `api/routes/assets.py` (171 lines) | Good, Minor Fixes |
| Image Route | `api/routes/image.py` | Needs Bug Fix |
| Video Route | `api/routes/video.py` | Needs Bug Fix |
| Server Init | `api/server.py` | Good |
| Tests | 44 tests across 3 files | Gaps Found |

### 1.2 Research Findings (Cloudinary Official Documentation)

| Topic | Finding | Impact on Implementation |
|-------|---------|--------------------------|
| **SDK Version** | Latest: `cloudinary==1.44.2` (2026-04-16), actively maintained | Update `requirements.txt` |
| **Configuration** | Supports `CLOUDINARY_URL` env var: `cloudinary://KEY:SECRET@CLOUD` | Add as alternative config method |
| **resource_type** | `resource_type="video"` is **MANDATORY** for video uploads or it FAILS | Already correct in code |
| **Chunked Uploads** | Built-in `upload_large()` for files >20MB, threshold 20MB | Should use for videos |
| **Eager Transformations** | Pre-process video derivatives at upload time | Future enhancement |
| **Upload Presets** | Unsigned presets for client-side uploads | Not needed (server-side only) |
| **Folder Structure** | Virtual folders — created by upload paths | Already correct |
| **Delete API** | `cloudinary.api.delete_resources()` + `invalidate=True` recommended | Missing `invalidate=True` |
| **Error Handling** | SDK has typed exceptions: `RateLimited`, `NotFound`, `BadRequest`, etc. | Not used — we wrap everything as `Exception` |
| **Rate Limits** | Headers in response: `x-featureratelimit-*` | Not monitored |
| **Retry Logic** | SDK has NO built-in retry — must implement manually | Not implemented |
| **Search API** | Fluent interface for advanced queries | Not used — we use Admin API `resources()` |
| **CloudinaryResource** | `CloudinaryImage` / `CloudinaryVideo` classes for URL building | Not used |

### 1.3 Issues Found (Critical to Low)

#### CRITICAL Issues (0)
None — the core logic is functionally correct.

#### HIGH Issues (3)

**H-1: No Retry Logic for Uploads/Downloads**
- Cloudinary SDK has NO built-in retry
- Network errors, rate limits (HTTP 429), and transient failures will cause uploads to silently fail
- Current code catches exception, logs warning, returns None — but never retries
- **Fix**: Add exponential backoff retry (3 attempts) for uploads, with specific handling for `RateLimited`

**H-2: Missing `invalidate=True` in Delete**
- When deleting assets from Cloudinary, CDN cache is not cleared
- The deleted resource may still be accessible via CDN for up to 24 hours
- **Fix**: Add `invalidate=True` to `cloudinary.api.delete_resources()` call

**H-3: `download_bytes()` Uses `urllib.request` Instead of Cloudinary SDK**
- `download_bytes()` manually constructs URL and uses `urllib.request.urlopen()`
- This bypasses Cloudinary's SDK URL building which handles signed URLs, transformations, etc.
- Should use `cloudinary.utils.cloudinary_url()` for consistent URL generation (already used, but urllib for download)
- **Note**: Cloudinary SDK doesn't have a built-in download method, so urllib is acceptable. But should use `requests` or `httpx` for better timeout/error handling.

#### MEDIUM Issues (5)

**M-1: `extract_public_id_from_url()` Doesn't Handle Transformation URLs**
- Cloudinary URLs with transformations: `res.cloudinary.com/cloud/image/upload/c_fill,h_200,w_300/v123/magnific/...`
- The regex `/upload/(?:v\d+/)?(.+)` will include transformation params in the public_id
- **Fix**: Strip transformation segment before extracting public_id

**M-2: `list_resources()` Returns `total = len(resources)` Not Actual Total**
- The Admin API `resources()` response doesn't include a total count field
- Current code returns count of current page as "total" — misleading for pagination
- **Fix**: Return `len(resources)` as "count" and remove misleading "total" field, or document it as "page_count"

**M-3: `_resolve_reference_base64()` Hardcodes MIME as `image/png`**
- When resolving Cloudinary image references, MIME is always set to `image/png`
- Should detect actual format from the asset registry record or URL extension
- **Fix**: Look up format from registry record first, fallback to URL extension

**M-4: `is_cloudinary_url()` Doesn't Validate Our Cloud Name**
- Checks for `cloudinary.com` in hostname — matches ANY Cloudinary account
- A user passing a URL from another Cloudinary account would be treated as ours
- **Fix**: Add optional cloud_name validation parameter

**M-5: Asset Registry JSON — No Concurrent Write Protection Against File Corruption**
- `_save()` writes the entire JSON on every mutation
- If process crashes during write, JSON file could be corrupted
- **Fix**: Write to temp file, then atomic rename (standard pattern)

#### LOW Issues (4)

**L-1: `requirements.txt` Uses `cloudinary>=1.40.0` — Should Pin or Update**
- Latest is 1.44.2; minimum 1.40.0 is fine but outdated
- **Fix**: Update to `cloudinary>=1.44.0`

**L-2: No `tags` Parameter Sent During Upload**
- Cloudinary `upload()` supports `tags=[]` for categorization
- Asset registry tracks tags but they're not sent to Cloudinary
- **Fix**: Pass tags to `cloudinary.uploader.upload()` if provided

**L-3: No `context` Metadata Sent During Upload**
- Cloudinary supports `context={}` for key-value metadata (e.g., model, creation_id)
- This would enable server-side search/filtering via Admin API
- **Fix**: Add context metadata on upload

**L-4: `build_public_id()` Uses Underscore Between creation_id and index**
- Format: `{folder}/{type}/{model}/{creation_id}_{index}`
- Underscore is fine, but consistent naming convention should be documented
- **Fix**: No code change needed, just document

### 1.4 Test Coverage Gaps

| Gap | Priority | Description |
|-----|----------|-------------|
| T-1 | HIGH | No tests for `upload_from_url()` / `upload_from_bytes()` with real SDK calls (only disabled-mode tests) |
| T-2 | HIGH | No tests for `_resolve_reference_base64()` in image routes — the Cloudinary URL → base64 flow |
| T-3 | HIGH | No tests for `_upload_to_cloud()` in image/video routes — the auto-upload after generation |
| T-4 | MEDIUM | No tests for `extract_public_id_from_url()` with transformation URLs |
| T-5 | MEDIUM | No tests for `download_bytes()` / `download_as_base64()` |
| T-6 | LOW | `create_test_app()` helper doesn't inject `FakeCloudinaryService` / `FakeAssetRegistry` |
| T-7 | LOW | No retry logic tests |

---

## PHASE 2: EXECUTION PLAN

### Step 1: Fix HIGH Issues in `core/cloudinary_service.py`

**1.1 Add Retry Logic with Exponential Backoff**
```
- Add `_retry_with_backoff()` private method to CloudinaryService
- Max 3 retries, exponential backoff (1s, 2s, 4s)
- Specifically catch and retry on:
  - cloudinary.exceptions.RateLimited (HTTP 429)
  - cloudinary.exceptions.GeneralError (HTTP 500)
  - Connection errors (timeout, network)
- Do NOT retry on:
  - cloudinary.exceptions.BadRequest (HTTP 400) — user error
  - cloudinary.exceptions.NotFound (HTTP 404) — won't fix on retry
  - cloudinary.exceptions.AuthorizationRequired (HTTP 401) — config error
- Apply retry to: upload_from_url(), upload_from_bytes(), download_bytes(), delete()
```

**1.2 Fix Delete to Include `invalidate=True`**
```
- In delete(): Add invalidate=True to cloudinary.api.delete_resources() call
```

**1.3 Improve `download_bytes()` Error Handling**
```
- Add proper timeout handling (currently 30s — keep it)
- Log download duration for monitoring
- Return None gracefully on failure instead of raising (optional — current raise is fine for reference resolution)
```

**1.4 Fix `extract_public_id_from_url()` for Transformation URLs**
```
- Strip transformation segment: /upload/t_{transformations}/v{version}/{public_id}
- Pattern: /upload/((?:c_|a_|e_|f_|l_|q_|r_|t_|w_)[^/]*\/)*(?:v\d+\/)?(.+)
- Simpler approach: find /upload/, then skip all transformation segments, then skip version, rest is public_id
```

**Tests for Step 1:**
- Test retry logic: mock RateLimited on first call, success on second
- Test retry exhaustion: mock 4 consecutive failures → raises CloudinaryError
- Test no retry on BadRequest: mock 400 → raises immediately
- Test extract_public_id_from_url with transformation URL
- Test extract_public_id_from_url with nested transformations
- Test delete with invalidate=True (verify invalidate param passed)

### Step 2: Fix MEDIUM Issues

**2.1 Fix `_resolve_reference_base64()` MIME Detection** (image.py)
```
- When resolving Cloudinary URL, look up AssetRecord from registry
- Use record.format to determine MIME type
- Fallback: extract from URL extension (.png → image/png, .jpg → image/jpeg, .webp → image/webp)
- Ultimate fallback: "image/png"
```

**2.2 Fix `list_resources()` Total Count** (cloudinary_service.py)
```
- Rename "total" to "count" in returned dict
- Document that this is the count of items in current page, not total across all pages
```

**2.3 Fix `is_cloudinary_url()` to Validate Cloud Name** (cloudinary_service.py)
```
- Add optional `validate_cloud_name: bool = False` parameter
- When True, also check that URL contains our cloud name
```

**2.4 Fix Asset Registry Atomic Write** (asset_registry.py)
```
- In _save(): Write to temp file first, then os.replace() for atomic move
- Pattern:
  1. Write to self._file_path.with_suffix('.tmp')
  2. os.replace(tmp_path, self._file_path)  # Atomic on POSIX
```

**Tests for Step 2:**
- Test MIME detection from registry record
- Test MIME detection from URL extension fallback
- Test MIME default when no info available
- Test list_resources returns "count" not "total"
- Test is_cloudinary_url with validate_cloud_name=True
- Test is_cloudinary_url rejects other cloud names
- Test atomic write (file not corrupted if write interrupted)

### Step 3: Fix Image/Video Route Issues

**3.1 Add Tags to Cloudinary Upload** (both routes)
```
- Pass tags=["magnific", model_slug, creation_id] to upload_from_url() call
- Update upload_from_url() signature or use Cloudinary upload options directly
```

**3.2 Add Context Metadata to Upload** (both routes)
```
- Pass context={"model": model_slug, "creation_id": creation_id} to upload
```

**3.3 Cloudinary Reference Tracking in Video Routes** (video.py)
```
- Current: video routes detect Cloudinary URLs in refs and track usage
- Verify this works correctly for VideoReferenceInput.url field
- Add similar tracking for KeyframeInput if it has Cloudinary URLs
```

**Tests for Step 3:**
- Test tags passed to Cloudinary upload (verify FakeCloudinaryService records them)
- Test context metadata passed to upload
- Test video reference tracking with Cloudinary URLs

### Step 4: Update Configuration & Dependencies

**4.1 Update requirements.txt**
```
- cloudinary>=1.44.0  (was >=1.40.0)
```

**4.2 Add CLOUDINARY_URL Support** (server.py / cloudinary_service.py)
```
- Check for CLOUDINARY_URL env var first
- Parse: cloudinary://API_KEY:API_SECRET@CLOUD_NAME
- Fallback to individual CLOUDINARY_* vars
```

**Tests for Step 4:**
- Test CLOUDINARY_URL parsing
- Test individual env vars fallback

### Step 5: Fill Test Coverage Gaps

**5.1 Tests for Reference Resolution in Image Routes**
```
- Test _resolve_reference_base64 with Cloudinary URL → downloads and converts
- Test _resolve_reference_base64 with regular base64 → passes through
- Test _resolve_reference_base64 with file path → reads file
- Test _resolve_reference_base64 with invalid Cloudinary URL → graceful fallback
```

**5.2 Tests for Auto-Upload After Generation**
```
- Test _upload_to_cloud success flow: mock upload, verify registry registration
- Test _upload_to_cloud disabled: returns None
- Test _upload_to_cloud failure: logs warning, returns None (non-fatal)
```

**5.3 Update create_test_app Helper**
```
- Add FakeCloudinaryService and FakeAssetRegistry injection to create_test_app()
```

---

## PHASE 3: DEFINITION OF DONE

- [ ] All HIGH issues (H-1, H-2, H-3) fixed and tested
- [ ] All MEDIUM issues (M-1 to M-5) fixed and tested
- [ ] All LOW issues (L-1 to L-4) addressed
- [ ] All test gaps (T-1 to T-7) covered
- [ ] All 217 existing tests still passing
- [ ] New tests added (estimated: +30 tests → ~247 total)
- [ ] No regression in existing image/video generation flow
- [ ] Cloudinary gracefully degrades when disabled (existing behavior preserved)
- [ ] Code follows project patterns (thread-safe, lazy imports, logger usage)

---

## PHASE 4: EXECUTION ORDER & ESTIMATES

| Step | Description | Est. Time | Depends On |
|------|-------------|-----------|-------------|
| 1 | Fix HIGH issues in cloudinary_service.py | 30 min | — |
| 2 | Fix MEDIUM issues | 20 min | Step 1 |
| 3 | Fix image/video route issues | 15 min | Step 1 |
| 4 | Update config & dependencies | 10 min | — |
| 5 | Fill test coverage gaps | 30 min | Steps 1-3 |
| **Total** | | **~105 min** | |

---

## PHASE 5: CHECK & ACT (After Implementation)

### Check:
1. Run full test suite: `pytest tests/ -v`
2. Verify no regressions
3. Manually verify Cloudinary URL detection logic
4. Check that all new tests pass

### Act (Retrospective):
1. What worked well?
2. What could be improved?
3. Update PDCA process for next cycle

---

## NOTES

### What's Already Good (No Changes Needed):
- `AssetRegistry` design — clean, thread-safe, JSON-backed
- `build_public_id()` structured naming — well organized
- `set_deps()` injection pattern — consistent with project architecture
- Graceful degradation when Cloudinary is disabled
- Auto-upload after generation (non-fatal failure)
- Server initialization with try/except fallback
- `resource_type="video"` correctly set for videos

### What the Research Confirmed:
- The `cloudinary` Python SDK (1.44.2) is the ONLY recommended library — no alternatives needed
- Our `resource_type` usage is correct (image for images, video for videos)
- Upload from URL is a standard Cloudinary feature (server-side fetch)
- Admin API `resources()` is correct for listing
- Folder-based organization via public_id is the standard approach
- Signed uploads (default with api_key + api_secret) are correct for server-side
