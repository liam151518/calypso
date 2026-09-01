"""tests/test_marketing.py. Phase F marketing surface tests."""

from __future__ import annotations

import time

import pytest

from app import db as db_mod
from app.marketing import (
    analytics,
    campaigns,
    compliance,
    contacts,
    pages,
    scheduler,
    social,
)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(db_mod, "DB_PATH", db)
    db_mod.init_db(db)
    yield


# ---------- contacts ----------


def test_contact_upsert_then_get():
    cid = contacts.upsert_contact(contacts.Contact(
        id=None, email="Alice@Example.com", first_name="Alice",
        tags=["vip"], consent_marketing=True,
    ))
    assert cid > 0
    c = contacts.get_contact(cid)
    assert c is not None
    assert c.email == "alice@example.com"  # normalised
    assert c.tags == ["vip"]
    assert c.consent_marketing is True
    assert c.consent_at is not None


def test_contact_rejects_invalid_email():
    with pytest.raises(ValueError):
        contacts.upsert_contact(contacts.Contact(id=None, email="no-at"))


def test_contact_upsert_preserves_consent():
    cid = contacts.upsert_contact(contacts.Contact(
        id=None, email="x@y.com", consent_marketing=True,
    ))
    # re-upsert without consent should keep the original consent
    contacts.upsert_contact(contacts.Contact(id=None, email="x@y.com",
                                             first_name="New"))
    c = contacts.get_contact(cid)
    assert c.consent_marketing is True


def test_contact_unsubscribe_blocks_emailing():
    contacts.upsert_contact(contacts.Contact(
        id=None, email="u@y.com", consent_marketing=True,
    ))
    c = contacts.get_contact_by_email("u@y.com")
    assert compliance.can_email(c) is True
    contacts.unsubscribe("u@y.com")
    c2 = contacts.get_contact_by_email("u@y.com")
    assert compliance.can_email(c2) is False


def test_contact_bulk_import_returns_counts():
    res = contacts.bulk_import([
        {"email": "a@x.com", "first_name": "A", "consent_marketing": True},
        {"email": "b@x.com", "first_name": "B", "consent_marketing": True},
        {"email": "no-email"},  # invalid
    ])
    assert res["imported"] == 2
    assert res["skipped"] == 1


def test_contact_list_filtered_by_tag():
    contacts.upsert_contact(contacts.Contact(id=None, email="a@x.com", tags=["vip"]))
    contacts.upsert_contact(contacts.Contact(id=None, email="b@x.com", tags=["basic"]))
    items = contacts.list_contacts(tag="vip")
    emails = [c.email for c in items]
    assert "a@x.com" in emails
    assert "b@x.com" not in emails


def test_contact_subscribed_only_excludes_unsubscribed():
    contacts.upsert_contact(contacts.Contact(id=None, email="a@x.com",
                                             consent_marketing=True))
    contacts.upsert_contact(contacts.Contact(id=None, email="b@x.com",
                                             consent_marketing=True))
    contacts.unsubscribe("b@x.com")
    items = contacts.list_contacts(subscribed_only=True)
    emails = [c.email for c in items]
    assert "a@x.com" in emails
    assert "b@x.com" not in emails


# ---------- campaigns ----------


def test_campaign_create_and_status_lifecycle():
    cid = campaigns.create_campaign(campaigns.Campaign(
        id=None, name="Launch", subject="Hi", channel="email",
    ))
    assert cid > 0
    campaigns.update_campaign(cid, status="scheduled",
                              send_at=time.time() + 3600)
    camp = campaigns.get_campaign(cid)
    assert camp.status == "scheduled"
    assert camp.send_at is not None


def test_campaign_invalid_status_rejected():
    with pytest.raises(ValueError):
        campaigns.create_campaign(campaigns.Campaign(
            id=None, name="x", channel="email", status="bogus"))


def test_campaign_invalid_channel_rejected():
    with pytest.raises(ValueError):
        campaigns.create_campaign(campaigns.Campaign(
            id=None, name="x", channel="smoke-signal"))


def test_campaign_delete():
    cid = campaigns.create_campaign(campaigns.Campaign(id=None, name="x"))
    assert campaigns.delete_campaign(cid) is True
    assert campaigns.get_campaign(cid) is None


# ---------- landing pages ----------


def test_page_slug_normalised():
    pid = pages.create_page(pages.LandingPage(
        id=None, slug="My Cool Page!", title="My Cool Page"))
    p = pages.get_page(pid)
    assert p.slug == "my-cool-page"


