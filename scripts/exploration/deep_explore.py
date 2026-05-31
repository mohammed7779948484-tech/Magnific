#!/usr/bin/env python3
"""
Deep exploration of Magnific AI internal API.
Tests ALL known and suspected endpoints, parameters, and response structures.
Uses curl_cffi with chrome136 TLS fingerprint for Cloudflare bypass.
"""

import json
import os
import sys
import time
from urllib.parse import urlencode
from urllib.parse import unquote

from curl_cffi.requests import Session

# ── Config ────────────────────────────────────────────────────────────
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinj_magnific.txt")
BASE_URL = "https://www.magnific.com"
API_PREFIX = "/app"  # magnific.com uses /app prefix

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

TRUNCATE = 2000  # Max response body chars to print


def load_cookies(path: str) -> dict[str, str]:
    """Parse Netscape cookie file into name->value dict."""
    cookies = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Handle #HttpOnly_ prefix
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            parts = line.split("\t") if "\t" in line else line.split()
            if len(parts) >= 7:
                name, value = parts[5], parts[6]
                # Skip analytics/tracking cookies
                skip = {"_ga", "_gid", "_gat", "ak_bmsc", "intercom-id",
                         "intercom-session", "posthog"}
                if name not in skip and not name.startswith("ph_"):
                    cookies[name] = value
    print(f"Loaded {len(cookies)} cookies from {path}")
    return cookies


def make_session(cookies: dict[str, str]) -> Session:
    """Create curl_cffi session with chrome136 fingerprint."""
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


def authenticate(s: Session) -> bool:
    """Run XSRF refresh + device identify."""
    # 1. Get CSRF cookie
    try:
        r = s.get(f"{BASE_URL}{API_PREFIX}/sanctum/csrf-cookie")
        if r.status_code in (200, 204):
            xsrf_raw = s.cookies.get("XSRF-TOKEN")
            if xsrf_raw:
                xsrf = unquote(xsrf_raw)
                s.headers["X-XSRF-TOKEN"] = xsrf
                print(f"XSRF-TOKEN obtained ({len(xsrf)} chars)")
            else:
                print("WARNING: No XSRF-TOKEN cookie received")
                return False
        else:
            print(f"WARNING: CSRF endpoint returned {r.status_code}")
            return False
    except Exception as e:
        print(f"WARNING: CSRF refresh failed: {e}")
        return False

    # 2. Device identify
    try:
        r = s.post(f"{BASE_URL}/user/api/devices/identify", json={})
        print(f"Device identify: {r.status_code}")
    except Exception as e:
        print(f"WARNING: Device identify failed: {e}")

    return True


def api_url(path: str) -> str:
    """Build full API URL, auto-prefixing /api/ paths."""
    if path.startswith("/api/"):
        return f"{BASE_URL}{API_PREFIX}{path}"
    elif path.startswith("/user/"):
        # user endpoints don't have the /app prefix
        return f"{BASE_URL}{path}"
    elif path.startswith("/sanctum/"):
        return f"{BASE_URL}{API_PREFIX}{path}"
    else:
        return f"{BASE_URL}{API_PREFIX}{path}"


def fetch(s: Session, method: str, path: str, params: dict = None, json_data: dict = None) -> tuple[int, str, dict | list | None]:
    """Make a request and return (status_code, content_type, parsed_json)."""
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
        body = r.text[:TRUNCATE]

        # Try to parse JSON
        parsed = None
        if "application/json" in ct or body.strip().startswith("{") or body.strip().startswith("["):
            try:
                parsed = json.loads(r.text)
            except Exception:
                parsed = None

        return r.status_code, ct, parsed
    except Exception as e:
        return 0, str(type(e)), {"error": str(e)}


