"""app.events. Tiny in-process pub/sub for one_shot + future WebSocket push.

Two flavors:

  - `register(event, fn)` / `publish(event, payload)` — fire callbacks
    for any subscriber (used by tests + CLI flows).
  - `enqueue(job_id, event_name, data)` / `drain(job_id)` — append
    structured events to a per-job queue (consumed by the SSE endpoint
    in `app.ws`).

The module is intentionally minimal — Phase G.6 layers a richer
WebSocket / SSE surface on top without changing this contract.
"""

from __future__ import annotations

import queue
import time
from typing import Any, Callable

_subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
_QUEUE_REGISTRY: dict[str, "queue.Queue[dict[str, Any]]"] = {}


# ---- subscriber-style API ----


def register(event: str, fn: Callable[[dict[str, Any]], None]) -> None:
    """Register a callback for an event name. Safe to call multiple times."""
    _subscribers.setdefault(event, []).append(fn)


def unregister(event: str, fn: Callable[[dict[str, Any]], None]) -> None:
    if event in _subscribers and fn in _subscribers[event]:
        _subscribers[event].remove(fn)


def publish(event: str, payload: dict[str, Any]) -> None:
    for fn in list(_subscribers.get(event, [])):
        try:
            fn(payload)
        except Exception:  # noqa: BLE001
            pass


# ---- queue-style API (per job) ----


def queue_for(job_id: str) -> "queue.Queue[dict[str, Any]]":
    q = _QUEUE_REGISTRY.get(job_id)
    if q is None:
        q = queue.Queue()
        _QUEUE_REGISTRY[job_id] = q
    return q


def enqueue(job_id: str, event_name: str, data: dict | None = None) -> None:
    """Append an event to a job's queue. Also publishes to subscribers."""
    q = queue_for(job_id)
    payload = {"name": event_name, "id": event_name,
               "data": data or {}, "ts": time.time()}
    q.put(payload)
    publish(job_id, payload)
    publish(event_name, payload)


def drain(job_id: str) -> list[dict[str, Any]]:
    """Pop every queued event for this job (destructive)."""
    q = _QUEUE_REGISTRY.get(job_id)
    if q is None:
        return []
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            break
    return out


def clear_queue(job_id: str | None = None) -> None:
    """Test helper: drop a job's queue (or all queues)."""
    if job_id is None:
        _QUEUE_REGISTRY.clear()
    else:
        _QUEUE_REGISTRY.pop(job_id, None)


def clear() -> None:
    """Test helper: drop all subscribers + queues."""
    _subscribers.clear()
    _QUEUE_REGISTRY.clear()


__all__ = [
    "register", "unregister", "publish",
    "queue_for", "enqueue", "drain", "clear_queue",
    "clear",
]