#!/usr/bin/env python3
"""
Deep exploration of Magnific AI API — v2.
Categorizes endpoints as: REAL API (JSON), AUTH REQUIRED (401 JSON), NOT FOUND (HTML SPA).
Extracts full model catalogs from public endpoints.
"""

import json
import os
import sys
import time
from urllib.parse import urlencode, unquote

from curl_cffi.requests import Session

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinj_magnific.txt")
BASE_URL = "https://www.magnific.com"
API_PREFIX = "/app"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


def load_cookies(path):
    cookies = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            parts = line.split("\t") if "\t" in line else line.split()
            if len(parts) >= 7:
                name, value = parts[5], parts[6]
                skip = {"_ga", "_gid", "_gat", "ak_bmsc", "intercom-id",
                         "intercom-session", "posthog", "ph_"}
                if name not in skip and not name.startswith("ph_"):
                    cookies[name] = value
    return cookies


def make_session(cookies):
    s = Session(impersonate="chrome136")
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
        "Sec-Ch-Ua": '"Chromium";v="136", "Not.A/Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
    })
    s.cookies.update(cookies)
    return s


def api_url(path):
    if path.startswith("/api/"):
        return f"{BASE_URL}{API_PREFIX}{path}"
    elif path.startswith("/user/"):
        return f"{BASE_URL}{path}"
    elif path.startswith("/sanctum/"):
        return f"{BASE_URL}{API_PREFIX}{path}"
    else:
        return f"{BASE_URL}{API_PREFIX}{path}"


def fetch(s, method, path, params=None, json_data=None):
    url = api_url(path)
    try:
        if method == "GET":
            r = s.get(url, params=params)
        elif method == "POST":
            r = s.post(url, json=json_data)
        elif method == "DELETE":
            r = s.delete(url)
        else:
            r = s.get(url, params=params)

        ct = r.headers.get("content-type", "")
        body_text = r.text[:5000]

        parsed = None
        if "application/json" in ct or body_text.strip().startswith(("{", "[")):
            try:
                parsed = json.loads(r.text)
            except Exception:
                parsed = None

        is_html = "text/html" in ct or "<!DOCTYPE" in body_text[:100]
        return r.status_code, ct, parsed, is_html, body_text[:300]
    except Exception as e:
        return 0, str(type(e)), {"error": str(e)}, False, str(e)[:300]


# Results tracking
REAL_API = []        # Returns JSON (working)
AUTH_REQUIRED = []   # Returns 401 JSON (exists but needs auth)
NOT_FOUND = []       # Returns HTML SPA (doesn't exist as API)
OTHER_STATUS = []    # Other HTTP codes with JSON


def test_endpoint(s, method, path, params=None, desc=""):
    st, ct, parsed, is_html, preview = fetch(s, method, path, params=params)
    pstr = f"?{urlencode(params)}" if params else ""

    if is_html and st == 200:
        NOT_FOUND.append((path, params, desc))
    elif st == 401 and parsed:
        AUTH_REQUIRED.append((path, params, desc))
    elif st == 200 and parsed and not is_html:
        REAL_API.append((path, params, desc))
    elif parsed and not is_html:
        OTHER_STATUS.append((path, params, st, desc))
    else:
        NOT_FOUND.append((path, params, desc))

    # Print one-line status
    if is_html and st == 200:
        icon = "📄"  # HTML fallback
        tag = "SPA_FALLBACK"
    elif st == 401 and parsed:
        icon = "🔒"
        tag = "AUTH_REQUIRED"
    elif st == 200 and parsed and not is_html:
        icon = "✅"
        tag = "JSON_API"
    elif st >= 500:
        icon = "🔥"
        tag = f"SERVER_{st}"
    elif st == 404:
        icon = "❌"
        tag = "NOT_FOUND"
    else:
        icon = "❓"
        tag = f"HTTP_{st}"

    desc_str = f"  # {desc}" if desc else ""
    params_str = f"  ?{urlencode(params)}" if params else ""
    print(f"  {icon} [{st:>3}] {tag:<16} {path}{params_str}{desc_str}")
    return st, parsed


