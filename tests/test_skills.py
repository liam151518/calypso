"""Tests for :mod:`app.skills` and :mod:`app.skills_store`."""

from __future__ import annotations

import pytest

from app import skills as skills_mod
from app import skills_store
from app.skills import (
    Skill,
    apply_post,
    apply_pre,
    build_system_prompt,
    enabled_skills,
    get_skill,
    list_skills,
    save_user_skill,
    sync_filesystem_to_db,
    delete_user_skill,
)


@pytest.fixture(autouse=True)
def _clean_db(tmp_path, monkeypatch):
    """Point the user_skills DB at a throwaway file for each test."""
    import app.db as app_db
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "skills.db")
    monkeypatch.setattr(skills_store, "_conn",
                        lambda: app_db.connect())
    skills_store.ensure_table()
    skills_store.ensure_builtin_seeded()
    yield


def test_builtin_skills_load():
    skills = skills_mod.load_all_builtins()
    slugs = {s.slug for s in skills}
    assert {"ugc_video", "image_ad", "prompt_enhancement", "caption_optimizer"} <= slugs
    for s in skills:
        assert s.builtin is True
        assert s.content_md, f"{s.slug} has empty body"


def test_list_skills_includes_builtins_and_overrides():
    skills = list_skills()
    slugs = {s.slug for s in skills}
    assert "ugc_video" in slugs
    assert all(isinstance(s, Skill) for s in skills)


def test_enable_and_disable():
    save_user_skill(slug="ugc_video", enabled=False)
    enabled = enabled_skills()
    assert "ugc_video" not in {s.slug for s in enabled}
    save_user_skill(slug="ugc_video", enabled=True)
    enabled = enabled_skills()
    assert "ugc_video" in {s.slug for s in enabled}


def test_apply_pre_injects_enabled_skills():
    # Disable noisy built-ins, enable prompt_enhancement only
    for s in skills_mod.BUILTIN_SLUGS:
        save_user_skill(slug=s, enabled=False)
    save_user_skill(slug="prompt_enhancement", enabled=True)
    out = apply_pre("hello world", system="be helpful")
    assert "prompt_enhancement" in out
    assert "be helpful" in out
    assert out.endswith("hello world")


def test_apply_pre_no_skills_returns_prompt_unchanged():
    for s in skills_mod.BUILTIN_SLUGS:
        save_user_skill(slug=s, enabled=False)
    assert apply_pre("x", system="y") == "x"


def test_apply_pre_no_system_returns_prompt_unchanged():
    for s in skills_mod.BUILTIN_SLUGS:
        save_user_skill(slug=s, enabled=False)
    save_user_skill(slug="ugc_video", enabled=True)
    # No system prompt → don't inject; the caller should use build_system_prompt
    assert apply_pre("raw user prompt") == "raw user prompt"


def test_build_system_prompt_collects_blocks():
    for s in skills_mod.BUILTIN_SLUGS:
        save_user_skill(slug=s, enabled=False)
    save_user_skill(slug="image_ad", enabled=True)
    sys = build_system_prompt(base="be terse")
    assert "be terse" in sys
    assert "image_ad" in sys


def test_apply_post_strips_filler_words():
    # caption_optimizer ships with post_process_re that strips filler words.
    for s in skills_mod.BUILTIN_SLUGS:
        save_user_skill(slug=s, enabled=False)
    save_user_skill(slug="caption_optimizer", enabled=True)
    out = apply_post("This is just really, very simple.")
    assert " just " not in out
    assert " really" not in out
    assert " very " not in out


def test_apply_post_skips_invalid_regex():
    # Disable built-ins so the bad skill is the only thing that runs.
    for s in skills_mod.BUILTIN_SLUGS:
        save_user_skill(slug=s, enabled=False)
    save_user_skill(
        slug="bad_skill",
        name="Bad",
        enabled=True,
        content_md="irrelevant",
        post_process_re="[unclosed",
    )
    # Should not raise.
    assert apply_post("hello world") == "hello world"


def test_get_sill_returns_none_for_missing():
    assert get_skill("nonexistent-skill") is None


def test_save_and_delete_user_skill():
    save_user_skill(
        slug="my_skill",
        name="My Skill",
        enabled=True,
        content_md="hello",
        tags=["one", "two"],
    )
    skill = get_skill("my_skill")
    assert skill is not None
    assert skill.name == "My Skill"
    assert skill.builtin is False

    assert delete_user_skill("my_skill") is True
    assert get_skill("my_skill") is None


def test_sync_filesystem_to_db(tmp_path):
    user_dir = tmp_path / "skills"
    user_dir.mkdir()
    (user_dir / "external_skill.md").write_text(
        "---\n"
        "name: External Skill\n"
        "enabled: true\n"
        "tags: [test, fixture]\n"
        "---\n\n"
        "external body\n",
        encoding="utf-8",
    )
    summary = skills_mod.sync_filesystem_to_db(user_dir=user_dir)
    assert summary["added"] == 1
    skill = get_skill("external_skill")
    assert skill is not None
    assert skill.content_md == "external body"


def test_write_user_skill_to_disk(tmp_path):
    save_user_skill(
        slug="disk_skill",
        name="Disk Skill",
        enabled=True,
        content_md="hello",
        tags=["a"],
    )
    user_dir = tmp_path / "skills"
    path = skills_mod.write_user_skill_to_disk("disk_skill", user_dir=user_dir)
    assert path is not None
    text = path.read_text()
    assert "Disk Skill" in text
    assert "hello" in text


def test_ensure_builtin_seeded_is_idempotent():
    skills_store.ensure_builtin_seeded()
    skills_store.ensure_builtin_seeded()
    rows = skills_store.user_skills()
    slugs = {r.slug for r in rows}
    for s in skills_mod.BUILTIN_SLUGS:
        assert s in slugs


def test_upsert_builtin_preserves_enabled_flag():
    skills_store.set_enabled("ugc_video", False)
    skills_store.ensure_builtin_seeded()
    rows = {r.slug: r for r in skills_store.user_skills()}
    assert rows["ugc_video"].enabled is False
