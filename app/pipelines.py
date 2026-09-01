"""app/pipelines.py. Pipeline registry + topological executor.

A Pipeline is a small graph of `nodes` connected by `edges` (typed via
the `inputs`/`outputs` declared in `app/node_schema.NODE_SCHEMAS`).

Public surface:

    create_pipeline(name, nodes, edges, ...)
    list_pipelines()
    get_pipeline(pid) -> dict | None
    update_pipeline(pid, **fields)
    delete_pipeline(pid)
    run_pipeline(pid, *, triggered_by="manual", max_workers=None)

`run_pipeline` is non-blocking from the caller's POV: it spawns a
thread and returns the run record immediately. The thread applies a
topological sort, then walks ready nodes in parallel up to max_workers.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

from . import db as db_mod
from . import pipeline_nodes
from .node_schema import schema_for

# --- exceptions ----------------------------------------------------------


class PipelineError(ValueError):
    """Raised on schema/validation issues at *author* time."""


class PipelineRunError(RuntimeError):
    """Raised when a node runner encounters a hard failure during execution."""


# --- DB helpers ----------------------------------------------------------


def _conn() -> sqlite3.Connection:
    """Open a fresh connection. Callers MUST close it."""
    if not db_mod.DB_PATH.exists():
        db_mod.init_db()
    conn = sqlite3.connect(str(db_mod.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_pipeline(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "description": row["description"] or "",
        "nodes": json.loads(row["nodes_json"] or "[]"),
        "edges": json.loads(row["edges_json"] or "[]"),
        "max_workers": int(row["max_workers"] or 2),
        "enabled": bool(row["enabled"]),
        "created_at": float(row["created_at"] or 0),
        "updated_at": float(row["updated_at"] or 0),
    }


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "pipeline_id": int(row["pipeline_id"]),
        "status": row["status"],
        "log": json.loads(row["log_json"] or "[]"),
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "spent_usd": float(row["spent_usd"] or 0),
        "error": row["error"],
        "triggered_by": row["triggered_by"],
    }


def create_pipeline(
    name: str,
    *,
    description: str = "",
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
    max_workers: int = 2,
    enabled: bool = True,
) -> dict:
    if not name or not name.strip():
        raise PipelineError("name is required")
    nodes = list(nodes or [])
    edges = list(edges or [])
    _validate_graph(nodes, edges)
    now = time.time()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO pipelines(name, description, nodes_json, edges_json, "
            "max_workers, enabled, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                name.strip(),
                description or "",
                json.dumps(nodes),
                json.dumps(edges),
                max(1, int(max_workers)),
                1 if enabled else 0,
                now,
                now,
            ),
        )
        conn.commit()
        pid = int(cur.lastrowid)
    finally:
        conn.close()
    out = get_pipeline(pid)
    assert out is not None
    return out


def list_pipelines() -> list[dict]:
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT * FROM pipelines ORDER BY updated_at DESC, id DESC"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_pipeline(r) for r in rows]


def get_pipeline(pid: int) -> dict | None:
    conn = _conn()
    try:
        cur = conn.execute("SELECT * FROM pipelines WHERE id=?", (int(pid),))
        row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_pipeline(row) if row else None


def update_pipeline(pid: int, **fields) -> dict | None:
    p = get_pipeline(pid)
    if not p:
        return None
    nodes = fields.get("nodes", p["nodes"])
    edges = fields.get("edges", p["edges"])
    if fields.get("nodes") is not None or fields.get("edges") is not None:
        _validate_graph(nodes, edges)
    name = fields.get("name", p["name"])
    description = fields.get("description", p["description"])
    max_workers = fields.get("max_workers", p["max_workers"])
    enabled = fields.get("enabled", p["enabled"])
    now = time.time()
    conn = _conn()
    try:
        conn.execute(
            "UPDATE pipelines SET name=?, description=?, nodes_json=?, edges_json=?, "
            "max_workers=?, enabled=?, updated_at=? WHERE id=?",
            (
                name.strip() if isinstance(name, str) else name,
                description or "",
                json.dumps(nodes),
                json.dumps(edges),
                max(1, int(max_workers)),
                1 if enabled else 0,
                now,
                int(pid),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_pipeline(pid)


def delete_pipeline(pid: int) -> bool:
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM pipelines WHERE id=?", (int(pid),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- runs ----------------------------------------------------------------


def list_runs(pipeline_id: int | None = None, limit: int = 50) -> list[dict]:
    conn = _conn()
    try:
        if pipeline_id is not None:
            cur = conn.execute(
                "SELECT * FROM pipeline_runs WHERE pipeline_id=? "
                "ORDER BY id DESC LIMIT ?",
                (int(pipeline_id), int(limit)),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_run(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    conn = _conn()
    try:
        cur = conn.execute("SELECT * FROM pipeline_runs WHERE id=?", (int(run_id),))
        row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_run(row) if row else None


def _set_run_status(run_id: int, status: str, **patch) -> None:
    """Set status and any other columns. Never touches `log_json` unless
    explicitly passed (the executor appends live via `_append_run_log`)."""
    sets = ["status=?"]
    vals: list[Any] = [status]
    if "log_json" in patch:
        sets.append("log_json=?")
        vals.append(patch.pop("log_json"))
    for k, v in patch.items():
        sets.append(f"{k}=?")
        vals.append(v)
    vals.append(int(run_id))
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE id=?",
            vals,
        )
        conn.commit()
    finally:
        conn.close()


def _append_run_log(run_id: int, log_entries: list[dict]) -> None:
    run = get_run(run_id)
    if not run:
        return
    merged = list(run["log"]) + list(log_entries)
    conn = _conn()
    try:
        conn.execute(
            "UPDATE pipeline_runs SET log_json=? WHERE id=?",
            (json.dumps(merged), int(run_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _create_run_row(pipeline_id: int, triggered_by: str) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO pipeline_runs(pipeline_id, status, log_json, triggered_by) "
            "VALUES (?,?,?,?)",
            (int(pipeline_id), "queued", "[]", triggered_by or "manual"),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


# --- graph validation ---------------------------------------------------


def _validate_graph(nodes: list[dict], edges: list[dict]) -> None:
    """Sanity-check that every node has a known type, every edge points to
    a real node, and we have at most one Trigger."""
    if not nodes:
        return  # empty pipeline is allowed (placeholder)
    known = {n["id"] for n in nodes if isinstance(n, dict) and n.get("id")}
    if not known:
        raise PipelineError("nodes must have unique 'id' values")
    triggers = 0
    for n in nodes:
        t = n.get("type")
        if schema_for(t) is None:
            raise PipelineError(f"unknown node type: {t}")
        if t == "trigger":
            triggers += 1
    if triggers > 1:
        raise PipelineError("only one trigger is allowed per pipeline")
    for e in edges:
        if e.get("source") not in known or e.get("target") not in known:
            raise PipelineError(f"edge references unknown node: {e}")


# --- topological executor -----------------------------------------------


def _topo_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's algorithm. Returns node ids in execution order."""
    incoming: dict[str, int] = {n["id"]: 0 for n in nodes}
    outgoing: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        src, dst = e.get("source"), e.get("target")
        if src in incoming and dst in incoming and src != dst:
            incoming[dst] += 1
            outgoing[src].append(dst)
    ready = [nid for nid, c in incoming.items() if c == 0]
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for child in outgoing[nid]:
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if len(order) != len(nodes):
        raise PipelineError("pipeline graph has a cycle")
    return order


