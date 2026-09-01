"""app.automation. Phase G.2 — automation rule engine.

Rules are JSON-driven, simple enough that the SPA can build them
without code:

    {
      "name": "Auto-sneaker-drop",
      "trigger": "product_added",
      "conditions": [
          {"field": "category", "op": "eq", "value": "shoes"},
          {"field": "tags", "op": "contains", "value": "limited"}
      ],
      "action": {
          "kind": "apply_preset",
          "preset_id": 1,
          "schedule_after_minutes": 60
      }
    }

Supported conditions:
  - `eq`, `neq`, `in`        (scalar / list membership)
  - `contains`               (substring or list membership)
  - `gt`, `lt`               (numeric)

Supported actions:
  - `apply_preset`           (render preset against the product)
  - `schedule_caption`       (generate caption variants + queue publish job)

Hook points live in the calling code (products.py, marketing.campaigns).
They call `run_rules_for_event(event, payload)` with the trigger name
plus the relevant entity as `payload`.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app import db as app_db
from app import presets as presets_mod


VALID_TRIGGERS = {
    "product_added",
    "product_updated",
    "campaign_scheduled",
    "output_published",
}

VALID_ACTIONS = {
    "apply_preset",
    "schedule_caption",
}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_rule(
    brand_id: int | None,
    *,
    name: str,
    trigger: str,
    conditions: list[dict],
    action: dict,
    is_active: bool = True,
) -> int:
    if not name.strip():
        raise ValueError("rule name required")
    if trigger not in VALID_TRIGGERS:
        raise ValueError(
            f"unsupported trigger {trigger!r}; valid: {sorted(VALID_TRIGGERS)}"
        )
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    action_kind = action.get("kind")
    if action_kind not in VALID_ACTIONS:
        raise ValueError(
            f"unsupported action.kind {action_kind!r}; valid: {sorted(VALID_ACTIONS)}"
        )
    if not isinstance(conditions, list):
        raise ValueError("conditions must be a list")
    conn = app_db.get_conn()
    cur = conn.execute(
        """INSERT INTO automation_rules(brand_id, name, trigger,
                                          conditions_json, action_json,
                                          is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            brand_id,
            name.strip(),
            trigger,
            json.dumps(conditions),
            json.dumps(action),
            1 if is_active else 0,
            time.time(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_rules(brand_id: int | None = None) -> list[dict]:
    conn = app_db.get_conn()
    if brand_id is None:
        rows = conn.execute(
            "SELECT * FROM automation_rules ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM automation_rules WHERE brand_id = ? "
            "ORDER BY created_at DESC",
            (brand_id,),
        ).fetchall()
    return [_row(r) for r in rows]


def get_rule(rule_id: int) -> dict | None:
    conn = app_db.get_conn()
    row = conn.execute(
        "SELECT * FROM automation_rules WHERE id = ?", (rule_id,)
    ).fetchone()
    return _row(row) if row else None


def set_active(rule_id: int, is_active: bool) -> bool:
    conn = app_db.get_conn()
    cur = conn.execute(
        "UPDATE automation_rules SET is_active = ? WHERE id = ?",
        (1 if is_active else 0, rule_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_rule(rule_id: int) -> bool:
    conn = app_db.get_conn()
    cur = conn.execute(
        "DELETE FROM automation_rules WHERE id = ?", (rule_id,)
    )
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def run_rules_for_event(
    event: str, payload: dict, *, brand_id: int | None = None
) -> list[int]:
    """Fire every active rule matching `event`. Returns output ids."""
    if event not in VALID_TRIGGERS:
        return []
    conn = app_db.get_conn()
    if brand_id is None:
        rows = conn.execute(
            "SELECT * FROM automation_rules "
            "WHERE is_active = 1 AND trigger = ?",
            (event,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM automation_rules "
            "WHERE is_active = 1 AND trigger = ? "
            "AND (brand_id IS NULL OR brand_id = ?)",
            (event, brand_id),
        ).fetchall()
    output_ids: list[int] = []
    for r in rows:
        rule = _row(r)
        if not _conditions_match(rule.get("conditions") or [], payload):
            continue
        try:
            ids = _run_action(rule.get("action") or {}, payload,
                                brand_id=brand_id)
        except Exception:  # noqa: BLE001
            ids = []
        output_ids.extend(ids)
        conn.execute(
            "UPDATE automation_rules SET last_run = ? WHERE id = ?",
            (time.time(), rule["id"]),
        )
    conn.commit()
    return output_ids


def run_rule(rule_id: int, payload: dict | None = None) -> list[int]:
    """Fire a single rule by id."""
    rule = get_rule(rule_id)
    if not rule or not rule.get("is_active"):
        return []
    payload = payload or {}
    if not _conditions_match(rule.get("conditions") or [], payload):
        return []
    return _run_action(
        rule.get("action") or {},
        payload,
        brand_id=rule.get("brand_id"),
    )


# ---------------------------------------------------------------------------
# Condition + action handlers
# ---------------------------------------------------------------------------


def _conditions_match(conditions: list[dict], payload: dict) -> bool:
    for cond in conditions:
        if not _condition_matches(cond, payload):
            return False
    return True


def _condition_matches(cond: dict, payload: dict) -> bool:
    field = cond.get("field")
    op = cond.get("op", "eq")
    value = cond.get("value")
    actual = payload.get(field)
    if op == "eq":
        return actual == value
    if op == "neq":
        return actual != value
    if op == "in":
        if not isinstance(value, list):
            return False
        return actual in value
    if op == "contains":
        if isinstance(actual, list):
            return value in actual
        if isinstance(actual, str):
            return str(value) in actual
        return False
    if op == "gt":
        try:
            return float(actual) > float(value)
        except (TypeError, ValueError):
            return False
    if op == "lt":
        try:
            return float(actual) < float(value)
        except (TypeError, ValueError):
            return False
    return False


def _run_action(
    action: dict, payload: dict, *, brand_id: int | None
) -> list[int]:
    kind = action.get("kind")
    if kind == "apply_preset":
        preset_id = action.get("preset_id")
        product_ids = []
        if "product_id" in payload:
            product_ids = [int(payload["product_id"])]
        elif "product_ids" in payload:
            product_ids = [int(p) for p in payload["product_ids"]]
        if not preset_id or not product_ids:
            return []
        return presets_mod.apply(int(preset_id), product_ids)
    if kind == "schedule_caption":
        # Phase G placeholder: we keep the surface but don't enqueue here
        # — the SPA / scheduler picks it up via the API.
        return []
    return []


def _row(row) -> dict:
    d = dict(row)
    for k_in, k_out in (("conditions_json", "conditions"),
                         ("action_json", "action")):
        raw = d.get(k_in)
        if isinstance(raw, str):
            try:
                d[k_out] = json.loads(raw)
            except json.JSONDecodeError:
                d[k_out] = [] if k_out == "conditions" else {}
        d.pop(k_in, None)
    if "is_active" in d:
        d["is_active"] = bool(d["is_active"])
    return d


__all__ = [
    "VALID_TRIGGERS",
    "VALID_ACTIONS",
    "create_rule",
    "list_rules",
    "get_rule",
    "set_active",
    "delete_rule",
    "run_rules_for_event",
    "run_rule",
]