"""Visual QA — boot the app, screenshot every page, dump to /tmp/calypso_qa/.

Run: python3 scripts/visual_qa.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use sync API
from playwright.async_api import async_playwright


OUT = Path("/tmp/calypso_qa")
OUT.mkdir(exist_ok=True)

PAGES = [
    ("generate", "http://127.0.0.1:8765/generate"),
    ("outputs", "http://127.0.0.1:8765/outputs"),
    ("references", "http://127.0.0.1:8765/references"),
    ("settings", "http://127.0.0.1:8765/settings"),
]


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        # Collect console errors
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(f"PAGE: {exc}"))
        page.on("console", lambda msg: errors.append(f"CONSOLE[{msg.type}]: {msg.text}") if msg.type == "error" else None)

        # 1. Empty state (no outputs, no refs)
        for name, url in PAGES:
            await page.goto(url, wait_until="networkidle")
            await page.screenshot(path=str(OUT / f"{name}_empty.png"), full_page=True)
            print(f"  saved {name}_empty.png")

        # 2. With data — set a key, upload a ref, generate (fake-succeed a job)
        # First save a key via the API
        await page.goto("http://127.0.0.1:8765/settings", wait_until="networkidle")
        await page.fill('input[name="value"]', "fake-fal-key-1234567890abcdef")
        await page.click('button[type="submit"]:has-text("Save")')
        await page.wait_for_load_state("networkidle")

        # Upload a reference (a real visible PNG)
        await page.goto("http://127.0.0.1:8765/references", wait_until="networkidle")
        ref_path = Path("/tmp/qa_ref.png")
        # 200x150 visible PNG (gradient)
        # Use Pillow if available, else fallback to a hand-crafted 200x150 png
        try:
            from PIL import Image, ImageDraw, ImageFont
            # Bright image so the dark preview background doesn't swallow it
            img = Image.new("RGB", (400, 300), (180, 90, 35))
            d = ImageDraw.Draw(img)
            d.rectangle([40, 40, 360, 260], outline=(20, 20, 22), width=6)
            d.text((90, 130), "REFERENCE 01", fill=(240, 236, 228))
            img.save(ref_path, "PNG")
        except ImportError:
            ref_path.write_bytes(bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000001900000009608020000004b"
                "5584f5000000206348524d00000a3a310004000101000000000000000000"
                "0000026247410ec8df5e4500000009704c544500ff0000ff6a1fff00ffff"
                "ffff0101010000000000000000ff000000"
            ))
        await page.set_input_files('input[type="file"]', str(ref_path))
        await page.click('button[type="submit"]:has-text("Upload")')
        await page.wait_for_load_state("networkidle")
        # Wait for the image to actually render
        try:
            await page.wait_for_selector(".ref-cell img", timeout=3000)
            await page.wait_for_function(
                "Array.from(document.querySelectorAll('.ref-cell img')).every(img => img.complete && img.naturalWidth > 0)",
                timeout=3000,
            )
        except Exception as e:
            print(f"  WARN: image wait failed: {e}")
        await page.screenshot(path=str(OUT / "references_with_data.png"), full_page=True)
        print("  saved references_with_data.png")

        # Set settings with data
        await page.goto("http://127.0.0.1:8765/settings", wait_until="networkidle")
        await page.screenshot(path=str(OUT / "settings_with_data.png"), full_page=True)
        print("  saved settings_with_data.png")

        # Generate page with ref dropdown populated
        await page.goto("http://127.0.0.1:8765/generate", wait_until="networkidle")
        await page.screenshot(path=str(OUT / "generate_with_keys.png"), full_page=True)
        print("  saved generate_with_keys.png")

        # Simulate a running job via direct API (since we can't actually call fal.ai)
        from app import jobs as jobs_module
        import time
        job = jobs_module.create_job(
            "Damascus cabinet reveal, cinematic, golden hour, 35mm film",
            model="h3-max", duration=8, resolution="768p",
        )
        with job._lock:
            job.status = "running"
        await page.goto("http://127.0.0.1:8765/generate", wait_until="networkidle")
        await page.screenshot(path=str(OUT / "generate_running.png"), full_page=True)
        print("  saved generate_running.png")

        # Simulate a succeeded job with a real video file
        # Create a tiny fake mp4 (just bytes; video tag will fail to load but UI shows it)
        out_dir = ROOT / "outputs" / job.job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "video.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100)
        with job._lock:
            job.status = "succeeded"
            job.output_path = str(out_dir / "video.mp4")
            job.cost_usd = 0.40
            job.elapsed_seconds = 32.5

        await page.goto("http://127.0.0.1:8765/generate", wait_until="networkidle")
        await page.screenshot(path=str(OUT / "generate_succeeded.png"), full_page=True)
        print("  saved generate_succeeded.png")

        # Outputs page with content
        await page.goto("http://127.0.0.1:8765/outputs", wait_until="networkidle")
        try:
            await page.wait_for_selector(".output-cell video", timeout=3000)
        except Exception:
            pass
        await page.screenshot(path=str(OUT / "outputs_with_data.png"), full_page=True)
        print("  saved outputs_with_data.png")

        # Mobile screenshots
        await ctx.close()
        ctx_mobile = await browser.new_context(viewport={"width": 390, "height": 844})
        page_mobile = await ctx_mobile.new_page()
        for name, url in PAGES:
            await page_mobile.goto(url, wait_until="networkidle")
            await page_mobile.screenshot(path=str(OUT / f"{name}_mobile.png"), full_page=True)
            print(f"  saved {name}_mobile.png")

        await browser.close()

        if errors:
            print("\nConsole/page errors:")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        else:
            print("\nNo console or page errors.")


if __name__ == "__main__":
    asyncio.run(main())
