#!/usr/bin/env python3
"""Explore Magnific internal API to discover queue/status structure."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.auth import Authenticator
from core.client import MagnificClient
from utils.cookie_parser import CookieParser
from utils.logger import setup_logger

logger = setup_logger("explore")

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinj_magnific.txt")


def main():
    # Load cookies and create client
    cookies = CookieParser(COOKIES_FILE).to_curl_cffi_dict()
    client = MagnificClient(cookies=cookies)

    try:
        # Authenticate
        auth = Authenticator(client)
        auth.authenticate()
        print("✅ Authenticated\n")

        # ── Explore endpoints ──
        
        # 1. Get creations list (recent)
        print("=" * 60)
        print("1. GET /api/creations (recent creations)")
        print("=" * 60)
        result = client.get("/api/creations")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
        print("...\n")

        # 2. Get creations with filters
        print("=" * 60)
        print("2. GET /api/creations?status=processing (active jobs)")
        print("=" * 60)
        result = client.get("/api/creations", params={"status": "processing"})
        print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
        print("...\n")

        # 3. Get a specific creation detail
        # Find one from the list first
        creations = client.get("/api/creations")
        data = creations.get("data", [])
        if data:
            first = data[0]
            cid = first.get("id")
            print("=" * 60)
            print(f"3. GET /api/creation/{cid} (single creation detail)")
            print("=" * 60)
            detail = client.get(f"/api/creation/{cid}")
            print(json.dumps(detail, indent=2, ensure_ascii=False)[:3000])
            print("...\n")

        # 4. Try queue/status endpoints
        print("=" * 60)
        print("4. GET /api/creations/queue (try queue endpoint)")
        print("=" * 60)
        try:
            result = client.get("/api/creations/queue")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        except Exception as e:
            print(f"❌ {e}\n")

        # 5. Try user quota/limits
        print("=" * 60)
        print("5. GET /api/user/usage (try usage endpoint)")
        print("=" * 60)
        try:
            result = client.get("/api/user/usage")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        except Exception as e:
            print(f"❌ {e}\n")

        # 6. Try credits/limits
        print("=" * 60)
        print("6. GET /api/credits (try credits endpoint)")
        print("=" * 60)
        try:
            result = client.get("/api/credits")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        except Exception as e:
            print(f"❌ {e}\n")

        # 7. Try subscription/plan
        print("=" * 60)
        print("7. GET /api/subscription (try subscription endpoint)")
        print("=" * 60)
        try:
            result = client.get("/api/subscription")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        except Exception as e:
            print(f"❌ {e}\n")

        # 8. Try active-generations or similar
        print("=" * 60)
        print("8. GET /api/active-generations")
        print("=" * 60)
        try:
            result = client.get("/api/active-generations")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        except Exception as e:
            print(f"❌ {e}\n")

        # 9. Try creations list with pagination
        print("=" * 60)
        print("9. GET /api/creations?page=1&per_page=50 (full structure)")
        print("=" * 60)
        try:
            result = client.get("/api/creations", params={"page": 1, "per_page": 5})
            # Show full structure of first item
            d = result.get("data", [])
            if d:
                print(f"Total items: {result.get('total', '?')}")
                print(f"Page: {result.get('page', '?')}")
                print(f"\nFirst item full structure:")
                print(json.dumps(d[0], indent=2, ensure_ascii=False)[:3000])
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        except Exception as e:
            print(f"❌ {e}\n")

        # 10. Try to start a small gen and capture the render/v4 response structure
        print("=" * 60)
        print("10. Testing start-tti-v2 response structure")
        print("=" * 60)
        try:
            tti = client.post("/api/start-tti-v2", json_data={
                "prompt": "red apple",
                "aspect_ratio": "1:1",
                "family": "imagen-nano-banana-2",
            })
            print(json.dumps(tti, indent=2, ensure_ascii=False)[:2000])
            
            # Check request_tokens
            tokens = tti.get("request_tokens", [])
            family = tti.get("family")
            print(f"\nFamily: {family}")
            print(f"Tokens: {tokens}")
            
            # Try render to see creation response
            if tokens:
                render = client.post("/api/render/v4", json_data={
                    "prompt": "red apple",
                    "family": family,
                    "request_token": tokens[0],
                    "aspect_ratio": "1:1",
                    "resolution": "2k",
                    "width": 2048,
                    "height": 2048,
                    "num_images": 1,
                })
                print(f"\nRender/v4 response:")
                print(json.dumps(render, indent=2, ensure_ascii=False)[:3000])
                
                # Get creation ID and poll once
                creation = render.get("creation", {})
                cid = creation.get("id")
                if cid:
                    time.sleep(3)
                    poll = client.get(f"/api/creation/{cid}")
                    print(f"\nPoll status after 3s:")
                    print(json.dumps(poll, indent=2, ensure_ascii=False)[:3000])
        except Exception as e:
            print(f"❌ {e}\n")

    finally:
        client.close()


if __name__ == "__main__":
    main()
