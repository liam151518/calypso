"""generate.py. Single-command video generator.

The simplest possible interface to the pipeline:

    python3 scripts/generate.py "damascus cabinet reveal, cinematic"

→ reads your API keys from .env
→ routes to the best video model for the job (or use --model to override)
→ downloads the result to outputs/<timestamp>/video.mp4
→ prints the path so you can preview it

You can also drive it from a reference image or video:

    python3 scripts/generate.py --reference ~/Downloads/damascus.png "spin the cabinet"

Setup: see README → "Quick start" → adds FAL_API_KEY (and optionally MINIMAX_API_KEY).

Tests: tests/test_generate.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Make sibling scripts importable when run as `python3 scripts/generate.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from falai_client import FalAIClient, FalError, FalVideoRequest  # noqa: E402
from h3_client import H3Client, H3Error, VideoRequest as H3VideoRequest  # noqa: E402
from reference_picker import pick, load_references  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
ENV_PATH = PROJECT_ROOT / ".env"


Model = Literal["auto", "h3-cloud", "h3-max", "kling"]


@dataclass
class GenerateResult:
    """The output of a generation run."""

    output_path: Path
    model: str
    duration_seconds: int
    resolution: str
    cost_usd: float
    elapsed_seconds: float
    reference_used: str | None = None
    source_request_id: str | None = None


# ---------- env loading ----------

def load_env() -> dict[str, str]:
    """Load .env file into a dict. Never overwrites existing os.environ entries."""
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env[key] = value
        os.environ.setdefault(key, value)
    return env


def require_env(name: str) -> str:
    """Read an env var or exit with a clear message."""
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"error: {name} is not set.", file=sys.stderr)
        print(f"  add it to {ENV_PATH} (see .env.example for the format)", file=sys.stderr)
        print(f"  or: echo '{name}=...' >> {ENV_PATH}", file=sys.stderr)
        sys.exit(2)
    return val


# ---------- reference handling ----------

def resolve_reference(explicit: str | None) -> tuple[Path | None, str | None]:
    """Pick a reference image. Explicit path takes priority; otherwise pick one from Folder A.

    Returns (local_path, source_url). source_url is set if the reference came from
    a scraped entry with a remote URL.
    """
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.exists():
            print(f"error: reference not found: {p}", file=sys.stderr)
            sys.exit(2)
        return p, None

    refs = load_references()
    if not refs:
        return None, None

    chosen = pick(refs, format="image")
    if not chosen:
        return None, None

    local = PROJECT_ROOT / chosen.local_path
    if not local.exists():
        # Reference metadata exists but the asset is missing. Skip silently.
        return None, None

    return local, chosen.source_url


def upload_to_temp_host(local_path: Path) -> str:
    """Upload a local file to a temporary public URL so the cloud APIs can fetch it.

    We use 0x0.st (free, no auth, no signup). If it fails, we fall back to a stub URL
    so the request still gets routed; the API will reject it but the error will be clear.
    """
    try:
        with local_path.open("rb") as fh:
            req = urllib.request.Request(
                "https://0x0.st",
                data=fh.read(),
                headers={"User-Agent": "calypso-pipeline/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                url = resp.read().decode().strip()
                if url.startswith("http"):
                    return url
    except (urllib.error.URLError, OSError):
        pass
    # Last-resort: return the local path as a file:// URL. The cloud APIs won't accept
    # this, but the user will see a clear "image URL not reachable" error.
    return f"file://{local_path}"


# ---------- model routing ----------

def pick_model(explicit: str | None, has_h3_cloud: bool, has_fal: bool) -> str:
    """Pick the actual model to use.

    - explicit == "auto": prefer H3 cloud if available, else fal.ai H3 Max
    - explicit == specific model name: use that one
    """
    if explicit and explicit != "auto":
        return explicit

    if has_h3_cloud:
        return "h3-cloud"
    if has_fal:
        return "h3-max"
    print("error: no API keys available. Set FAL_API_KEY or MINIMAX_API_KEY in .env", file=sys.stderr)
    sys.exit(2)


# ---------- main generation ----------

def generate(
    prompt: str,
    *,
    model: str = "auto",
    reference: str | None = None,
    duration: int = 8,
    resolution: str = "768p",
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> GenerateResult:
    """Generate a video and save it locally.

    Returns a GenerateResult; raises SystemExit on user/input errors, FalError/H3Error on API errors.
    """
    env = load_env()
    fal_key = env.get("FAL_API_KEY", "").strip()
    h3_key = env.get("MINIMAX_API_KEY", "").strip()
    chosen_model = pick_model(model, bool(h3_key), bool(fal_key))

    ref_path, ref_url = resolve_reference(reference)
    ref_url_or_uploaded = ref_url
    if ref_path and not ref_url:
        # Reference is local. We need to upload it for the API to see it.
        if dry_run:
            print(f"[dry-run] would upload {ref_path} to a public host")
            ref_url_or_uploaded = f"https://example.invalid/{ref_path.name}"
        else:
            ref_url_or_uploaded = upload_to_temp_host(ref_path)
            print(f"  uploaded reference → {ref_url_or_uploaded}")

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = (output_dir or (OUTPUTS_DIR / timestamp))
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()

    if chosen_model == "h3-cloud":
        if not h3_key:
            print("error: MINIMAX_API_KEY required for h3-cloud", file=sys.stderr)
            sys.exit(2)
        client = H3Client(api_key=h3_key)
        req = H3VideoRequest(prompt=prompt, duration_seconds=duration, resolution=resolution)
        if ref_url_or_uploaded:
            req.reference_image_urls = [ref_url_or_uploaded]
        out_path = out_dir / "video.mp4"
        if dry_run:
            print(f"[dry-run] would call H3 API with prompt={prompt!r}, ref={ref_url_or_uploaded}")
            cost = 0.0
            request_id = "dry-run"
        else:
            request_id = client.submit(req)
            client.wait_for_completion(request_id)
            url = client.get_result_url(request_id)
            urllib.request.urlretrieve(url, out_path)
            cost = req.estimated_cost_usd()

    elif chosen_model in ("h3-max", "kling"):
        if not fal_key:
            print("error: FAL_API_KEY required for fal.ai models", file=sys.stderr)
            sys.exit(2)
        client = FalAIClient(api_key=fal_key)
        m = "minimax/h3-max" if chosen_model == "h3-max" else "kling-video/v2.6/pro"
        req = FalVideoRequest(model=m, prompt=prompt, duration_seconds=duration, resolution=resolution)
        if ref_url_or_uploaded:
            req.reference_image_urls = [ref_url_or_uploaded]
        out_path = out_dir / "video.mp4"
        if dry_run:
            print(f"[dry-run] would call fal.ai {m} with prompt={prompt!r}, ref={ref_url_or_uploaded}")
            cost = 0.0
            request_id = "dry-run"
        else:
            request_id, status_url = client.submit(req)
            client.wait_for_completion(status_url)
            result = client.get_result(request_id, m)
            url = (result.get("video") or {}).get("url")
            if not url:
                raise FalError(f"no video URL in fal.ai result: {result}")
            urllib.request.urlretrieve(url, out_path)
            cost = req.estimated_cost_usd()
    else:
        raise SystemExit(f"unknown model: {chosen_model}")

    elapsed = time.monotonic() - started
    return GenerateResult(
        output_path=out_path,
        model=chosen_model,
        duration_seconds=duration,
        resolution=resolution,
        cost_usd=cost,
        elapsed_seconds=elapsed,
        reference_used=str(ref_path) if ref_path else None,
        source_request_id=request_id,
    )


# ---------- CLI ----------

def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a video from a prompt (and optional reference).",
    )
    parser.add_argument("prompt", nargs="?", help="The text prompt describing the video you want")
    parser.add_argument(
        "--model",
        choices=["auto", "h3-cloud", "h3-max", "kling"],
        default="auto",
        help="Which model to route to (default: auto. H3 cloud if key present, else H3 Max via fal.ai)",
    )
    parser.add_argument(
        "--reference",
        help="Path to a reference image or video to drive the generation. If omitted, one is picked from Folder A.",
    )
    parser.add_argument("--duration", type=int, default=8, help="Clip duration in seconds (default: 8)")
    parser.add_argument("--resolution", choices=["480p", "768p", "1080p"], default="768p")
    parser.add_argument("--output-dir", help="Where to save the output (default: outputs/<timestamp>/)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually call the API; just print the plan")
    parser.add_argument("--check-keys", action="store_true", help="Show which API keys are configured and exit")
    args = parser.parse_args()

    if args.check_keys:
        env = load_env()
        print(f"FAL_API_KEY:      {'set' if env.get('FAL_API_KEY') else 'MISSING'}")
        print(f"MINIMAX_API_KEY:  {'set' if env.get('MINIMAX_API_KEY') else 'MISSING'}")
        print(f"TELEGRAM_BOT_TOKEN: {'set' if env.get('TELEGRAM_BOT_TOKEN') else 'not set (optional)'}")
        return 0

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    try:
        result = generate(
            args.prompt,
            model=args.model,
            reference=args.reference,
            duration=args.duration,
            resolution=args.resolution,
            output_dir=output_dir,
            dry_run=args.dry_run,
        )
    except (FalError, H3Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130

    print()
    print(f"  video:   {result.output_path}")
    print(f"  model:   {result.model}")
    print(f"  cost:    ${result.cost_usd:.2f}")
    print(f"  elapsed: {result.elapsed_seconds:.1f}s")
    if result.reference_used:
        print(f"  ref:     {result.reference_used}")
    print()
    print(f"open: open {result.output_path}  # macOS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