def run_pipeline(
    pipeline_id: int,
    *,
    triggered_by: str = "manual",
    max_workers: int | None = None,
) -> dict:
    """Kick off a run. Returns the run record immediately; execution happens
    in a daemon thread. Use `get_run` to poll for status/log."""
    p = get_pipeline(pipeline_id)
    if not p:
        raise PipelineError(f"pipeline {pipeline_id} not found")
    run_id = _create_run_row(p["id"], triggered_by)
    workers = max(1, int(max_workers or p.get("max_workers") or 2))

    def _exec() -> None:
        _set_run_status(run_id, "running", started_at=time.time(), log_json="[]")
        log_buf: list[dict] = []
        ctx: dict[str, Any] = {
            "pipeline_id": p["id"],
            "run_id": run_id,
            "spent": {"usd": 0.0},
        }

        def _log(node: str, msg: str) -> None:
            entry = {"t": time.time(), "node": node, "msg": msg}
            log_buf.append(entry)
            _append_run_log(run_id, [entry])  # live-stream to disk

        ctx["log"] = _log
        try:
            order = _topo_order(p["nodes"], p["edges"])
            node_map = {n["id"]: n for n in p["nodes"]}
            upstream: dict[str, dict] = {nid: {} for nid in node_map}
            # Build incoming-port index so we can route outputs.
            incoming_ports: dict[str, dict[str, list[str]]] = {
                nid: {} for nid in node_map
            }
            for e in p["edges"]:
                src_port = e.get("source_port") or e.get("sourceHandle") or "flow"
                tgt_port = e.get("target_port") or e.get("targetHandle") or "flow"
                incoming_ports[e["target"]].setdefault(tgt_port, []).append(
                    (e["source"], src_port)
                )
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures: dict[Any, str] = {}
                remaining = set(order)
                completed: set[str] = set()

                def _run_node(nid: str) -> tuple[str, dict]:
                    node = node_map[nid]
                    ntype = node["type"]
                    runner = pipeline_nodes.runner_for(ntype)
                    params = node.get("params") or {}
                    # build `inputs` from upstream + sibling outputs.
                    inputs: dict[str, Any] = {}
                    for port_name, src_pairs in incoming_ports[nid].items():
                        values: list[Any] = []
                        for src_id, src_port in src_pairs:
                            if src_id in upstream and src_port in upstream[src_id]:
                                values.append(upstream[src_id][src_port])
                        # If a port has a single source, expose directly.
                        if len(values) == 1:
                            inputs[port_name] = values[0]
                        elif len(values) > 1:
                            inputs[port_name] = values
                    if runner is None:
                        ctx["log"](ntype, "no runner; skipping")
                        return nid, {"flow": True}
                    try:
                        result = runner(ctx, params, inputs) or {}
                    except Exception as exc:  # noqa: BLE001
                        ctx["log"](ntype, f"FAILED: {exc}")
                        raise
                    ctx["log"](ntype, f"ok -> {sorted(result.keys())}")
                    return nid, {"flow": True, **result}

                # Schedule ready nodes (incoming == 0) initially.
                scheduled = set()
                initial = [nid for nid in order if all(
                    e["target"] != nid for e in p["edges"]
                )]
                for nid in initial:
                    futures[pool.submit(_run_node, nid)] = nid
                    scheduled.add(nid)

                while futures:
                    done = next(
                        iter([f for f in futures if f.done()]),
                        None,
                    )
                    if done is None:
                        time.sleep(0.05)
                        continue
                    nid = futures.pop(done)
                    remaining.discard(nid)
                    try:
                        _, payload = done.result()
                        upstream[nid] = payload
                        completed.add(nid)
                    except Exception as exc:  # noqa: BLE001
                        _append_run_log(run_id, log_buf)
                        _set_run_status(
                            run_id,
                            "failed",
                            finished_at=time.time(),
                            error=str(exc),
                            spent_usd=float(ctx["spent"].get("usd", 0.0)),
                        )
                        return
                    # Now schedule any newly-ready nodes.
                    for child_id in node_map:
                        if child_id in scheduled:
                            continue
                        # "Done" means we've received its payload. We store
                        # the payload under `completed` so the `in upstream`
                        # check no longer aliases with the empty placeholder dict.
                        if child_id in completed:
                            continue
                        sources = [
                            e["source"] for e in p["edges"] if e["target"] == child_id
                        ]
                        if sources and all(s in completed for s in sources):
                            futures[pool.submit(_run_node, child_id)] = child_id
                            scheduled.add(child_id)
            _append_run_log(run_id, log_buf)
            _set_run_status(
                run_id,
                "succeeded",
                finished_at=time.time(),
                spent_usd=float(ctx["spent"].get("usd", 0.0)),
            )
        except PipelineError as exc:
            _append_run_log(run_id, log_buf)
            _set_run_status(
                run_id,
                "failed",
                finished_at=time.time(),
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            _append_run_log(run_id, log_buf)
            _set_run_status(
                run_id,
                "failed",
                finished_at=time.time(),
                error=f"unexpected: {exc}",
            )

    t = threading.Thread(
        target=_exec,
        name=f"pipeline-run-{run_id}-{uuid.uuid4().hex[:6]}",
        daemon=True,
    )
    t.start()
    return get_run(run_id)
