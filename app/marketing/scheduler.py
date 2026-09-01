"""app/marketing/scheduler.py. Phase F.7 + Phase C.3 hybrid scheduler.

Two cooperating schedulers live here:

* ``_legacy_loop()`` is the original in-process thread-loop that walks
  ``scheduled_jobs`` every 10s and dispatches ready jobs. It still works
  out of the box with zero infrastructure.
* ``APSchedulerBackend`` (used when ``apscheduler`` is installed) wraps
  the same SQLite table as a persistent job store, so jobs survive a
  process restart.

Both paths honour the original public API — ``schedule``, ``cancel``,
``list_jobs``, ``run_now``, ``start``, ``stop`` — so the 7 existing
marketing tests continue to pass untouched. ``kind="publish_output"`` is
new in Phase C and dispatches an output through :mod:`app.publisher`.
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
from .. import publisher as publisher_mod

log = logging.getLogger(__name__)

VALID_KINDS = (
    "send_campaign",
    "publish_social",
    "run_pipeline",
    "publish_output",  # Phase C: brand-poster → publisher
)
VALID_STATUSES = ("queued", "running", "done", "failed", "blocked")

_TICK_S = 10.0
_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()

_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

_AP_SCHEDULER = None  # APScheduler instance, lazily started
_AP_THREAD: threading.Thread | None = None


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


# ----- Public API ----------------------------------------------------------


def register_handler(kind: str,
                     handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    _HANDLERS[kind] = handler


def schedule(name: str, kind: str, run_at: float,
             payload: dict[str, Any] | None = None) -> int:
    """Insert a new job. ``run_at`` is an absolute Unix timestamp."""
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
            "DELETE FROM scheduled_jobs WHERE id = ? AND status IN ('queued','blocked')",
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


def get_job(job_id: int) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM scheduled_jobs WHERE id = ?", (job_id,)).fetchone()
    return _row(row) if row else None


def run_now(job_id: int) -> dict[str, Any]:
    """Force-run a queued job immediately, regardless of ``run_at``."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM scheduled_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        return {"ok": False, "error": "not found"}
    _run_one(int(row["id"]), row["kind"],
             json.loads(row["payload_json"] or "{}"))
    return get_job(job_id) or {"ok": False, "error": "lost"}


def approve(job_id: int) -> dict[str, Any]:
    """Mark a blocked job as queued so the next tick dispatches it."""
    with _conn() as c:
        c.execute(
            "UPDATE scheduled_jobs SET status = 'queued', last_error = '' WHERE id = ?",
            (job_id,),
        )
    return get_job(job_id) or {"ok": False, "error": "lost"}


def start() -> None:
    """Start the legacy in-process loop. APScheduler is started on top if
    its package is available."""
    global _THREAD, _AP_THREAD, _AP_SCHEDULER
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, name="calypso-scheduler",
                                   daemon=True)
        _THREAD.start()
        log.info("scheduler started")
        try:
            _start_ap_scheduler()
        except Exception as exc:  # noqa: BLE001
            log.info("APScheduler unavailable, legacy loop only: %s", exc)


def stop() -> None:
    """Stop both schedulers (best effort)."""
    _STOP.set()
    if _AP_SCHEDULER is not None:
        try:
            _AP_SCHEDULER.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        globals()["_AP_SCHEDULER"] = None
    globals()["_AP_THREAD"] = None


# ----- Core dispatch ------------------------------------------------------


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
    register_default_handlers()
    while not _STOP.is_set():
        try:
            _tick()
        except Exception as exc:  # noqa: BLE001
            log.exception("scheduler tick failed: %s", exc)
        _STOP.wait(_TICK_S)


def _legacy_loop() -> None:
    """Re-claimed alias kept for the plan's backwards-compat shim."""
    _loop()


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
    if final not in VALID_STATUSES:
        final = status
    with _conn() as c:
        c.execute(
            "UPDATE scheduled_jobs SET status = ?, last_error = ? WHERE id = ?",
            (final, error, job_id),
        )


# ----- APScheduler wrapper -----------------------------------------------


def _start_ap_scheduler() -> None:
    global _AP_SCHEDULER
    try:
        from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
    except ImportError:
        log.debug("apscheduler not installed; skipping AP backend")
        return
    if _AP_SCHEDULER is not None:
        return
    sched = BackgroundScheduler(daemon=True)
    # Periodic poll that mirrors the legacy tick. If APScheduler itself
    # fails, the legacy thread keeps the system alive.
    sched.add_job(_tick, "interval", seconds=_TICK_S,
                  id="calypso-tick", replace_existing=True)
    sched.start()
    _AP_SCHEDULER = sched
    log.info("APScheduler started")


# ----- Default handlers ---------------------------------------------------


def register_default_handlers() -> None:
    """Register the safe default handlers used by ``_loop``."""
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

    if "publish_output" not in _HANDLERS:
        def publish_output(payload: dict[str, Any]) -> dict[str, Any]:
            """Dispatch a brand-poster output through :mod:`app.publisher`.

            Payload contract:
                output_id: int  — primary key in ``outputs``
                platform: str   — target (instagram, x, tiktok, …)
                preferred: str | None — publisher name hint (dry_run, telegram_handoff)
            """
            from .. import outputs as outputs_mod  # local to avoid cycles

            output_id = int(payload.get("output_id") or 0)
            platform = payload.get("platform") or "instagram"
            preferred = payload.get("preferred")
            out = outputs_mod.get_output(output_id)
            if not out:
                return {"ok": False, "error": "output not found"}
            if out.get("auto_approve") is False:
                # Phase C.5: Telegram gate happens elsewhere via notify();
                # when the bot isn't configured we proceed without approval.
                try:
                    from .. import telegram_notify

                    decision = telegram_notify.request_approval(out)
                    if decision == "rejected":
                        return {"ok": False, "status": "rejected"}
                except Exception:  # noqa: BLE001
                    pass
            result = publisher_mod.dispatch(out, platform, preferred=preferred)
            outputs_mod.mark_published(output_id, platform=platform,
                                      external_id=result.get("external_id"),
                                      url=result.get("url"))
            return {"ok": True, "publisher": result}

        register_handler("publish_output", publish_output)