def print_result(label: str, method: str, path: str, params: dict, status: int, ct: str, parsed):
    """Print a formatted result line."""
    param_str = ""
    if params:
        param_str = f"  ? {urlencode(params)}"

    # Status emoji
    if status == 0:
        icon = "💥"
    elif 200 <= status < 300:
        icon = "✅"
    elif status == 401:
        icon = "🔒"
    elif status == 403:
        icon = "🚫"
    elif status == 404:
        icon = "❌"
    elif status == 422:
        icon = "⚠️"
    elif status == 429:
        icon = "⏳"
    elif status >= 500:
        icon = "🔥"
    else:
        icon = "❓"

    print(f"\n{icon} [{status}] {method} {path}{param_str}")
    if ct and ct != "str":
        print(f"   Content-Type: {ct[:80]}")

    if parsed:
        body_str = json.dumps(parsed, indent=2, ensure_ascii=False)
        if len(body_str) > TRUNCATE:
            print(f"   Body (truncated):")
            print("   " + body_str[:TRUNCATE].replace("\n", "\n   "))
            print(f"   ... ({len(body_str)} total chars)")
        else:
            print(f"   Body:")
            print("   " + body_str.replace("\n", "\n   "))


def explore(s: Session):
    """Run all exploration tests."""

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: PAGINATION PARAMETERS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 1: PAGINATION PARAMETERS on /api/creations")
    print("=" * 80)

    pagination_tests = [
        ("limit=5&offset=0", {"limit": 5, "offset": 0}),
        ("page=1", {"page": 1}),
        ("page=1&pageSize=5", {"page": 1, "pageSize": 5}),
        ("page=1&per_page=5", {"page": 1, "per_page": 5}),
        ("limit=3", {"limit": 3}),
        ("limit=3&offset=3", {"limit": 3, "offset": 3}),
        ("skip=5&take=5", {"skip": 5, "take": 5}),
        ("per_page=50", {"per_page": 50}),
        ("per_page=1", {"per_page": 1}),
        ("per_page=100", {"per_page": 100}),
    ]

    for label, params in pagination_tests:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params=params)
        print_result(label, "GET", "/api/creations", params, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2: STATUS VALUES
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 2: STATUS VALUES on /api/creations?status=...")
    print("=" * 80)

    status_tests = [
        "processing", "queued", "completed", "failed", "error",
        "cancelled", "all", "pending", "active", "waiting",
        "success", "timeout", "expired", "draft",
    ]

    for status in status_tests:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params={"status": status})
        print_result(f"status={status}", "GET", "/api/creations", {"status": status}, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 3: SORT PARAMETERS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 3: SORT PARAMETERS on /api/creations")
    print("=" * 80)

    sort_tests = [
        ("sort=createdAt", {"sort": "createdAt"}),
        ("sort=-createdAt", {"sort": "-createdAt"}),
        ("sort=created_at", {"sort": "created_at"}),
        ("sort=created_at&order=desc", {"sort": "created_at", "order": "desc"}),
        ("sort=created_at&order=asc", {"sort": "created_at", "order": "asc"}),
        ("orderBy=createdAt", {"orderBy": "createdAt"}),
        ("orderBy=created_at&direction=desc", {"orderBy": "created_at", "direction": "desc"}),
        ("sort=id", {"sort": "id"}),
        ("sort=-id", {"sort": "-id"}),
    ]

    for label, params in sort_tests:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params=params)
        print_result(label, "GET", "/api/creations", params, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 4: FILTER PARAMETERS (tool, family, etc.)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 4: FILTER PARAMETERS on /api/creations")
    print("=" * 80)

    filter_tests = [
        ("tool=text-to-image", {"tool": "text-to-image"}),
        ("tool=video-generator", {"tool": "video-generator"}),
        ("tool=upscaler", {"tool": "upscaler"}),
        ("tool=video", {"tool": "video"}),
        ("tool=image", {"tool": "image"}),
        ("family=imagen-nano-banana-2", {"family": "imagen-nano-banana-2"}),
        ("search=test", {"search": "test"}),
        ("q=test", {"q": "test"}),
        ("has_prompt=true", {"has_prompt": True}),
    ]

    for label, params in filter_tests:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params=params)
        print_result(label, "GET", "/api/creations", params, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 5: SINGLE CREATION DETAIL
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 5: SINGLE CREATION DETAIL — /api/creation/{id}")
    print("=" * 80)

    # Get a creation ID from the list first
    st, ct, parsed = fetch(s, "GET", "/api/creations", params={"per_page": 1, "status": "completed"})
    creation_ids = []
    if parsed and isinstance(parsed, dict):
        data = parsed.get("data", [])
        if data:
            cid = data[0].get("id")
            creation_ids.append(cid)

            # Full detail of a completed creation
            print(f"\n--- Fetching FULL detail of creation ID: {cid} ---")
            st, ct, detail = fetch(s, "GET", f"/api/creation/{cid}")
            print_result(f"creation/{cid}", "GET", f"/api/creation/{cid}", None, st, ct, detail)

            if detail and isinstance(detail, dict):
                print(f"\n--- ALL FIELDS in creation object ---")
                for key, val in detail.items():
                    if isinstance(val, dict):
                        print(f"  {key}: <dict with {len(val)} keys: {list(val.keys())}>")
                        # Print metadata sub-keys for debugging
                        if key == "metadata":
                            for mk, mv in val.items():
                                mv_str = json.dumps(mv, ensure_ascii=False) if not isinstance(mv, str) else mv
                                if len(mv_str) > 200:
                                    mv_str = mv_str[:200] + "..."
                                print(f"    {mk}: {mv_str}")
                    elif isinstance(val, list):
                        print(f"  {key}: <list with {len(val)} items>")
                        if val and isinstance(val[0], dict):
                            print(f"    First item keys: {list(val[0].keys())}")
                    elif isinstance(val, str) and len(val) > 150:
                        print(f"  {key}: {val[:150]}...")
                    else:
                        print(f"  {key}: {val}")

    # Also get a creation from queued/processing if available
    for status in ["queued", "processing"]:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params={"per_page": 1, "status": status})
        if parsed and isinstance(parsed, dict):
            data = parsed.get("data", [])
            if data:
                cid = data[0].get("id")
                if cid and cid not in creation_ids:
                    creation_ids.append(cid)
                    print(f"\n--- Fetching FULL detail of {status} creation ID: {cid} ---")
                    st, ct, detail = fetch(s, "GET", f"/api/creation/{cid}")
                    print_result(f"creation/{cid} ({status})", "GET", f"/api/creation/{cid}", None, st, ct, detail)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 6: ACCOUNT / CREDITS / USER INFO
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 6: ACCOUNT / CREDITS / USER INFO")
    print("=" * 80)

    account_endpoints = [
        "/api/user",
        "/api/account",
        "/api/credits",
        "/api/user/credits",
        "/api/user/profile",
        "/api/user/settings",
        "/api/user/quota",
        "/api/user/plan",
        "/api/user/limits",
        "/api/user/collections",
        "/api/billing",
        "/api/billing/usage",
        "/api/subscription",
        "/api/subscription/usage",
        "/api/subscription/plan",
        "/api/subscription/current",
        "/api/usage",
        "/api/usage/stats",
        "/api/me",
        "/api/profile",
        "/api/account/settings",
        "/api/account/billing",
        "/api/account/subscription",
        "/api/account/credits",
        "/api/account/plan",
    ]

    for path in account_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path.split("/")[-1], "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 7: SETTINGS / CONFIG / MODELS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 7: SETTINGS / CONFIG / MODELS")
    print("=" * 80)

    config_endpoints = [
        "/api/settings",
        "/api/config",
        "/api/models",
        "/api/v2/ai-models",
        "/api/video/ai-models",
        "/api/custom-models",
        "/api/ai-models",
        "/api/families",
        "/api/tools",
        "/api/features",
        "/api/feature-flags",
    ]

    for path in config_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path.split("/")[-1], "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 8: CREATIONS SUB-ENDPOINTS (stats, count, etc.)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 8: CREATIONS SUB-ENDPOINTS")
    print("=" * 80)

    sub_endpoints = [
        "/api/creations/stats",
        "/api/creations/count",
        "/api/creations/summary",
        "/api/creations/queue",
        "/api/creations/status",
        "/api/creations/recent",
        "/api/creations/history",
        "/api/creations/failed",
        "/api/creations/active",
        "/api/creations/batch",
        "/api/creations/export",
        "/api/creations/metrics",
        "/api/creations/filters",
    ]

    for path in sub_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 9: GENERATION / QUEUE ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 9: GENERATION / QUEUE ENDPOINTS")
    print("=" * 80)

    gen_endpoints = [
        "/api/generations",
        "/api/generations/active",
        "/api/generations/limits",
        "/api/generations/count",
        "/api/generation-limits",
        "/api/queue",
        "/api/queue/status",
        "/api/queue/position",
        "/api/jobs",
        "/api/jobs/active",
        "/api/tasks",
        "/api/tasks/active",
        "/api/rate-limit",
        "/api/rate-limits",
        "/api/concurrency",
        "/api/concurrency/limit",
        "/api/concurrent",
        "/api/max-concurrent",
        "/api/limits",
        "/api/capabilities",
    ]

    for path in gen_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 10: VIDEO-SPECIFIC ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 10: VIDEO-SPECIFIC ENDPOINTS")
    print("=" * 80)

    video_endpoints = [
        "/api/video",
        "/api/video/generate",
        "/api/video/models",
        "/api/video/ai-models",
        "/api/video/settings",
        "/api/video/config",
        "/api/video/features",
        "/api/video/prompt-improvement",
        "/api/video/describe-frames",
        "/api/video/feature/soundfx",
        "/api/video/feature/extension",
        "/api/video/feature/auto-caption",
        "/api/video/create-multi-shot-scenes",
    ]

    for path in video_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 11: IMAGE-SPECIFIC ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 11: IMAGE-SPECIFIC ENDPOINTS")
    print("=" * 80)

    image_endpoints = [
        "/api/image",
        "/api/image/models",
        "/api/start-tti-v2",
        "/api/render/v4",
        "/api/image/generate",
        "/api/temporal-storage",
        "/api/upload",
        "/api/uploads",
        "/api/image/settings",
        "/api/image/config",
        "/api/image/features",
        "/api/image/styles",
        "/api/image/presets",
        "/api/image/color-palettes",
        "/api/image/modifiers",
        "/api/prompt-improvement",
        "/api/smart-prompt",
        "/api/prompt-enhance",
    ]

    for path in image_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 12: HEALTH / SYSTEM ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 12: HEALTH / SYSTEM ENDPOINTS")
    print("=" * 80)

    system_endpoints = [
        "/api/health",
        "/api/healthz",
        "/api/status",
        "/api/ping",
        "/api/ready",
        "/api/info",
        "/api/version",
        "/api/system",
        "/api/debug",
        "/api/maintenance",
        "/api/notifications",
        "/api/announcements",
        "/api/changelog",
    ]

    for path in system_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 13: V1 / V2 VERSIONED ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 13: VERSIONED ENDPOINTS (v1, v2, v3)")
    print("=" * 80)

    versioned_endpoints = [
        "/api/v1/creations",
        "/api/v2/creations",
        "/api/v3/creations",
        "/api/v1/user",
        "/api/v1/settings",
        "/api/v1/models",
        "/api/v2/ai-models",
        "/api/v2/user",
        "/api/v2/config",
    ]

    for path in versioned_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 14: FOLDERS / BOARDS / COLLECTIONS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 14: FOLDERS / BOARDS / COLLECTIONS")
    print("=" * 80)

    board_endpoints = [
        "/api/folders",
        "/api/boards",
        "/api/collections",
        "/api/albums",
        "/api/galleries",
        "/api/favorites",
        "/api/starred",
        "/api/pins",
        "/api/tags",
        "/api/categories",
    ]

    for path in board_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 15: UPSCALER / ENHANCE ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 15: UPSCALER / ENHANCE / OTHER TOOLS")
    print("=" * 80)

    tool_endpoints = [
        "/api/upscaler",
        "/api/upscale",
        "/api/enhance",
        "/api/remove-bg",
        "/api/remove-background",
        "/api/inpaint",
        "/api/outpaint",
        "/api/eraser",
        "/api/variation",
        "/api/outpainting",
        "/api/inpainting",
        "/api/variation",
        "/api/diffusion",
        "/api/controlnet",
        "/api/sketch",
        "/api/prompt-adventure",
        "/api/adventure",
    ]

    for path in tool_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 16: DASHBOARD / STATS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 16: DASHBOARD / STATS")
    print("=" * 80)

    dashboard_endpoints = [
        "/api/stats",
        "/api/stats/usage",
        "/api/stats/overview",
        "/api/dashboard",
        "/api/dashboard/stats",
        "/api/analytics",
        "/api/analytics/usage",
        "/api/reports",
        "/api/activity",
        "/api/activity/log",
    ]

    for path in dashboard_endpoints:
        st, ct, parsed = fetch(s, "GET", path)
        print_result(path, "GET", path, None, st, ct, parsed)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 17: FULL CREATION RESPONSE STRUCTURE (with pagination)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 17: FULL /api/creations RESPONSE STRUCTURE")
    print("=" * 80)

    st, ct, parsed = fetch(s, "GET", "/api/creations", params={"per_page": 3, "status": "completed"})
    if parsed and isinstance(parsed, dict):
        print(f"Top-level keys: {list(parsed.keys())}")
        for key in parsed:
            val = parsed[key]
            if key == "data":
                print(f"  {key}: list with {len(val)} items")
                if val:
                    print(f"    First item keys: {list(val[0].keys())}")
            elif isinstance(val, dict):
                print(f"  {key}: {json.dumps(val, indent=2, ensure_ascii=False)[:500]}")
            else:
                print(f"  {key}: {val}")

        # Full item structure
        if parsed.get("data"):
            print("\n--- COMPLETE first creation item structure ---")
            item = parsed["data"][0]
            for key, val in item.items():
                if isinstance(val, dict):
                    print(f"  {key}: <dict with {len(val)} keys>")
                    for mk, mv in val.items():
                        mv_str = json.dumps(mv, ensure_ascii=False) if not isinstance(mv, str) else mv
                        if len(mv_str) > 150:
                            mv_str = mv_str[:150] + "..."
                        print(f"    {mk}: {mv_str}")
                elif isinstance(val, list):
                    print(f"  {key}: <list with {len(val)} items>")
                elif isinstance(val, str) and len(val) > 100:
                    print(f"  {key}: {val[:100]}...")
                else:
                    print(f"  {key}: {val}")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 18: CREATIONS RESPONSE STRUCTURE — top-level meta
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 18: PAGINATION META STRUCTURE")
    print("=" * 80)

    for page_size in [1, 5, 10, 50]:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params={"per_page": page_size, "status": "completed"})
        if parsed and isinstance(parsed, dict):
            meta = parsed.get("meta", {})
            total = meta.get("total", "?")
            current = meta.get("current_page", "?")
            last = meta.get("last_page", "?")
            print(f"  per_page={page_size} → total={total}, current_page={current}, last_page={last}, items={len(parsed.get('data', []))}")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 19: CREATION COUNTS BY ALL STATUSES
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  SECTION 19: CREATION COUNTS BY STATUS")
    print("=" * 80)

    for status in ["processing", "queued", "completed", "failed", "cancelled"]:
        st, ct, parsed = fetch(s, "GET", "/api/creations", params={"status": status, "per_page": 1})
        if parsed and isinstance(parsed, dict):
            meta = parsed.get("meta", {})
            total = meta.get("total", len(parsed.get("data", [])))
            data_len = len(parsed.get("data", []))
            print(f"  status={status}: HTTP {st}, total={total}, items_in_response={data_len}")

    # Also try without status filter
    st, ct, parsed = fetch(s, "GET", "/api/creations", params={"per_page": 1})
    if parsed and isinstance(parsed, dict):
        meta = parsed.get("meta", {})
        total = meta.get("total", len(parsed.get("data", [])))
        print(f"  status=<none>: HTTP {st}, total={total}, items_in_response={len(parsed.get('data', []))}")


def main():
    print("=" * 80)
    print("  MAGNIFIC AI — DEEP API EXPLORATION")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"API Prefix: {API_PREFIX}")
    print(f"Cookies: {COOKIES_FILE}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load cookies
    cookies = load_cookies(COOKIES_FILE)

    # Create session
    s = make_session(cookies)

    # Authenticate
    print("\n--- Authentication ---")
    if not authenticate(s):
        print("Authentication FAILED. Results may be limited.")
    else:
        print("Authentication OK")

    # Run all exploration
    try:
        explore(s)
    finally:
        s.close()

    print("\n" + "=" * 80)
    print("  EXPLORATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
