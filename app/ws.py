"""app.ws. Phase G.6 — Server-Sent Events for render progress.

We don't depend on `flask-sock` so the existing install keeps working
without new system deps. Instead we expose `/api/render/:job_id/events`
as an SSE endpoint; clients subscribe with `EventSource` in the SPA.

Compositor + one_shot publish events via `app.events.publish` which
already exists for the one_shot brief flow.
"""

from __future__ import annotations

import json
import time
from typing import Iterable

from flask import Response, stream_with_context

from app import events as events_mod


# 8-event protocol from spec §10.2.
EVENT_NAMES = {
    "queued": "queued",
    "started": "started",
    "background_ready": "background_ready",
    "cutout_ready": "cutout_ready",
    "layers_composed": "layers_composed",
    "filter_applied": "filter_applied",
    "exported": "exported",
    "failed": "failed",
}


def stream_for(job_id: str, *, heartbeat_s: float = 5.0,
                timeout_s: float = 60.0) -> Iterable[str]:
    """Yield SSE-formatted lines for a single job_id."""
    started = time.time()
    seen: set[str] = set()
    while True:
        queue = events_mod._QUEUE_REGISTRY.get(job_id)  # noqa: SLF001
        events = list(queue.queue) if queue else []
        for ev in events:
            eid = ev.get("id") or ev.get("name") or ""
            if eid in seen:
                continue
            seen.add(eid)
            payload = {"id": eid, "ts": ev.get("ts", time.time()),
                       "data": ev.get("data") or {}}
            yield f"event: {eid}\n"
            yield f"data: {json.dumps(payload)}\n\n"
        if any(e.get("name") == "failed" or e.get("id") == "exported"
               for e in events):
            return
        if time.time() - started > timeout_s:
            yield ": heartbeat timeout\n\n"
            return
        if not events:
            time.sleep(0.2)
            # Periodic heartbeat keeps proxies from closing the stream.
            if time.time() - started > heartbeat_s:
                yield ": heartbeat\n\n"


def sse_response(job_id: str) -> Response:
    return Response(
        stream_with_context(stream_for(job_id)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["stream_for", "sse_response", "EVENT_NAMES"]