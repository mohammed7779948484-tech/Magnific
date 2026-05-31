#!/usr/bin/env python3
"""Extract full model schema from v2/ai-models and a video model for reference."""

import json
from curl_cffi.requests import Session

s = Session(impersonate="chrome136")
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
})

# v2/ai-models — full image model schema
r = s.get("https://www.magnific.com/app/api/v2/ai-models")
models = r.json()

# Find an image model with full metadata
image_model = None
for m in models:
    if m.get("tool") == "text-to-image" and m.get("metadata", {}).get("api"):
        image_model = m
        break

if not image_model:
    # Try to find one with maximum keys
    image_models = [m for m in models if m.get("tool") == "text-to-image"]
    image_model = max(image_models, key=lambda x: len(json.dumps(x)))

print("=" * 80)
print("FULL IMAGE MODEL SCHEMA (from v2/ai-models)")
print("=" * 80)
print(json.dumps(image_model, indent=2, ensure_ascii=False)[:5000])

# Find a video model with full metadata
video_model = None
for m in models:
    if m.get("tool") == "video-generator" and m.get("metadata", {}).get("api"):
        video_model = m
        break

if not video_model:
    video_models = [m for m in models if m.get("tool") == "video-generator"]
    video_model = max(video_models, key=lambda x: len(json.dumps(x)))

print("\n" + "=" * 80)
print("FULL VIDEO MODEL SCHEMA (from v2/ai-models)")
print("=" * 80)
print(json.dumps(video_model, indent=2, ensure_ascii=False)[:5000])

# Video ai-models schema (bytedance as example)
r2 = s.get("https://www.magnific.com/app/api/video/ai-models")
vid_models = r2.json()

bytedance_models = vid_models.get("bytedance", [])
if bytedance_models:
    # Get the most detailed one
    best = max(bytedance_models, key=lambda x: len(json.dumps(x)))
    print("\n" + "=" * 80)
    print("FULL VIDEO AI-MODEL SCHEMA (from video/ai-models, bytedance)")
    print("=" * 80)
    print(json.dumps(best, indent=2, ensure_ascii=False)[:5000])

# Custom models schema
r3 = s.get("https://www.magnific.com/app/api/custom-models")
custom = r3.json()
print("\n" + "=" * 80)
print("CUSTOM MODELS SCHEMA (top-level keys + first item)")
print("=" * 80)
print(f"Top-level keys: {list(custom.keys())}")
for key in custom:
    val = custom[key]
    if isinstance(val, list):
        print(f"  {key}: list with {len(val)} items")
        if val:
            print(f"    First item keys: {list(val[0].keys())}")
    else:
        print(f"  {key}: {type(val).__name__}")

if custom.get("public_custom_models"):
    print("\nFirst custom model full structure:")
    print(json.dumps(custom["public_custom_models"][0], indent=2, ensure_ascii=False)[:3000])

s.close()
