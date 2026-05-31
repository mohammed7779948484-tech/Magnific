#!/usr/bin/env python3
"""Phase 3: Get full structure of queued + processing items + queue metadata."""

import json
import os
import sys

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

        # 1. Get queued items FULL detail
        print("=" * 70)
        print("1. /api/creations?status=queued — FULL ITEMS")
        print("=" * 70)
        result = client.get("/api/creations", params={"status": "queued", "per_page": 5})
        data = result.get("data", [])
        
        for i, item in enumerate(data):
            print(f"\n--- Queued Item {i+1} ---")
            # Print only monitoring-relevant fields
            print(f"  id: {item.get('id')}")
            print(f"  status: {item.get('status')}")
            print(f"  tool: {item.get('tool')}")
            print(f"  created_at: {item.get('created_at')}")
            print(f"  date_for_humans: {item.get('date_for_humans')}")
            print(f"  expectTime: {item.get('expectTime')}")
            print(f"  webUrl: {item.get('webUrl')}")
            
            meta = item.get("metadata", {})
            print(f"  [metadata]")
            print(f"    status: {meta.get('status')}")
            print(f"    model: {meta.get('model')}")
            print(f"    api: {meta.get('api')}")
            print(f"    mode: {meta.get('mode')}")
            print(f"    position: {meta.get('position')}")
            print(f"    fast_track: {meta.get('fast_track')}")
            print(f"    multiplier: {meta.get('multiplier')}")
            print(f"    expectedQueuedTime: {meta.get('expectedQueuedTime')}")
            print(f"    expectedGenerationTime: {meta.get('expectedGenerationTime')}")
            print(f"    expectedQueuedTimeParameterized: {meta.get('expectedQueuedTimeParameterized')}")
            print(f"    expectedGenerationTimeParameterized: {meta.get('expectedGenerationTimeParameterized')}")
            print(f"    unlimited: {meta.get('unlimited')}")
            print(f"    generationId: {meta.get('generationId')}")
            print(f"    transactionId: {meta.get('transactionId')}")
            print(f"    creditLedger: {meta.get('creditLedger')}")
            print(f"    creditLedgerTotals: {json.dumps(meta.get('creditLedgerTotals', {}), indent=4)}")
            print(f"    prompt (first 100): {str(meta.get('prompt', ''))[:100]}")

        # 2. Get processing items FULL detail
        print("\n" + "=" * 70)
        print("2. /api/creations?status=processing — FULL ITEMS")
        print("=" * 70)
        result = client.get("/api/creations", params={"status": "processing", "per_page": 5})
        data = result.get("data", [])
        
        for i, item in enumerate(data[:3]):
            print(f"\n--- Processing Item {i+1} ---")
            print(f"  id: {item.get('id')}")
            print(f"  status: {item.get('status')}")
            print(f"  tool: {item.get('tool')}")
            print(f"  created_at: {item.get('created_at')}")
            print(f"  expectTime: {item.get('expectTime')}")
            
            meta = item.get("metadata", {})
            print(f"  [metadata]")
            print(f"    status: {meta.get('status')}")
            print(f"    model: {meta.get('model')}")
            print(f"    api: {meta.get('api')}")
            print(f"    mode: {meta.get('mode')}")
            print(f"    position: {meta.get('position')}")
            print(f"    expectedQueuedTime: {meta.get('expectedQueuedTime')}")
            print(f"    expectedGenerationTime: {meta.get('expectedGenerationTime')}")
            print(f"    creditLedgerTotals: {json.dumps(meta.get('creditLedgerTotals', {}), indent=4)}")
            print(f"    unlimited: {meta.get('unlimited')}")

        # 3. Get a single creation detail to see if there's more queue info
        if data:
            cid = data[0].get("id")
            print(f"\n" + "=" * 70)
            print(f"3. /api/creation/{cid} — FULL DETAIL")
            print("=" * 70)
            detail = client.get(f"/api/creation/{cid}")
            # Print all keys and their values
            for key in detail:
                val = detail[key]
                if isinstance(val, dict) and len(json.dumps(val)) > 300:
                    print(f"  {key}: <dict with {len(val)} keys>")
                    if key == "metadata":
                        for mk, mv in val.items():
                            mv_str = str(mv)
                            if len(mv_str) > 150:
                                mv_str = mv_str[:150] + "..."
                            print(f"    {mk}: {mv_str}")
                elif isinstance(val, str) and len(val) > 150:
                    print(f"  {key}: {val[:150]}...")
                else:
                    print(f"  {key}: {val}")

        # 4. Count creations by status
        print(f"\n" + "=" * 70)
        print("4. CREATION COUNTS BY STATUS")
        print("=" * 70)
        for status in ["processing", "queued", "completed", "failed"]:
            result = client.get("/api/creations", params={"status": status, "per_page": 1})
            meta = result.get("meta", {})
            data_list = result.get("data", [])
            total = meta.get("total", len(data_list))
            print(f"  {status}: {total} items (in response: {len(data_list)})")

        # 5. Explore /api/creations?status=queued more carefully
        print(f"\n" + "=" * 70)
        print("5. /api/creations?status=queued — FULL RESPONSE STRUCTURE")
        print("=" * 70)
        result = client.get("/api/creations", params={"status": "queued"})
        print(f"  Top-level keys: {list(result.keys())}")
        meta = result.get("meta", {})
        print(f"  meta: {json.dumps(meta, indent=2)}")
        links = result.get("links", {})
        print(f"  links: {json.dumps(links, indent=2)}")
        data_list = result.get("data", [])
        print(f"  items count: {len(data_list)}")

        # 6. /api/creations/queue endpoint
        print(f"\n" + "=" * 70)
        print("6. /api/creations/queue — FULL RESPONSE")
        print("=" * 70)
        result = client.get("/api/creations/queue")
        print(f"  Response: {json.dumps(result, indent=2, ensure_ascii=False)[:2000]}")

        # 7. /api/creations/status endpoint
        print(f"\n" + "=" * 70)
        print("7. /api/creations/status — FULL RESPONSE")
        print("=" * 70)
        result = client.get("/api/creations/status")
        print(f"  Response: {json.dumps(result, indent=2, ensure_ascii=False)[:2000]}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
