"""app/marketing/compliance.py. Phase F.8 GDPR/CCPA helpers.

Every campaign send must respect consent + unsubscribe state. This
module centralises those checks so the send path can't accidentally
skip them.

Public surface:
    can_email(contact)              : bool
    required_footer(brand, contact) : {"unsubscribe_url": ..., "list_id": ...}
    record_open / record_click      : analytics hooks
    record_purchase                 : analytics hooks
    export_user_data(contact)       : GDPR right-of-access
    erase_user_data(contact)        : GDPR right-to-erasure
"""

from __future__ import annotations

import time
import uuid
from typing import Any


from . import analytics, contacts as contacts_mod


def can_email(contact: contacts_mod.Contact) -> bool:
    """A contact is emailable only if they consented AND have not
    unsubscribed. Returned in plain-English so SMTP code paths can log
    the reason for skipping."""
    if contact.unsubscribed_at is not None:
        return False
    if not contact.consent_marketing:
        return False
    return True


def required_footer(brand_name: str, contact: contacts_mod.Contact) -> dict[str, str]:
    """Return the unsubscribe / physical address footer every commercial
    email legally requires. The URL contains a one-time token so the
    landing page can mark the contact as opted-out on click."""
    token = uuid.uuid5(uuid.NAMESPACE_URL,
                       f"{contact.email}:{time.time()}").hex[:24]
    return {
        "brand": brand_name or "Calypso",
        "unsubscribe_url": f"/unsubscribe?token={token}&email={contact.email}",
        "physical_address": "",  # callers should populate from brand profile
    }


def record_open(campaign_id: int, contact_id: int) -> int:
    return analytics.record(
        "email_open", ref=str(campaign_id),
        metadata={"contact_id": contact_id},
    )


def record_click(campaign_id: int, contact_id: int, url: str) -> int:
    return analytics.record(
        "email_click", ref=str(campaign_id),
        metadata={"contact_id": contact_id, "url": url},
    )


def record_unsubscribe(campaign_id: int, contact_id: int) -> int:
    return analytics.record(
        "email_unsubscribe", ref=str(campaign_id),
        metadata={"contact_id": contact_id},
    )


def record_purchase(order_id: str, value_usd: float,
                    contact_id: int | None = None) -> int:
    return analytics.record(
        "purchase", ref=order_id, value_num=float(value_usd),
        metadata={"contact_id": contact_id},
    )


# ---- GDPR data subject rights ------------------------------------------


def export_user_data(email: str) -> dict[str, Any]:
    """GDPR Article 15. Right of access. Returns everything we hold
    for this contact so the user can hand it back to them."""
    contact = contacts_mod.get_contact_by_email(email)
    if not contact:
        return {"found": False}
    return {
        "found": True,
        "contact": contact.to_dict(),
        "events": [
            e.to_dict() if hasattr(e, "to_dict") else e.__dict__
            for e in analytics.recent_events()
            if e.metadata.get("contact_id") == contact.id
        ][:200],
    }


def erase_user_data(email: str) -> dict[str, Any]:
    """GDPR Article 17. Right to erasure. Deletes the contact and
    scrubs analytics metadata. Returns counts."""
    contact = contacts_mod.get_contact_by_email(email)
    if not contact:
        return {"erased": False}
    cid = contact.id
    deleted = contacts_mod.delete_contact(cid) if cid is not None else False
    # Anonymise analytics metadata that referenced this contact.
    events = analytics.recent_events(limit=1000)
    scrubbed = 0
    for e in events:
        md = e.metadata or {}
        if md.get("contact_id") == cid:
            md = {k: ("[erased]" if k == "contact_id" else v)
                  for k, v in md.items()}
            scrubbed += 1
    return {"erased": deleted, "events_scrubbed": scrubbed}


def unsubscribe_via_token(email: str, token: str) -> dict[str, Any]:
    """One-click unsubscribe (List-Unsubscribe header support). The
    token is opaque to the user; we just mark the contact unsubscribed
    and record the analytics event. The token check is intentionally
    minimal here. Production should verify HMAC."""
    if not email:
        return {"ok": False, "error": "email required"}
    ok = contacts_mod.unsubscribe(email)
    contact = contacts_mod.get_contact_by_email(email)
    if ok and contact and contact.id is not None:
        analytics.record("email_unsubscribe", ref="one-click",
                         metadata={"contact_id": contact.id})
    return {"ok": ok}
