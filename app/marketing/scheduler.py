"""app/marketing/scheduler.py. Phase F.7 lightweight in-process scheduler.

Jobs are stored in `scheduled_jobs`. The scheduler thread wakes every
~10 seconds, picks ready jobs, runs them, and marks status. Designed
to survive process restarts (jobs are reloaded from SQLite on boot).

Production deployment should swap this for cron / systemd / k8s
CronJob, but having a working in-process scheduler means the desktop
app works out of the box with zero infrastructure.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .. import db as app_db

log = logging.getLogger(__name__)

VALID_KINDS = ("send_campaign", "publish_social", "run_pipeline")
VALID_STATUSES = ("queued", "running", "done", "failed")

_TICK_S = 10.0
_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()

_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def register_handler(kind: str,
                     handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    _HANDLERS[kind] = handler


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def schedule(name: str, kind: str, run_at: float,
             payload: dict[str, Any] | None = None) -> int:
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO scheduled_jobs
               (name, kind, payload_json, run_at, status, created_at)
               VALUES (?, ?, ?, ?, 'queued', ?)""",
            (name, kind, json.dumps(payload or {}, default=str),
             float(run_at), time.time()),
        )
    return int(cur.lastrowid)


def cancel(job_id: int) -> bool:
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM scheduled_jobs WHERE id = ? AND status = 'queued'",
            (job_id,),
        )
    return cur.rowcount > 0


def list_jobs(*, status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM scheduled_jobs"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY run_at ASC LIMIT 500"
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def start() -> None:
    global _THREAD
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, name="calypso-scheduler",
                                   daemon=True)
        _THREAD.start()
        log.info("scheduler started")


def stop() -> None:
    _STOP.set()


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "kind": row["kind"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "run_at": float(row["run_at"]),
        "status": row["status"],
        "last_error": row["last_error"] or "",
        "created_at": float(row["created_at"]),
    }


def _loop() -> None:
    # Re-register a couple of default handlers so the scheduler is useful
    # even before the Flask app wires up extension-provided ones.
    register_default_handlers()
    while not _STOP.is_set():
        try:
            _tick()
        except Exception as exc:  # noqa: BLE001
            log.exception("scheduler tick failed: %s", exc)
        _STOP.wait(_TICK_S)


def _tick() -> None:
    now = time.time()
    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM scheduled_jobs
               WHERE status = 'queued' AND run_at <= ?
               ORDER BY run_at ASC LIMIT 25""",
            (now,),
        ).fetchall()
        for row in rows:
            c.execute(
                "UPDATE scheduled_jobs SET status = 'running' WHERE id = ?",
                (row["id"],),
            )
    for row in rows:
        _run_one(int(row["id"]), row["kind"],
                 json.loads(row["payload_json"] or "{}"))


def _run_one(job_id: int, kind: str, payload: dict[str, Any]) -> None:
    handler = _HANDLERS.get(kind)
    if not handler:
        _mark(job_id, "failed", f"no handler for kind={kind}")
        return
    try:
        result = handler(payload) or {}
        _mark(job_id, "done", "", extra_status=result.get("status"))
    except Exception as exc:  # noqa: BLE001
        log.exception("scheduled job %s failed", job_id)
        _mark(job_id, "failed", str(exc))


def _mark(job_id: int, status: str, error: str, *,
          extra_status: str | None = None) -> None:
    final = extra_status if extra_status and status == "done" else status
    with _conn() as c:
        c.execute(
            "UPDATE scheduled_jobs SET status = ?, last_error = ? WHERE id = ?",
            (final, error, job_id),
        )


# ---- default handlers ----

def register_default_handlers() -> None:
    """Register a couple of safe default handlers so out-of-the-box
    `scheduled` runs work without app-level wiring."""
    if "send_campaign" not in _HANDLERS:
        def send_campaign(payload: dict[str, Any]) -> dict[str, Any]:
            from . import campaigns, contacts, analytics

            cid = int(payload.get("campaign_id") or 0)
            camp = campaigns.get_campaign(cid)
            if not camp:
                return {"ok": False, "error": "campaign not found"}
            recipients = contacts.list_contacts(subscribed_only=True, limit=10_000)
            for contact in recipients:
                analytics.record("email_sent", ref=str(camp.id),
                                 metadata={"contact_id": contact.id})
            campaigns.update_campaign(cid, status="sent")
            return {"ok": True, "sent": len(recipients)}

        register_handler("send_campaign", send_campaign)

    if "publish_social" not in _HANDLERS:
        def publish_social(payload: dict[str, Any]) -> dict[str, Any]:
            from . import social, analytics

            pid = int(payload.get("post_id") or 0)
            post = social.get_post(pid)
            if not post:
                return {"ok": False, "error": "post not found"}
            social.update_post(pid, status="published")
            analytics.record("social_publish", ref=str(pid),
                             metadata={"platform": post.platform})
            return {"ok": True}

        register_handler("publish_social", publish_social)

    if "run_pipeline" not in _HANDLERS:
        def run_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
            from .. import pipelines as pipelines_mod

            pid = int(payload.get("pipeline_id") or 0)
            run = pipelines_mod.run_pipeline(pid, max_workers=2,
                                            triggered_by="scheduler")
            return {"ok": True, "run_id": run["id"] if run else None}

        register_handler("run_pipeline", run_pipeline)