def main():
    print("=" * 80)
    print("  MAGNIFIC AI — DEEP API EXPLORATION v2")
    print("=" * 80)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    cookies = load_cookies(COOKIES_FILE)
    print(f"Loaded {len(cookies)} cookies")
    s = make_session(cookies)

    # Try auth
    print("\n--- Auth ---")
    r = s.get(f"{BASE_URL}{API_PREFIX}/sanctum/csrf-cookie")
    xsrf = s.cookies.get("XSRF-TOKEN")
    if xsrf:
        s.headers["X-XSRF-TOKEN"] = unquote(xsrf)
        print(f"  XSRF OK ({len(xsrf)} chars)")
    r2 = s.post(f"{BASE_URL}/user/api/devices/identify", json={})
    print(f"  Device identify: {r2.status_code}")
    print(f"  NOTE: GR_TOKEN expired (exp=1780156063 = Feb 1 2026, now = {int(time.time())})")
    print(f"  Most authenticated endpoints will return 401. Public endpoints still work.")

    # ═══════════════════════════════════════════════════════════════════
    # 1. CREATIONS LIST + PARAMETERS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  1. CREATIONS LIST — Pagination, Status, Sort, Filters")
    print("=" * 80)

    # Base endpoint
    test_endpoint(s, "GET", "/api/creations", desc="Base creations list")

    # Pagination params
    for params in [
        {"per_page": 1}, {"per_page": 5}, {"per_page": 10}, {"per_page": 50}, {"per_page": 100},
        {"page": 1}, {"page": 1, "per_page": 5}, {"page": 2, "per_page": 5},
        {"limit": 5}, {"limit": 5, "offset": 0}, {"limit": 5, "offset": 5},
        {"pageSize": 5}, {"take": 5}, {"skip": 5, "take": 5},
    ]:
        test_endpoint(s, "GET", "/api/creations", params=params)

    # Status filters
    for status in ["processing", "queued", "completed", "failed", "error",
                    "cancelled", "all", "pending", "active", "waiting", "success"]:
        test_endpoint(s, "GET", "/api/creations", params={"status": status}, desc=f"status={status}")

    # Sort
    for params in [
        {"sort": "createdAt"}, {"sort": "-createdAt"}, {"sort": "created_at"},
        {"sort": "created_at", "order": "desc"}, {"sort": "created_at", "order": "asc"},
        {"orderBy": "createdAt"}, {"orderBy": "created_at", "direction": "desc"},
    ]:
        test_endpoint(s, "GET", "/api/creations", params=params)

    # Tool/family filters
    for params in [
        {"tool": "text-to-image"}, {"tool": "video-generator"}, {"tool": "video"},
        {"tool": "upscaler"}, {"tool": "image"},
        {"family": "imagen-nano-banana-2"}, {"family": "bytedance"},
    ]:
        test_endpoint(s, "GET", "/api/creations", params=params)

    # Combined
    for params in [
        {"status": "completed", "per_page": 3},
        {"status": "processing", "per_page": 1},
        {"status": "queued", "per_page": 1},
        {"status": "failed", "per_page": 1},
    ]:
        test_endpoint(s, "GET", "/api/creations", params=params)

    # ═══════════════════════════════════════════════════════════════════
    # 2. SINGLE CREATION DETAIL
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  2. SINGLE CREATION — /api/creation/{id}")
    print("=" * 80)

    test_endpoint(s, "GET", "/api/creation/12345", desc="Single creation (dummy ID)")
    test_endpoint(s, "GET", "/api/creation/0", desc="Single creation (zero ID)")
    test_endpoint(s, "DELETE", "/api/creation/12345", desc="DELETE creation")
    test_endpoint(s, "GET", "/api/creation/12345/download", desc="Creation download")
    test_endpoint(s, "GET", "/api/creation/12345/status", desc="Creation status sub-endpoint")

    # ═══════════════════════════════════════════════════════════════════
    # 3. CREATIONS SUB-ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  3. CREATIONS SUB-ENDPOINTS")
    print("=" * 80)

    for path in ["/api/creations/stats", "/api/creations/count", "/api/creations/summary",
                 "/api/creations/queue", "/api/creations/status", "/api/creations/recent",
                 "/api/creations/history", "/api/creations/failed", "/api/creations/active",
                 "/api/creations/batch", "/api/creations/export", "/api/creations/metrics",
                 "/api/creations/filters", "/api/creations/search"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 4. USER / ACCOUNT / CREDITS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  4. USER / ACCOUNT / CREDITS")
    print("=" * 80)

    for path in ["/api/user", "/api/account", "/api/credits", "/api/user/credits",
                 "/api/user/profile", "/api/user/settings", "/api/user/quota",
                 "/api/user/plan", "/api/user/limits", "/api/user/collections",
                 "/api/billing", "/api/billing/usage", "/api/subscription",
                 "/api/subscription/usage", "/api/subscription/plan", "/api/subscription/current",
                 "/api/usage", "/api/usage/stats", "/api/me", "/api/profile",
                 "/api/account/settings", "/api/account/billing", "/api/account/subscription",
                 "/api/account/credits", "/api/account/plan", "/api/account/info"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 5. MODELS / CONFIG / SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  5. MODELS / CONFIG / SETTINGS")
    print("=" * 80)

    for path in ["/api/settings", "/api/config", "/api/models", "/api/v2/ai-models",
                 "/api/video/ai-models", "/api/custom-models", "/api/ai-models",
                 "/api/families", "/api/tools", "/api/features", "/api/feature-flags",
                 "/api/v1/ai-models", "/api/v3/ai-models"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 6. GENERATION / QUEUE / LIMITS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  6. GENERATION / QUEUE / LIMITS")
    print("=" * 80)

    for path in ["/api/generations", "/api/generations/active", "/api/generations/limits",
                 "/api/generations/count", "/api/generation-limits", "/api/queue",
                 "/api/queue/status", "/api/queue/position", "/api/jobs", "/api/jobs/active",
                 "/api/tasks", "/api/tasks/active", "/api/rate-limit", "/api/rate-limits",
                 "/api/concurrency", "/api/concurrency/limit", "/api/concurrent",
                 "/api/max-concurrent", "/api/limits", "/api/capabilities",
                 "/api/max-creations", "/api/credits-balance", "/api/credits/check"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 7. IMAGE ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  7. IMAGE ENDPOINTS")
    print("=" * 80)

    for path in ["/api/image", "/api/image/models", "/api/image/settings", "/api/image/config",
                 "/api/image/features", "/api/image/styles", "/api/image/presets",
                 "/api/image/color-palettes", "/api/image/modifiers", "/api/start-tti-v2",
                 "/api/render/v4", "/api/temporal-storage", "/api/prompt-improvement",
                 "/api/smart-prompt", "/api/prompt-enhance", "/api/modifiers",
                 "/api/color-palettes", "/api/styles", "/api/presets"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 8. VIDEO ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  8. VIDEO ENDPOINTS")
    print("=" * 80)

    for path in ["/api/video", "/api/video/generate", "/api/video/models",
                 "/api/video/ai-models", "/api/video/settings", "/api/video/config",
                 "/api/video/features", "/api/video/prompt-improvement",
                 "/api/video/describe-frames", "/api/video/feature/soundfx",
                 "/api/video/feature/extension", "/api/video/feature/auto-caption",
                 "/api/video/create-multi-shot-scenes", "/api/video/generate/upload-frame",
                 "/api/video/generate/upload-frames", "/api/video/simulate/generate",
                 "/api/video/cancel"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 9. SYSTEM / HEALTH
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  9. SYSTEM / HEALTH")
    print("=" * 80)

    for path in ["/api/health", "/api/healthz", "/api/status", "/api/ping",
                 "/api/ready", "/api/info", "/api/version", "/api/system",
                 "/api/debug", "/api/maintenance", "/api/notifications",
                 "/api/announcements", "/api/changelog"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 10. FOLDERS / BOARDS / COLLECTIONS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  10. FOLDERS / BOARDS / COLLECTIONS")
    print("=" * 80)

    for path in ["/api/folders", "/api/boards", "/api/collections", "/api/albums",
                 "/api/galleries", "/api/favorites", "/api/starred", "/api/pins",
                 "/api/tags", "/api/categories", "/api/folder", "/api/board"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 11. UPSCALER / OTHER TOOLS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  11. UPSCALER / OTHER TOOLS")
    print("=" * 80)

    for path in ["/api/upscaler", "/api/upscale", "/api/enhance", "/api/remove-bg",
                 "/api/remove-background", "/api/inpaint", "/api/outpaint",
                 "/api/eraser", "/api/variation", "/api/diffusion", "/api/controlnet",
                 "/api/sketch", "/api/adventure", "/api/prompt-adventure"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 12. VERSIONED ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  12. VERSIONED ENDPOINTS")
    print("=" * 80)

    for path in ["/api/v1/creations", "/api/v2/creations", "/api/v3/creations",
                 "/api/v1/user", "/api/v1/settings", "/api/v1/models",
                 "/api/v2/user", "/api/v2/config"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 13. DASHBOARD / STATS / ANALYTICS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  13. DASHBOARD / STATS / ANALYTICS")
    print("=" * 80)

    for path in ["/api/stats", "/api/stats/usage", "/api/stats/overview",
                 "/api/dashboard", "/api/dashboard/stats", "/api/analytics",
                 "/api/analytics/usage", "/api/reports", "/api/activity", "/api/activity/log"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # 14. ADDITIONAL CREATION-RELATED ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  14. ADDITIONAL CREATION-RELATED ENDPOINTS")
    print("=" * 80)

    for path in ["/api/creation", "/api/creations/favorite", "/api/creations/delete",
                 "/api/creations/download", "/api/creations/share",
                 "/api/creations/retry", "/api/creations/cancel",
                 "/api/creations/regenerate", "/api/creations/rate",
                 "/api/creations/report", "/api/creations/copy",
                 "/api/creations/history/clear", "/api/creations/trash",
                 "/api/creations/restore", "/api/creations/archived",
                 "/api/creations/public", "/api/creations/private",
                 "/api/creations/pinned"]:
        test_endpoint(s, "GET", path)

    # ═══════════════════════════════════════════════════════════════════
    # FULL MODEL CATALOG EXTRACTION
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  15. FULL MODEL CATALOG EXTRACTION")
    print("=" * 80)

    # v2/ai-models — full catalog
    st, ct, parsed, _, _ = fetch(s, "GET", "/api/v2/ai-models")
    if parsed and isinstance(parsed, list):
        print(f"\n  /api/v2/ai-models: {len(parsed)} models total")

        image_models = [m for m in parsed if m.get("tool") == "text-to-image"]
        video_models = [m for m in parsed if m.get("tool") == "video-generator"]

        print(f"\n  IMAGE MODELS ({len(image_models)}):")
        for m in sorted(image_models, key=lambda x: x.get("slug", "")):
            meta = m.get("metadata", {})
            inputs = m.get("inputs", {})
            outputs = m.get("outputs", {})
            ar = inputs.get("aspectRatio", {}).get("values", [])
            res = inputs.get("resolution", {}).get("values", [])
            prompt_max = inputs.get("prompt", {}).get("maxLength", "?")
            has_refs = inputs.get("references", [])
            seed = "seed" in inputs
            print(f"    {m['slug']}")
            print(f"      status: {m.get('status')}, disabled: {m.get('disabled')}")
            print(f"      aspect_ratios: {ar}, resolutions: {res}, prompt_max: {prompt_max}")
            print(f"      references: {len(has_refs)} types, seed: {seed}")
            print(f"      expected_gen_time: {outputs.get('expectedGenerationTime', '?')}s")
            print(f"      metadata.api: {meta.get('api')}, metadata.model: {meta.get('model')}, metadata.mode: {meta.get('mode')}")

        print(f"\n  VIDEO MODELS ({len(video_models)}):")
        for m in sorted(video_models, key=lambda x: x.get("slug", "")):
            meta = m.get("metadata", {})
            inputs = m.get("inputs", {})
            outputs = m.get("outputs", {})
            dur_raw = inputs.get("duration", [])
            dur = dur_raw if isinstance(dur_raw, list) else dur_raw.get("values", [])
            ar_raw = inputs.get("aspectRatio", {})
            ar = ar_raw if isinstance(ar_raw, list) else ar_raw.get("values", [])
            res_raw = inputs.get("resolution", {})
            res = res_raw if isinstance(res_raw, list) else res_raw.get("values", [])
            prompt_raw = inputs.get("prompt", {})
            prompt_max = prompt_raw if isinstance(prompt_raw, dict) else prompt_raw.get("maxLength", "?")
            if isinstance(prompt_max, dict):
                prompt_max = prompt_max.get("maxLength", "?")
            has_refs = inputs.get("references", [])
            sound = inputs.get("soundEffects", {})
            multishot = inputs.get("multishot", {})
            seed = "seed" in inputs
            print(f"    {m['slug']}")
            print(f"      status: {m.get('status')}, disabled: {m.get('disabled')}")
            print(f"      duration: {dur}, aspect_ratios: {ar}, resolutions: {res}")
            print(f"      prompt_max: {prompt_max}, seed: {seed}")
            print(f"      sound_effects: {sound}, multishot: {multishot}")
            print(f"      expected_gen_time: {outputs.get('expectedGenerationTime', '?')}s, fps: {outputs.get('fps', '?')}")
            print(f"      metadata.api: {meta.get('api')}, metadata.model: {meta.get('model')}, metadata.mode: {meta.get('mode')}")

    # video/ai-models — grouped by provider
    st, ct, parsed, _, _ = fetch(s, "GET", "/api/video/ai-models")
    if parsed and isinstance(parsed, dict):
        print(f"\n  /api/video/ai-models: providers={list(parsed.keys())}")
        for provider, models in parsed.items():
            print(f"\n  Provider '{provider}': {len(models)} models")
            for m in models:
                print(f"    {m.get('id', '?')}: {m.get('name', '?')}")
                print(f"      duration: {m.get('duration', '?')}, ar: {m.get('aspectRatio', '?')}")
                print(f"      expected_gen_time: {m.get('expectedGenerationTime', '?')}s")
                print(f"      seed: {m.get('seed')}, sound: {m.get('withSoundEffects')}")
                print(f"      keyframes: {list(m.get('keyframes', {}).keys()) if m.get('keyframes') else []}")

    # custom-models
    st, ct, parsed, _, _ = fetch(s, "GET", "/api/custom-models")
    if parsed and isinstance(parsed, dict):
        public = parsed.get("public_custom_models", [])
        print(f"\n  /api/custom-models: {len(public)} public custom models")
        if public:
            print(f"    First: {public[0].get('name', '?')} ({public[0].get('type', '?')})")

    # ═══════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"\n  ✅ CONFIRMED API ENDPOINTS (return JSON): {len(REAL_API)}")
    for path, params, desc in REAL_API:
        p = f"?{urlencode(params)}" if params else ""
        d = f"  ({desc})" if desc else ""
        print(f"     {path}{p}{d}")

    print(f"\n  🔒 AUTH-REQUIRED ENDPOINTS (return 401 JSON): {len(AUTH_REQUIRED)}")
    for path, params, desc in AUTH_REQUIRED:
        p = f"?{urlencode(params)}" if params else ""
        d = f"  ({desc})" if desc else ""
        print(f"     {path}{p}{d}")

    print(f"\n  📄 SPA FALLBACK / NOT FOUND: {len(NOT_FOUND)} (return HTML)")

    s.close()


if __name__ == "__main__":
    main()
