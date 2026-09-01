"""app/marketing/contacts.py. Phase F.1 contact store.

Stores contacts with consent flags (GDPR/CCPA aware). All writes go
through helpers so the consent timestamps stay consistent.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .. import db as app_db


def _row_factory(cursor, name):  # noqa: ANN001
    return {col[0]: cursor.fetchone() and None}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


@dataclass
class Contact:
    id: int | None
    email: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    tags: list[str] = None  # type: ignore[assignment]
    source: str = ""
    consent_marketing: bool = False
    consent_at: float | None = None
    unsubscribed_at: float | None = None
    custom: dict[str, Any] = None  # type: ignore[assignment]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tags"] = list(self.tags or [])
        d["custom"] = dict(self.custom or {})
        return d


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def upsert_contact(contact: Contact) -> int:
    email = _normalize_email(contact.email)
    if "@" not in email:
        raise ValueError("invalid email")
    now = time.time()
    tags_json = json.dumps(list(contact.tags or []))
    custom_json = json.dumps(dict(contact.custom or {}))
    with _conn() as c:
        existing = c.execute(
            "SELECT id, consent_marketing, consent_at, unsubscribed_at FROM contacts WHERE email = ?",
            (email,),
        ).fetchone()
        if existing is None:
            consent = 1 if contact.consent_marketing else 0
            consent_at = now if contact.consent_marketing else None
            cur = c.execute(
                """INSERT INTO contacts
                   (email, first_name, last_name, phone, tags_json, source,
                    consent_marketing, consent_at, unsubscribed_at, custom_json,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (email, contact.first_name, contact.last_name, contact.phone,
                 tags_json, contact.source, consent, consent_at,
                 contact.unsubscribed_at, custom_json, now, now),
            )
            return int(cur.lastrowid)
        cid = int(existing["id"])
        # Update only the fields the caller actually changed; preserve
        # consent / unsubscribe state unless explicitly toggled.
        consent = existing["consent_marketing"]
        consent_at = existing["consent_at"]
        unsubscribed_at = existing["unsubscribed_at"]
        if contact.consent_marketing and not consent:
            consent = 1
            consent_at = now
        if contact.unsubscribed_at is not None:
            unsubscribed_at = contact.unsubscribed_at
        c.execute(
            """UPDATE contacts
               SET first_name = ?, last_name = ?, phone = ?, tags_json = ?,
                   source = ?, consent_marketing = ?, consent_at = ?,
                   unsubscribed_at = ?, custom_json = ?, updated_at = ?
               WHERE id = ?""",
            (contact.first_name, contact.last_name, contact.phone, tags_json,
             contact.source, consent, consent_at, unsubscribed_at, custom_json,
             now, cid),
        )
        return cid


def get_contact(cid: int) -> Contact | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM contacts WHERE id = ?", (cid,)).fetchone()
    return _row_to_contact(row) if row else None


def get_contact_by_email(email: str) -> Contact | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM contacts WHERE email = ?", (_normalize_email(email),)
        ).fetchone()
    return _row_to_contact(row) if row else None


def unsubscribe(email: str, *, at: float | None = None) -> bool:
    ts = at or time.time()
    with _conn() as c:
        cur = c.execute(
            "UPDATE contacts SET unsubscribed_at = ?, updated_at = ? "
            "WHERE email = ? AND unsubscribed_at IS NULL",
            (ts, ts, _normalize_email(email)),
        )
    return cur.rowcount > 0


def delete_contact(cid: int) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM contacts WHERE id = ?", (cid,))
    return cur.rowcount > 0


def list_contacts(
    *, tag: str | None = None, query: str | None = None,
    subscribed_only: bool = False, limit: int = 200,
) -> list[Contact]:
    sql = "SELECT * FROM contacts"
    params: list[Any] = []
    clauses: list[str] = []
    if tag:
        clauses.append("tags_json LIKE ?")
        params.append(f"%\"{tag}\"%")
    if query:
        clauses.append("(email LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like])
    if subscribed_only:
        clauses.append("unsubscribed_at IS NULL")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_contact(r) for r in rows]


def bulk_import(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Bulk-upsert contacts. Used by the Phase D CSV importer extension.

    Returns `{imported, skipped}` counts."""
    imported = 0
    skipped = 0
    for row in rows:
        try:
            upsert_contact(Contact(
                id=None,
                email=row.get("email", ""),
                first_name=row.get("first_name", "") or row.get("name", ""),
                last_name=row.get("last_name", ""),
                phone=row.get("phone", ""),
                tags=row.get("tags") or [],
                source=row.get("source") or "import",
                consent_marketing=bool(row.get("consent_marketing")),
            ))
            imported += 1
        except Exception:  # noqa: BLE001
            skipped += 1
    return {"imported": imported, "skipped": skipped}


def _row_to_contact(row: sqlite3.Row) -> Contact:
    return Contact(
        id=int(row["id"]),
        email=row["email"],
        first_name=row["first_name"] or "",
        last_name=row["last_name"] or "",
        phone=row["phone"] or "",
        tags=json.loads(row["tags_json"] or "[]"),
        source=row["source"] or "",
        consent_marketing=bool(row["consent_marketing"]),
        consent_at=row["consent_at"],
        unsubscribed_at=row["unsubscribed_at"],
        custom=json.loads(row["custom_json"] or "{}"),
    )