def test_page_form_capture():
    pid = pages.create_page(pages.LandingPage(
        id=None, slug="signup", title="Sign up"))
    pages.update_page(pid, published=True)
    sid = pages.record_submission(pid, {"email": "a@b.com"})
    assert sid > 0
    assert pages.count_submissions(pid) == 1


# ---------- social ----------


def test_social_post_validates_platform():
    with pytest.raises(ValueError):
        social.create_post(social.SocialPost(id=None, platform="myspace",
                                             body="hi"))


def test_social_post_calculates_over_limit():
    pid = social.create_post(social.SocialPost(
        id=None, platform="x", body="x" * 500))
    p = social.get_post(pid)
    assert p.to_dict()["over_limit"] is True


def test_social_update_status():
    pid = social.create_post(social.SocialPost(
        id=None, platform="x", body="hello"))
    social.update_post(pid, status="queued")
    assert social.get_post(pid).status == "queued"


# ---------- analytics ----------


def test_analytics_record_and_aggregate():
    analytics.record("email_sent", ref="camp-1")
    analytics.record("email_open", ref="camp-1")
    analytics.record("purchase", ref="o-1", value_num=42.5)
    agg = analytics.aggregate(since=time.time() - 60)
    assert agg["email_sent"]["count"] == 1
    assert agg["email_open"]["count"] == 1
    assert agg["purchase"]["count"] == 1
    assert agg["purchase"]["sum"] == 42.5


def test_analytics_rejects_unknown_kind():
    with pytest.raises(ValueError):
        analytics.record("not_a_kind")


# ---------- scheduler ----------


def test_scheduler_schedules_and_lists():
    jid = scheduler.schedule(
        "test-job", "send_campaign", time.time() + 60,
        payload={"campaign_id": 0},
    )
    jobs = scheduler.list_jobs()
    assert any(j["id"] == jid for j in jobs)


def test_scheduler_rejects_unknown_kind():
    with pytest.raises(ValueError):
        scheduler.schedule("x", "unicorn", time.time())


def test_scheduler_cancels_queued():
    jid = scheduler.schedule("x", "send_campaign", time.time() + 60)
    assert scheduler.cancel(jid) is True
    assert all(j["id"] != jid or j["status"] != "queued"
               for j in scheduler.list_jobs())


def test_scheduler_runs_immediate_handler():
    """Run the scheduler tick synchronously. The default send_campaign
    handler should mark the campaign as sent."""
    from app.marketing.scheduler import register_default_handlers, _HANDLERS, _tick
    register_default_handlers()
    contacts.upsert_contact(contacts.Contact(
        id=None, email="a@x.com", consent_marketing=True))
    cid = campaigns.create_campaign(campaigns.Campaign(
        id=None, name="x"))
    # schedule in the past so the tick picks it up
    scheduler.schedule("send-x", "send_campaign", time.time() - 1,
                       payload={"campaign_id": cid})
    assert "send_campaign" in _HANDLERS
    _tick()
    camp = campaigns.get_campaign(cid)
    assert camp.status == "sent"


# ---------- compliance ----------


def test_compliance_footer_contains_unsubscribe_url():
    contacts.upsert_contact(contacts.Contact(
        id=None, email="a@x.com", consent_marketing=True))
    c = contacts.get_contact_by_email("a@x.com")
    footer = compliance.required_footer("Calypso", c)
    assert footer["unsubscribe_url"].startswith("/unsubscribe")
    assert "token=" in footer["unsubscribe_url"]


def test_compliance_export_returns_contact_data():
    contacts.upsert_contact(contacts.Contact(
        id=None, email="e@x.com", consent_marketing=True))
    out = compliance.export_user_data("e@x.com")
    assert out["found"] is True
    assert out["contact"]["email"] == "e@x.com"


def test_compliance_export_unknown_email_returns_found_false():
    out = compliance.export_user_data("nobody@x.com")
    assert out["found"] is False


def test_compliance_erase_deletes_contact():
    contacts.upsert_contact(contacts.Contact(
        id=None, email="e@x.com", consent_marketing=True))
    out = compliance.erase_user_data("e@x.com")
    assert out["erased"] is True
    assert contacts.get_contact_by_email("e@x.com") is None


def test_compliance_one_click_unsubscribe_records_event():
    contacts.upsert_contact(contacts.Contact(
        id=None, email="o@x.com", consent_marketing=True))
    res = compliance.unsubscribe_via_token("o@x.com", "fake-token")
    assert res["ok"] is True
    # analytics event was recorded
    events = analytics.recent_events(kind="email_unsubscribe")
    assert len(events) >= 1
