#!/usr/bin/env python3
"""Concurrent image generation test script.

Starts the server, sends N requests in parallel, reports results.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = 8090
BASE_URL = f"http://localhost:{PORT}"
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinj_magnific.txt")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

PROMPTS = [
    "A golden dragon flying over a medieval castle at sunset, cinematic lighting",
    "Cyberpunk city street at night with neon pink and blue lights, rain reflections",
    "Cute cat wearing a tiny top hat sitting in a vintage coffee shop",
    "Futuristic sports car speeding on a coastal highway with mountains",
    "Underwater coral reef teeming with colorful tropical fish, sunlight beams",
    "Astronaut planting a flag on Mars surface with Earth visible in sky",
    "Japanese cherry blossom garden with a red wooden bridge over a pond",
    "Magical enchanted forest with glowing bioluminescent mushrooms at twilight",
    "Vintage steampunk robot playing a grand piano in a smoky jazz bar",
    "Crystal ice palace floating above pink clouds at golden hour sunrise",
    "Desert oasis with palm trees under a brilliant starry milky way sky",
    "Steampunk airship flying over Victorian London in foggy evening",
    "White wolf howling at vivid green and purple aurora borealis",
    "Tropical waterfall cascading into a hidden turquoise pool in lush jungle",
    "Abstract colorful fluid art swirl, metallic gold and deep blue, 4k detail",
]


def start_server():
    """Start the FastAPI server in background."""
    print(f"[Server] Starting on port {PORT}...")
    proc = subprocess.Popen(
        [sys.executable, "main.py", "serve",
         "--cookies", COOKIES_FILE,
         "--port", str(PORT),
         "--rate-limit", "100",
         "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return proc


def wait_for_server(max_wait=30):
    """Wait until server is ready."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            req = urllib.request.Request(f"{BASE_URL}/openapi.json")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    print(f"[Server] Ready! ({time.time() - start:.1f}s)")
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def send_request(req_id: int, prompt: str, wait: bool = True) -> dict:
    """Send a single image generation request."""
    payload = {
        "prompt": prompt,
        "model": "imagen-nano-banana-2",
        "aspect_ratio": "1:1",
        "resolution": "2k",
        "wait": wait,
        "download": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/image/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            elapsed = time.time() - start
            result = json.loads(resp.read())
            result["_req_id"] = req_id
            result["_elapsed"] = elapsed
            result["_http_code"] = resp.status
            return result
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"error": e.reason}
        return {
            "_req_id": req_id,
            "_elapsed": elapsed,
            "_http_code": e.code,
            "success": False,
            "status": "http_error",
            "message": body.get("detail") or str(e),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "_req_id": req_id,
            "_elapsed": elapsed,
            "_http_code": 0,
            "success": False,
            "status": "connection_error",
            "message": str(e),
        }


def run_concurrent(num_requests: int):
    """Run N concurrent requests and report results."""
    print(f"\n{'='*60}")
    print(f"  Launching {num_requests} concurrent image generation requests")
    print(f"  Target: localhost:{PORT}/api/image/generate")
    print(f"  Model: imagen-nano-banana-2 | Resolution: 2k | Wait: true")
    print(f"{'='*60}\n")

    start_all = time.time()
    results = []

    # Use ThreadPoolExecutor for true concurrent HTTP requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = {}
        for i in range(num_requests):
            prompt = PROMPTS[i % len(PROMPTS)]
            print(f"  [Req {i+1}] Launching: {prompt[:60]}...")
            future = executor.submit(send_request, i + 1, prompt, wait=True)
            futures[future] = i + 1

        print(f"\n  All {num_requests} requests launched. Waiting for results...\n")

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    total_time = time.time() - start_all

    # Sort by request ID
    results.sort(key=lambda r: r["_req_id"])

    # Report
    print(f"\n{'='*60}")
    print(f"  RESULTS ({total_time:.1f}s total)")
    print(f"{'='*60}")

    success = 0
    fail = 0

    for r in results:
        rid = r["_req_id"]
        http_code = r.get("_http_code", 0)
        status = r.get("status", "?")
        is_success = r.get("success", False)
        elapsed = r.get("_elapsed", 0)
        creation_id = r.get("creation_id", "?")

        if is_success and status in ("completed", "processing"):
            print(f"  [Req {rid:2d}] ✅ SUCCESS — status={status} http={http_code} time={elapsed:.1f}s id={creation_id}")
            success += 1
        else:
            msg = r.get("message", "?")[:80]
            print(f"  [Req {rid:2d}] ❌ FAIL — status={status} http={http_code} time={elapsed:.1f}s msg={msg}")
            fail += 1

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {success}/{num_requests} succeeded, {fail}/{num_requests} failed")
    print(f"  Total wall time: {total_time:.1f}s")
    if success > 0:
        avg = sum(r["_elapsed"] for r in results if r.get("success")) / success
        print(f"  Avg per-request time: {avg:.1f}s")
    print(f"{'='*60}")

    # Save detailed results
    result_file = os.path.join(RESULTS_DIR, f"run_{num_requests}_{int(time.time())}.json")
    with open(result_file, "w") as f:
        json.dump({
            "num_requests": num_requests,
            "success": success,
            "fail": fail,
            "total_time": total_time,
            "results": results,
        }, f, indent=2)
    print(f"\n  Detailed results saved: {result_file}")

    return success, fail


def main():
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    # Start server
    server_proc = start_server()

    try:
        # Wait for server
        if not wait_for_server():
            print("[ERROR] Server failed to start within 30s")
            sys.exit(1)

        # Run concurrent test
        success, fail = run_concurrent(num)

        # Return exit code
        sys.exit(0 if fail == 0 else 1)

    finally:
        # Stop server
        print(f"\n[Server] Stopping...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        print("[Server] Stopped.")


if __name__ == "__main__":
    main()
