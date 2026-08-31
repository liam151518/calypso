"""app/jobs.py — in-process job tracker for video generation.

Each generation request becomes a `Job` with an id, status, output path, and
metadata. The Flask server kicks off work in a background thread and exposes
the job to the UI via GET /generate/<job_id>/status (HTMX-pollable).

This module is deliberately small — no broker, no Redis. The process is a
desktop app, and losing jobs on restart is acceptable.

Used by: app/server.py (Generate routes).
"""

from __future__ import annotations

import threading
import time
import traceback
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.falai_client import FalError
from scripts.generate import ENV_PATH as GENERATE_ENV_PATH
from scripts.generate import generate as run_generate
from scripts.h3_client import H3Error


# Project root mirrors scripts/generate.py: outputs live in outputs/<timestamp>/video.mp4
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

VALID_MODELS = ("auto", "h3-cloud", "h3-max", "kling")
VALID_RESOLUTIONS = ("480p", "768p", "1080p")


@dataclass
class Job:
    """A single generation request, tracked by id."""

    job_id: str
    status: str = "queued"  # queued | running | succeeded | failed
    prompt: str = ""
    model: str = "auto"
    reference: str | None = None
    duration: int = 8
    resolution: str = "768p"
    output_path: str | None = None
    cost_usd: float | None = None
    elapsed_seconds: float | None = None
    error: str | None = None
    error_trace: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    batch_id: str | None = None
    references: list[str] = field(default_factory=list)
    effective_prompt: str | None = None
    ref_ids: list[str] = field(default_factory=list)
    draft_id: int | None = None
    brand_id: int | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialisable view (used by both JSON endpoints and template rendering)."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "prompt": self.prompt,
            "model": self.model,
            "reference": self.reference,
            "duration": self.duration,
            "resolution": self.resolution,
            "output_path": self.output_path,
            "cost_usd": self.cost_usd,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "batch_id": self.batch_id,
            "references": list(self.references),
            "effective_prompt": self.effective_prompt,
            "ref_ids": list(self.ref_ids),
            "draft_id": self.draft_id,
            "brand_id": self.brand_id,
        }


# Module-level registry. Thread-safe via Job._lock for individual jobs.
_JOBS: dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()


def make_job_id() -> str:
    """Generate a short, unique job id (timestamp + microseconds, base36)."""
    return time.strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"


def create_job(
    prompt: str,
    *,
    model: str = "auto",
    reference: str | None = None,
    duration: int = 8,
    resolution: str = "768p",
    batch_id: str | None = None,
    references: list[str] | None = None,
    effective_prompt: str | None = None,
    ref_ids: list[str] | None = None,
    draft_id: int | None = None,
    brand_id: int | None = None,
) -> Job:
    """Create and store a new Job in the 'queued' state."""
    job = Job(
        job_id=make_job_id(),
        prompt=prompt,
        model=model,
        reference=reference,
        duration=duration,
        resolution=resolution,
        batch_id=batch_id,
        references=list(references or []),
        effective_prompt=effective_prompt,
        ref_ids=list(ref_ids or []),
        draft_id=draft_id,
        brand_id=brand_id,
    )
    with _JOBS_LOCK:
        _JOBS[job.job_id] = job
    return job


def make_batch_id() -> str:
    return "b-" + time.strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"


def create_batch(
    prompt: str,
    *,
    refs: list[tuple[str, str | None]],
    model: str = "auto",
    duration: int = 8,
    resolution: str = "768p",
    effective_prompt: str | None = None,
    draft_id: int | None = None,
    brand_id: int | None = None,
) -> tuple[str, list[Job]]:
    """Create a batch of jobs from a list of (ref_id, ref_path) tuples.

    Returns the batch_id and the list of created Jobs (NOT yet started —
    the caller decides when to spawn threads).
    """
    batch_id = make_batch_id()
    jobs: list[Job] = []
    for ref_id, ref_path in refs:
        job = create_job(
            prompt,
            model=model,
            reference=ref_path,
            duration=duration,
            resolution=resolution,
            batch_id=batch_id,
            references=[ref_path] if ref_path else [],
            effective_prompt=effective_prompt,
            ref_ids=[ref_id] if ref_id else [],
            draft_id=draft_id,
            brand_id=brand_id,
        )
        jobs.append(job)
    return batch_id, jobs


def list_jobs_for_batch(batch_id: str) -> list[Job]:
    """Return all jobs in a batch, in creation order."""
    with _JOBS_LOCK:
        jobs = [j for j in _JOBS.values() if j.batch_id == batch_id]
    jobs.sort(key=lambda j: j.created_at)
    return jobs


def get_batch_summary(batch_id: str) -> dict | None:
    """Aggregate counts and overall status for a batch."""
    children = list_jobs_for_batch(batch_id)
    if not children:
        return None
    statuses = [j.status for j in children]
    overall = "succeeded" if all(s == "succeeded" for s in statuses) else (
        "failed" if all(s in ("succeeded", "failed") for s in statuses) else "running"
    )
    succeeded = sum(1 for s in statuses if s == "succeeded")
    failed = sum(1 for s in statuses if s == "failed")
    return {
        "batch_id": batch_id,
        "overall": overall,
        "total": len(children),
        "succeeded": succeeded,
        "failed": failed,
        "running": len(children) - succeeded - failed,
    }


def get_job(job_id: str) -> Job | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def list_jobs(limit: int = 50) -> list[Job]:
    """Most recent jobs first."""
    with _JOBS_LOCK:
        jobs = sorted(_JOBS.values(), key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]


def run_job(job: Job) -> None:
    """Execute the generation in the current thread. Called via threading.Thread."""
    with job._lock:
        job.status = "running"
        job.touch()

    try:
        result = run_generate(
            job.prompt,
            model=job.model,
            reference=job.reference,
            duration=job.duration,
            resolution=job.resolution,
            output_dir=OUTPUTS_DIR / job.job_id,
        )
        with job._lock:
            job.status = "succeeded"
            job.output_path = str(result.output_path)
            job.cost_usd = result.cost_usd
            job.elapsed_seconds = result.elapsed_seconds
            job.touch()
    except (FalError, H3Error) as exc:
        with job._lock:
            job.status = "failed"
            job.error = str(exc)
            job.error_trace = traceback.format_exc()
            job.touch()
    except SystemExit as exc:
        # generate.py raises SystemExit for user/input errors (no keys, etc.)
        # Convert to a regular Job failure so the UI can show the message.
        with job._lock:
            job.status = "failed"
            job.error = f"Input error: {exc.code}"
            job.error_trace = None
            job.touch()
    except Exception as exc:  # noqa: BLE001 — broad catch so background thread never dies silently
        with job._lock:
            job.status = "failed"
            job.error = str(exc)
            job.error_trace = traceback.format_exc()
            job.touch()


def start_job(job: Job) -> threading.Thread:
    """Spawn a background thread to run the job. Returns the Thread handle."""
    thread = threading.Thread(target=run_job, args=(job,), daemon=True, name=f"job-{job.job_id}")
    thread.start()
    return thread


def safe_urlretrieve(url: str, dest: Path) -> None:
    """Helper for tests — equivalent to urllib.request.urlretrieve but mockable."""
    urllib.request.urlretrieve(url, dest)
