"""app/image_jobs.py. Image generation jobs (fal.ai image models).

A small parallel to app/jobs.py: each request becomes a Job with the same
fields but no duration/resolution. We submit synchronously to fal.ai's
`fal.run` (image models are typically fast enough to not need the queue)
and write the resulting PNG to outputs/<job_id>/image.png.

For models that DO require queueing (e.g. Imagen), we fall back to the same
queue path as videos via the BASE_URL submit.

    Used by: app/server.py (POST /api/image-generate, GET /api/image-jobs/<id>).
"""

from __future__ import annotations

import threading
import time
import traceback
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.falai_client import FalAIClient, FalError
from scripts.generate import ENV_PATH as GENERATE_ENV_PATH

from app import jobs as video_jobs  # reuse the registry + threading primitives

OUTPUTS_DIR = video_jobs.OUTPUTS_DIR


@dataclass
class ImageJob:
    """A single image generation request. Mirrors video_jobs.Job for the
    fields the SPA cares about (status, output_rel, cost, model)."""

    job_id: str
    prompt: str
    model: str = "flux-pro/v1.1"
    aspect_ratio: str = "1:1"
    num_images: int = 1
    reference: str | None = None
    ref_ids: list[str] = field(default_factory=list)
    brand_id: int | None = None
    draft_id: int | None = None
    status: str = "queued"
    output_paths: list[str] = field(default_factory=list)  # local file paths
    cost_usd: float | None = None
    elapsed_seconds: float | None = None
    error: str | None = None
    error_trace: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "prompt": self.prompt,
            "model": self.model,
            "aspect_ratio": self.aspect_ratio,
            "num_images": self.num_images,
            "reference": self.reference,
            "ref_ids": list(self.ref_ids),
            "draft_id": self.draft_id,
            "brand_id": self.brand_id,
            "output_paths": [str(p) for p in self.output_paths],
            "output_rel": _rel_for_first(self.output_paths),
            "cost_usd": self.cost_usd,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _rel_for_first(paths: list[str]) -> str | None:
    if not paths:
        return None
    p = Path(paths[0])
    try:
        return f"/outputs/file/{p.parent.name}/{p.name}"
    except Exception:  # noqa: BLE001
        return None


# Module-level registry.
_IMAGE_JOBS: dict[str, ImageJob] = {}
_LOCK = threading.Lock()


def make_job_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"


def create_image_job(
    prompt: str,
    *,
    model: str = "flux-pro/v1.1",
    aspect_ratio: str = "1:1",
    num_images: int = 1,
    reference: str | None = None,
    ref_ids: list[str] | None = None,
    draft_id: int | None = None,
    brand_id: int | None = None,
) -> ImageJob:
    job = ImageJob(
        job_id=make_job_id(),
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        reference=reference,
        ref_ids=list(ref_ids or []),
        draft_id=draft_id,
        brand_id=brand_id,
    )
    with _LOCK:
        _IMAGE_JOBS[job.job_id] = job
    return job


def get_image_job(job_id: str) -> ImageJob | None:
    with _LOCK:
        return _IMAGE_JOBS.get(job_id)


def list_image_jobs(limit: int = 50) -> list[ImageJob]:
    with _LOCK:
        jobs = sorted(_IMAGE_JOBS.values(), key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]


def _read_fal_key() -> str:
    from app.settings import _read_env_file, ENV_PATH

    env = _read_env_file(ENV_PATH)
    return env.get("FAL_API_KEY", "").strip()


def _download(url: str, dest: Path, timeout: int = 60) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Calypso/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def run_image_job(job: ImageJob) -> None:
    """Execute the image generation in the current thread."""
    from app.models import estimate_cost

    with job._lock:
        job.status = "running"
        est = estimate_cost(
            job.model,
            aspect_ratio=job.aspect_ratio,
            num_images=job.num_images,
        )
        if est.get("usd") and job.cost_usd is None:
            job.cost_usd = est["usd"]
        job.touch()

    started = time.monotonic()
    try:
        api_key = _read_fal_key()
        if not api_key:
            raise FalError("FAL_API_KEY not set")

        client = FalAIClient(api_key=api_key)

        # Try the sync fal.run endpoint first; image models typically support it.
        body: dict[str, Any] = {
            "prompt": job.prompt,
            "image_size": job.aspect_ratio,
            "num_images": max(1, job.num_images),
        }
        if job.reference:
            body["image_url"] = job.reference

        try:
            result = client.run_sync(job.model, body)
        except FalError as exc:
            msg = str(exc).lower()
            if "not found" not in msg and "404" not in msg:
                raise
            # Fallback: route through the queue path using a FalVideoRequest.
            from scripts.falai_client import FalVideoRequest

            queue_req = FalVideoRequest(
                model=job.model,  # type: ignore[arg-type]
                prompt=job.prompt,
                duration_seconds=8,
                resolution="768p",
            )
            request_id, status_url = client.submit(queue_req)
            client.wait_for_completion(status_url)
            result = client.get_result(request_id, job.model)  # type: ignore[arg-type]

        urls = _extract_image_urls(result)
        if not urls:
            raise FalError(f"no image URL in result: {result}")

        out_dir = OUTPUTS_DIR / job.job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for idx, url in enumerate(urls[: job.num_images]):
            ext = _guess_ext(url)
            dest = out_dir / f"image-{idx + 1}.{ext}"
            _download(url, dest)
            paths.append(str(dest))

        with job._lock:
            job.status = "succeeded"
            job.output_paths = paths
            job.elapsed_seconds = round(time.monotonic() - started, 2)
            job.touch()
    except FalError as exc:
        with job._lock:
            job.status = "failed"
            job.error = str(exc)
            job.error_trace = traceback.format_exc()
            job.touch()
    except Exception as exc:  # noqa: BLE001
        with job._lock:
            job.status = "failed"
            job.error = str(exc)
            job.error_trace = traceback.format_exc()
            job.touch()


def _extract_image_urls(result: dict[str, Any]) -> list[str]:
    """fal.ai image endpoints return the result as {images: [{url, ...}, ...]}
    or sometimes a flat list. Be defensive.
    """
    if not isinstance(result, dict):
        return []
    if isinstance(result.get("images"), list):
        return [
            img.get("url") if isinstance(img, dict) else str(img)
            for img in result["images"]
            if (isinstance(img, dict) and img.get("url")) or isinstance(img, str)
        ]
    if result.get("image"):
        img = result["image"]
        if isinstance(img, dict) and img.get("url"):
            return [img["url"]]
        if isinstance(img, str):
            return [img]
    return []


def _guess_ext(url: str) -> str:
    lower = url.lower().split("?", 1)[0]
    for ext in ("png", "jpg", "jpeg", "webp"):
        if lower.endswith(f".{ext}"):
            return "jpg" if ext == "jpeg" else ext
    return "png"


def start_image_job(job: ImageJob) -> threading.Thread:
    thread = threading.Thread(
        target=run_image_job, args=(job,), daemon=True, name=f"img-job-{job.job_id}"
    )
    thread.start()
    return thread
