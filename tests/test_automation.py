"""Phase G.2 — automation rule engine tests."""

from __future__ import annotations

import pytest

from app import automation as automation_mod
from app import db as app_db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "auto.db"
    monkeypatch.setattr(app_db, "DB_PATH", db)
    app_db.reset_for_tests(db)
    app_db.init_db(db)
    yield db


def test_create_rule_returns_id(fresh_db):
    rid = automation_mod.create_rule(
        None, name="R1", trigger="product_added",
        conditions=[], action={"kind": "apply_preset", "preset_id": 1},
    )
    assert rid > 0


def test_create_rule_rejects_unknown_trigger(fresh_db):
    with pytest.raises(ValueError):
        automation_mod.create_rule(
            None, name="x", trigger="bogus",
            conditions=[], action={"kind": "apply_preset"},
        )


def test_create_rule_rejects_unknown_action(fresh_db):
    with pytest.raises(ValueError):
        automation_mod.create_rule(
            None, name="x", trigger="product_added",
            conditions=[], action={"kind": "bogus"},
        )


def test_condition_eq(fresh_db):
    rule = automation_mod.create_rule(
        None, name="eq", trigger="product_added",
        conditions=[{"field": "category", "op": "eq", "value": "shoes"}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    out = automation_mod.run_rules_for_event(
        "product_added", {"category": "shoes"}
    )
    # No preset 1 actually exists, but the rule fired.
    conn = app_db.get_conn()
    last_run = conn.execute(
        "SELECT last_run FROM automation_rules WHERE id = ?", (rule,)
    ).fetchone()["last_run"]
    assert last_run is not None


def test_condition_does_not_match(fresh_db):
    automation_mod.create_rule(
        None, name="neq", trigger="product_added",
        conditions=[{"field": "category", "op": "eq", "value": "shoes"}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    conn = app_db.get_conn()
    last_run = conn.execute(
        "SELECT last_run FROM automation_rules WHERE name = 'neq'"
    ).fetchone()["last_run"]
    assert last_run is None  # never fired


def test_condition_contains_string(fresh_db):
    automation_mod.create_rule(
        None, name="cs", trigger="product_added",
        conditions=[{"field": "name", "op": "contains", "value": "sneaker"}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    automation_mod.run_rules_for_event(
        "product_added", {"name": "limited sneaker edition"}
    )
    conn = app_db.get_conn()
    assert conn.execute(
        "SELECT last_run FROM automation_rules WHERE name = 'cs'"
    ).fetchone()["last_run"] is not None


def test_condition_contains_list(fresh_db):
    automation_mod.create_rule(
        None, name="cl", trigger="product_added",
        conditions=[{"field": "tags", "op": "contains", "value": "limited"}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    automation_mod.run_rules_for_event(
        "product_added", {"tags": ["limited", "exclusive"]}
    )
    conn = app_db.get_conn()
    assert conn.execute(
        "SELECT last_run FROM automation_rules WHERE name = 'cl'"
    ).fetchone()["last_run"] is not None


def test_condition_in(fresh_db):
    automation_mod.create_rule(
        None, name="in", trigger="product_added",
        conditions=[{"field": "category", "op": "in",
                     "value": ["shoes", "apparel"]}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    automation_mod.run_rules_for_event(
        "product_added", {"category": "shoes"}
    )
    conn = app_db.get_conn()
    assert conn.execute(
        "SELECT last_run FROM automation_rules WHERE name = 'in'"
    ).fetchone()["last_run"] is not None


def test_condition_gt_lt(fresh_db):
    automation_mod.create_rule(
        None, name="gt", trigger="product_added",
        conditions=[{"field": "price", "op": "gt", "value": 100}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    automation_mod.run_rules_for_event(
        "product_added", {"price": 150}
    )
    conn = app_db.get_conn()
    assert conn.execute(
        "SELECT last_run FROM automation_rules WHERE name = 'gt'"
    ).fetchone()["last_run"] is not None


def test_inactive_rule_does_not_fire(fresh_db):
    rid = automation_mod.create_rule(
        None, name="off", trigger="product_added",
        conditions=[], action={"kind": "apply_preset", "preset_id": 1},
        is_active=False,
    )
    automation_mod.run_rules_for_event("product_added", {})
    conn = app_db.get_conn()
    assert conn.execute(
        "SELECT last_run FROM automation_rules WHERE id = ?", (rid,)
    ).fetchone()["last_run"] is None


def test_set_active_toggles(fresh_db):
    rid = automation_mod.create_rule(
        None, name="t", trigger="product_added",
        conditions=[], action={"kind": "apply_preset", "preset_id": 1},
    )
    assert automation_mod.set_active(rid, False) is True
    rule = automation_mod.get_rule(rid)
    assert rule["is_active"] is False
    assert automation_mod.set_active(rid, True) is True
    rule = automation_mod.get_rule(rid)
    assert rule["is_active"] is True


def test_run_rule(fresh_db, monkeypatch):
    """run_rule() should fire a single rule regardless of trigger sweep."""
    from app import presets as presets_mod

    called = {"count": 0}

    def fake_apply(preset_id, product_ids):
        called["count"] += 1
        return [1]

    monkeypatch.setattr(presets_mod, "apply", fake_apply)

    rid = automation_mod.create_rule(
        None, name="r", trigger="product_added",
        conditions=[{"field": "category", "op": "eq", "value": "shoes"}],
        action={"kind": "apply_preset", "preset_id": 1},
    )
    ids = automation_mod.run_rule(rid, {"category": "shoes", "product_id": 7})
    assert ids == [1]
    assert called["count"] == 1
    # Now with mismatched condition.
    ids = automation_mod.run_rule(rid, {"category": "boots"})
    assert ids == []
    assert called["count"] == 1


def test_unknown_trigger_no_op(fresh_db):
    assert automation_mod.run_rules_for_event("nope", {}) == []


def test_delete_rule(fresh_db):
    rid = automation_mod.create_rule(
        None, name="del", trigger="product_added",
        conditions=[], action={"kind": "apply_preset", "preset_id": 1},
    )
    assert automation_mod.delete_rule(rid) is True
    assert automation_mod.get_rule(rid) is None