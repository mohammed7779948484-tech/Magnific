#!/usr/bin/env python3
"""Deep explore Magnific API - phase 2: queue, limits, filters."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.auth import Authenticator
from core.client import MagnificClient
from utils.cookie_parser import CookieParser

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinj_magnific.txt")

def main():
    cookies = CookieParser(COOKIES_FILE).to_curl_cffi_dict()
    client = MagnificClient(cookies=cookies)

    try:
        auth = Authenticator(client)
        auth.authenticate()
        print("✅ Authenticated\n")

        endpoints_to_try = [
            # Queue variations
            ("/api/creations/queue", None, "Queue endpoint (already confirmed)"),
            ("/api/creations/status", None, "Status endpoint"),
            ("/api/creations?status=queued", None, "Queued creations"),
            ("/api/creations?status=pending", None, "Pending creations"),
            ("/api/creations?tool=text-to-image", None, "Image creations"),
            ("/api/creations?tool=video-generator", None, "Video creations"),
            
            # User/account
            ("/api/user", None, "User profile"),
            ("/api/user/profile", None, "User profile v2"),
            ("/api/user/settings", None, "User settings"),
            ("/api/user/quota", None, "Quota"),
            ("/api/user/plan", None, "Plan"),
            ("/api/user/limits", None, "Limits"),
            ("/api/user/collections", None, "Collections"),
            
            # Credits/billing
            ("/api/credits/balance", None, "Credits balance"),
            ("/api/credits/usage", None, "Credits usage"),
            ("/api/billing", None, "Billing"),
            ("/api/billing/usage", None, "Billing usage"),
            ("/api/subscription/usage", None, "Subscription usage"),
            
            # Generation limits
            ("/api/generations", None, "Generations list"),
            ("/api/generations/active", None, "Active generations"),
            ("/api/generations/limits", None, "Generation limits"),
            ("/api/generations/count", None, "Generation count"),
            ("/api/generation-limits", None, "Generation limits v2"),
            
            # Stats
            ("/api/stats", None, "Stats"),
            ("/api/stats/usage", None, "Stats usage"),
            ("/api/dashboard", None, "Dashboard"),
            ("/api/dashboard/stats", None, "Dashboard stats"),
            
            # Queue variations
            ("/api/queue", None, "Queue v2"),
            ("/api/queue/status", None, "Queue status"),
            ("/api/jobs", None, "Jobs"),
            ("/api/jobs/active", None, "Active jobs"),
            ("/api/tasks", None, "Tasks"),
            ("/api/tasks/active", None, "Active tasks"),
            
            # Rate limit
            ("/api/rate-limit", None, "Rate limit info"),
            ("/api/rate-limits", None, "Rate limits info"),
            ("/api/concurrency", None, "Concurrency info"),
            ("/api/concurrency/limit", None, "Concurrency limit"),
        ]

        found_endpoints = []
        
        for path, params, desc in endpoints_to_try:
            try:
                result = client.get(path, params=params) if params else client.get(path)
                content_type = str(type(result))
                
                # Check if it's actual JSON data (not HTML)
                if isinstance(result, dict) and ("<!DOCTYPE" not in str(result)):
                    found_endpoints.append(path)
                    print(f"✅ {path}")
                    print(f"   Description: {desc}")
                    print(f"   Response: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                    print()
                elif isinstance(result, str) and "<!DOCTYPE" in result:
                    print(f"❌ {path} → 404 HTML")
                else:
                    print(f"⚠️  {path} → {content_type}: {str(result)[:200]}")
                    print()
            except Exception as e:
                err = str(e)
                if "404" in err or "Not Found" in err:
                    print(f"❌ {path} → 404")
                elif "401" in err:
                    print(f"🔒 {path} → 401 (auth required but exists!)")
                    found_endpoints.append(path)
                elif "422" in err:
                    print(f"⚠️  {path} → 422 (exists, wrong params)")
                    found_endpoints.append(path)
                else:
                    print(f"❌ {path} → {err[:100]}")
        
        print("\n" + "=" * 60)
        print("  DISCOVERED ENDPOINTS SUMMARY")
        print("=" * 60)
        for ep in found_endpoints:
            print(f"  ✅ {ep}")
        print(f"\n  Total discovered: {len(found_endpoints)}")

        # Deep dive into creations structure
        print("\n" + "=" * 60)
        print("  DEEP DIVE: /api/creations full structure")
        print("=" * 60)
        
        # Get all creations with different statuses
        for status_filter in [None, "processing", "completed", "failed"]:
            params = {"per_page": 3}
            if status_filter:
                params["status"] = status_filter
            
            result = client.get("/api/creations", params=params)
            data = result.get("data", [])
            
            print(f"\n--- status={status_filter or 'all'} ({len(data)} items) ---")
            
            # Show top-level keys
            top_keys = list(result.keys())
            print(f"  Top-level keys: {top_keys}")
            
            if data:
                item = data[0]
                item_keys = list(item.keys())
                print(f"  Item keys: {item_keys}")
                print(f"  status field: '{item.get('status', 'N/A')}'")
                print(f"  tool field: '{item.get('tool', 'N/A')}'")
                
                metadata = item.get("metadata", {})
                meta_keys = list(metadata.keys())
                print(f"  metadata keys: {meta_keys}")
                
                # Check for retryInfo
                retry_info = metadata.get("retryInfo")
                if retry_info:
                    print(f"  retryInfo keys: {list(retry_info.keys())}")
                    print(f"  retryInfo: {json.dumps(retry_info, indent=2, ensure_ascii=False)[:500]}")
                
                # Check for queue position
                if "queue_position" in item:
                    print(f"  queue_position: {item['queue_position']}")
                if "queue" in item:
                    print(f"  queue: {item['queue']}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
