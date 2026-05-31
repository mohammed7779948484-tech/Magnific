#!/usr/bin/env python3
"""Magnific API Client — Main Entry Point

Usage:
    # Start local API server
    python main.py serve --cookies cookies.txt --port 8080

    # Generate image (CLI)
    python main.py image --cookies cookies.txt --prompt "A golden dragon" --model nano_banana_2 --ratio 16:9 --res 4k -o dragon.png

    # Generate video (CLI)
    python main.py video --cookies cookies.txt --prompt "Eagle soaring" --model seedance_2_pro --ratio 16:9 --duration 5 -o eagle.mp4

    # List available models
    python main.py models
"""

import argparse
import os
import sys
import time
from core.exceptions import RateLimitError

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger

logger = setup_logger("magnific")


def cmd_serve(args):
    """Start the local API server."""
    import uvicorn
    from api.server import create_app

    logger.info(f"Starting Magnific API server on port {args.port}...")

    # Parse cookies-dict if provided
    cookies_dict = None
    if args.cookies_dict:
        cookies_dict = {}
        for pair in args.cookies_dict.split(";"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                cookies_dict[k.strip()] = v.strip()

    if not args.cookies and not cookies_dict:
        logger.error("Either --cookies or --cookies-dict must be provided")
        return

    app = create_app(
        cookies_file=args.cookies,
        cookies_dict=cookies_dict,
        base_url=args.base_url,
        poll_interval=args.poll_interval,
        poll_timeout=args.poll_timeout,
        rate_limit=args.rate_limit,
    )

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


def cmd_image(args):
    """Generate an image via CLI."""
    from config.constants import AspectRatios
    from config.endpoints import Endpoints
    from core.auth import Authenticator
    from core.client import MagnificClient
    from core.poller import Poller
    from core.uploader import Uploader
    from models.base import ModelRegistry
    from utils.cookie_parser import CookieParser
    from utils.file_helpers import FileHelpers

    # Discover models
    ModelRegistry.discover()

    # Load cookies and create client
    cookies = CookieParser(args.cookies).to_curl_cffi_dict()
    client = MagnificClient(cookies=cookies, base_url=args.base_url)

    try:
        # Authenticate
        auth = Authenticator(client)
        auth.authenticate()

        # Get model
        model = ModelRegistry.get_image(args.model)

        # Calculate dimensions
        width, height = AspectRatios.dimensions(args.ratio, args.res)

        # Process references
        temporal_refs = []
        render_refs = []

        if args.reference:
            for ref_str in args.reference:
                parsed = FileHelpers.parse_reference_input(ref_str)
                b64 = FileHelpers.file_to_base64(parsed["source"])

                # Upload to temporal
                uploader = Uploader(client)
                upload_result = uploader.upload_temporal(base64_data=b64)
                temporal_path = upload_result.get("path", "")

                label = parsed.get("name") or "ref"
                ref_type = getattr(args, "ref_type", "reference") or "reference"
                category = getattr(args, "ref_category", "product") or "product"

                temporal_refs.append({
                    "image": f"temporal:{temporal_path}",
                    "type": ref_type,
                    "category": category,
                    "label": label,
                    "frame": None,
                })

                render_refs.append({
                    "id": label,
                    "label": label,
                    "image": b64,
                    "type": ref_type,
                    "category": category,
                    "frame": None,
                })

        logger.info(f"Generating image with {model.display_name}...")
        logger.info(f"  Prompt: {args.prompt[:100]}")
        logger.info(f"  Ratio: {args.ratio}, Resolution: {args.res}, Size: {width}x{height}")

        # Step 1: start-tti-v2
        start_body = model.build_start_tti_body(
            prompt=args.prompt,
            aspect_ratio=args.ratio,
            references=temporal_refs if temporal_refs else None,
        )
        tti_result = client.post("/api/start-tti-v2", json_data=start_body)

        request_token = tti_result.get("request_tokens", [None])[0]
        family = tti_result.get("family")

        if not request_token:
            logger.error("Failed to get request token")
            return

        logger.info(f"  Family: {family}, Token: {request_token[:20]}...")

        # Step 2: render/v4
        render_body = model.build_render_body(
            prompt=args.prompt,
            family=family,
            request_token=request_token,
            aspect_ratio=args.ratio,
            resolution=args.res,
            width=width,
            height=height,
            negative_prompt=args.negative_prompt,
            image_references=render_refs if render_refs else None,
        )
        render_result = client.post("/api/render/v4", json_data=render_body)

        creation_data = render_result.get("creation", {})
        creation_id = creation_data.get("id") or render_result.get("id")

        if not creation_id:
            logger.error(f"No creation ID in response: {str(render_result)[:300]}")
            return

        logger.info(f"  Creation ID: {creation_id}")
        logger.info("  Waiting for generation...")

        # Step 3: Poll
        poller = Poller(client, poll_interval=5, poll_timeout=180)
        poll_result = poller.poll_creation(creation_id, creation_type="image")
        download_url = poll_result.get("download_url")

        if not download_url:
            logger.error("Generation completed but no download URL found")
            return

        logger.info(f"  Image ready!")

        # Step 4: Download
        output_path = args.output or "output.png"
        saved_path = client.download(download_url, output_path)
        logger.info(f"  Saved to: {saved_path}")

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise
    finally:
        client.close()


def cmd_video(args):
    """Generate a video via CLI."""
    from config.endpoints import Endpoints
    from core.auth import Authenticator
    from core.client import MagnificClient
    from core.poller import Poller
    from core.uploader import Uploader
    from models.base import ModelRegistry
    from utils.cookie_parser import CookieParser
    from utils.file_helpers import FileHelpers

    # Discover models
    ModelRegistry.discover()

    # Load cookies and create client
    cookies = CookieParser(args.cookies).to_curl_cffi_dict()
    client = MagnificClient(cookies=cookies, base_url=args.base_url)

    try:
        # Authenticate
        auth = Authenticator(client)
        auth.authenticate()

        # Get model
        model = ModelRegistry.get_video(args.model)
        logger.info(f"Generating video with {model.display_name}...")
        logger.info(f"  Prompt: {args.prompt[:100]}")
        logger.info(f"  Ratio: {args.ratio}, Duration: {args.duration}s")

        # Process references
        uploader = Uploader(client)
        refs = []
        audio_url = None

        if args.ref_image:
            for ref_str in args.ref_image:
                parsed = FileHelpers.parse_reference_input(ref_str)
                name = parsed.get("name") or "ref"

                if FileHelpers.is_url(parsed["source"]):
                    url = parsed["source"]
                else:
                    url = uploader.upload_reference_frame(file_path=parsed["source"])

                refs.append({"type": "image", "url": url, "name": name})

        if args.ref_video:
            for ref_str in args.ref_video:
                parsed = FileHelpers.parse_reference_input(ref_str)
                name = parsed.get("name") or "ref"

                if FileHelpers.is_url(parsed["source"]):
                    url = parsed["source"]
                else:
                    result = uploader.upload_video_audio(file_path=parsed["source"])
                    path = result.get("path", "")
                    url = f"temporal:{path}" if path else parsed["source"]

                refs.append({"type": "video", "url": url, "name": name})
                if not audio_url:
                    audio_url = url

        if args.ref_audio:
            for ref_str in args.ref_audio:
                parsed = FileHelpers.parse_reference_input(ref_str)
                name = parsed.get("name") or "ref"

                if FileHelpers.is_url(parsed["source"]):
                    url = parsed["source"]
                else:
                    result = uploader.upload_video_audio(file_path=parsed["source"])
                    path = result.get("path", "")
                    url = f"temporal:{path}" if path else parsed["source"]

                refs.append({"type": "audio", "url": url, "name": name})
                if not audio_url:
                    audio_url = url

        # Build video body
        video_body = model.build_video_body(
            prompt=args.prompt,
            aspect_ratio=args.ratio,
            duration=args.duration,
            resolution=args.resolution,
            negative_prompt=args.negative_prompt,
            references=refs if refs else None,
            audio_url=audio_url,
            with_sound=args.sound,
        )

        headers = {"x-request-origin": "video_generator"}

        # Auto-retry on rate limit (concurrent creation limit)
        max_retries = 5
        retry_delay = 15
        result = None
        for attempt in range(max_retries):
            try:
                result = client.post(
                    "/api/video/generate?return_creations=true",
                    json_data=video_body,
                    headers=headers,
                )
                break
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait = retry_delay * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s before retry ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    raise

        creations = result.get("data", {}).get("creations", [])
        if not creations:
            logger.error(f"No creation returned: {str(result)[:300]}")
            return

        creation_id = creations[0].get("id")
        logger.info(f"  Creation ID: {creation_id}")
        logger.info("  Waiting for generation (30-120s)...")

        # Poll
        poller = Poller(client, poll_interval=5, poll_timeout=180)
        poll_result = poller.poll_creation(creation_id, creation_type="video")
        download_url = poll_result.get("download_url")

        if not download_url:
            logger.error("Video completed but no download URL found")
            return

        logger.info(f"  Video ready!")

        # Download
        output_path = args.output or "output.mp4"
        saved_path = client.download(download_url, output_path)
        logger.info(f"  Saved to: {saved_path}")

    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        raise
    finally:
        client.close()


def cmd_models(args):
    """List available models."""
    from models.base import ModelRegistry

    ModelRegistry.discover()

    print("\n" + "=" * 60)
    print("  Available Image Models")
    print("=" * 60)
    for slug, model in ModelRegistry.list_images().items():
        print(f"  {slug:<30} {model.display_name:<25} credits: {model.credits}")

    print("\n" + "=" * 60)
    print("  Available Video Models")
    print("=" * 60)
    for slug, model in ModelRegistry.list_videos().items():
        dur = f"{model.duration_range[0]}-{model.duration_range[1]}s"
        print(f"  {slug:<40} {model.display_name:<25} duration: {dur}")

    print()


def main():
    parser = argparse.ArgumentParser(
        prog="magnific",
        description="Magnific API Client — Generate images & videos via Freepik's internal API",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── Serve command ──────────────────────────────────────────────
    serve_parser = subparsers.add_parser("serve", help="Start local API server")
    serve_parser.add_argument("--cookies", default=None, help="Path to cookies file")
    serve_parser.add_argument("--cookies-dict", default=None, help="Cookies as key=value pairs (e.g., name1=val1;name2=val2)")
    serve_parser.add_argument("--base-url", default=None, help="Base URL (default: magnific.com)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    serve_parser.add_argument("--poll-interval", type=int, default=5, help="Poll interval in seconds")
    serve_parser.add_argument("--poll-timeout", type=int, default=180, help="Poll timeout in seconds")
    serve_parser.add_argument("--rate-limit", type=int, default=20, help="Rate limit per minute")
    serve_parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])

    # ── Image command ──────────────────────────────────────────────
    img_parser = subparsers.add_parser("image", help="Generate an image")
    img_parser.add_argument("--cookies", required=True, help="Path to cookies file")
    img_parser.add_argument("--base-url", default=None, help="Base URL (default: magnific.com)")
    img_parser.add_argument("-p", "--prompt", required=True, help="Image prompt")
    img_parser.add_argument("-m", "--model", default="imagen-nano-banana-2", help="Model slug")
    img_parser.add_argument("-r", "--ratio", default="1:1", help="Aspect ratio (default: 1:1)")
    img_parser.add_argument("-s", "--res", default="4k", help="Resolution: 1k, 2k, 4k")
    img_parser.add_argument("-o", "--output", help="Output file path")
    img_parser.add_argument("--negative-prompt", default=None, help="Negative prompt")
    img_parser.add_argument("--reference", action="append", help="Reference: file|label")
    img_parser.add_argument("--ref-type", default="reference", help="Reference type")
    img_parser.add_argument("--ref-category", default="product", help="Reference category")

    # ── Video command ─────────────────────────────────────────────
    vid_parser = subparsers.add_parser("video", help="Generate a video")
    vid_parser.add_argument("--cookies", required=True, help="Path to cookies file")
    vid_parser.add_argument("--base-url", default=None, help="Base URL (default: magnific.com)")
    vid_parser.add_argument("-p", "--prompt", required=True, help="Video prompt")
    vid_parser.add_argument("-m", "--model", default="bytedance-seedance-pro-2.0", help="Model slug")
    vid_parser.add_argument("-r", "--ratio", default="16:9", help="Aspect ratio")
    vid_parser.add_argument("-d", "--duration", type=int, default=5, help="Duration in seconds")
    vid_parser.add_argument("--resolution", default="1080p", help="Resolution: 1080p, 720p, 480p")
    vid_parser.add_argument("-o", "--output", help="Output file path")
    vid_parser.add_argument("--negative-prompt", default="", help="Negative prompt")
    vid_parser.add_argument("--ref-image", action="append", help="Image reference: file|name or url|name")
    vid_parser.add_argument("--ref-video", action="append", help="Video reference: file|name or url|name")
    vid_parser.add_argument("--ref-audio", action="append", help="Audio reference: file|name or url|name")
    vid_parser.add_argument("--sound", action="store_true", help="Add AI sound effects")

    # ── Models command ─────────────────────────────────────────────
    subparsers.add_parser("models", help="List available models")

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "image":
        cmd_image(args)
    elif args.command == "video":
        cmd_video(args)
    elif args.command == "models":
        cmd_models(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
