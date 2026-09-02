"""app/skills.py. Skill loading + application runtime.

A "skill" is a markdown file with YAML frontmatter that the platform injects
into every LLM prompt (pre) or applies as a deterministic transform after
the LLM returns text (post). Built-in skills ship under :mod:`app.skills.builtins`;
user skills live in ``~/.calypso/skills/*.md`` and are mirrored into the
``user_skills`` DB table by :func:`sync_filesystem_to_db`.

Frontmatter spec (minimal):

    ---
    name: Caption Optimizer
    enabled: true
    post_process_re: '#\w+'    # optional regex applied post-LLM
    ---

    Markdown body that becomes a <skill> block in the system prompt.

The runtime exposes:

- :func:`list_skills` — return all skills (built-in + user)
- :func:`get_skill(slug)` — fetch one by slug
- :func:`apply_pre(prompt, *, system=None)` — prepend enabled skill bodies
- :func:`apply_post(text)` — apply post-process regexes in order
- :func:`save_user_skill(...)` / :func:`delete_user_skill(...)` — write to DB

Built-in slugs (do not change without DB migration):

- ``ugc_video``            — UGC-script patterns for short-form video
- ``image_ad``             — Direct-response ad copy patterns for static posts
- ``prompt_enhancement``   — Generic prompt-quality improvements
- ``caption_optimizer``    — Tightens captions for engagement
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)


# Built-in skill slugs. Keep these in sync with app/skills/builtins/*.md.
BUILTIN_SLUGS: tuple[str, ...] = (
    "ugc_video",
    "image_ad",
    "prompt_enhancement",
    "caption_optimizer",
)

_BUILTINS_DIR = Path(__file__).resolve().parent / "skills" / "builtins"


@dataclass(frozen=True)
class Skill:
    """One loaded skill.

    ``slug`` is the stable identifier (filesystem basename or DB primary
    key). ``builtin`` is True for shipped skills. ``content_md`` is the
    raw markdown body that gets injected into prompts. ``post_process_re``
    is an optional regex applied after the LLM returns.
    """

    slug: str
    name: str
    enabled: bool
    content_md: str
    post_process_re: str | None = None
    builtin: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "enabled": self.enabled,
            "builtin": self.builtin,
            "description": self.description,
            "tags": list(self.tags),
            "post_process_re": self.post_process_re,
        }


# ---- Frontmatter parsing -------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


def _parse_md(text: str) -> tuple[dict[str, str], str]:
    """Parse a markdown file's YAML-ish frontmatter. We don't pull in PyYAML
    for this — the frontmatter is intentionally a tiny subset (name,
    enabled, post_process_re, description, tags)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group("fm").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fm[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
        else:
            fm[key] = value.strip("'\"")
    return fm, m.group("body")


def _coerce_enabled(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _skill_from_md(slug: str, text: str, *, builtin: bool,
                   default_enabled: bool | None = None) -> Skill:
    fm, body = _parse_md(text)
    name = fm.get("name") or slug.replace("_", " ").title()
    enabled_value = fm.get("enabled")
    if enabled_value is None:
        enabled = bool(default_enabled) if default_enabled is not None else True
    else:
        enabled = _coerce_enabled(enabled_value)
    description = fm.get("description", "")
    tags_value = fm.get("tags", [])
    tags = tags_value if isinstance(tags_value, list) else []
    return Skill(
        slug=slug,
        name=str(name),
        enabled=enabled,
        content_md=body.strip(),
        post_process_re=fm.get("post_process_re"),
        builtin=builtin,
        description=str(description) if description else "",
        tags=tags,
    )


# ---- Loading -------------------------------------------------------------


def load_builtin(slug: str) -> Skill | None:
    """Read one built-in markdown file from disk."""
    path = _BUILTINS_DIR / f"{slug}.md"
    if not path.exists():
        return None
    return _skill_from_md(slug, path.read_text(encoding="utf-8"), builtin=True)


def load_all_builtins() -> list[Skill]:
    """Load every built-in skill from :mod:`app.skills.builtins`."""
    out: list[Skill] = []
    for slug in BUILTIN_SLUGS:
        try:
            skill = load_builtin(slug)
        except Exception as exc:  # noqa: BLE001
            log.warning("failed to load builtin skill %s: %s", slug, exc)
            continue
        if skill is not None:
            out.append(skill)
    return out


def list_skills() -> list[Skill]:
    """Return every skill (built-in + user) with DB toggle overrides applied.

    Storage sync is the caller's responsibility: invoke
    :func:`sync_filesystem_to_db` once at startup so DB-side ``enabled``
    flags override the built-in defaults.
    """
    from .skills_store import user_skills  # local import to avoid cycle
    builtins = load_all_builtins()
    user = user_skills()
    by_slug: dict[str, Skill] = {s.slug: s for s in builtins}
    for u in user:
        existing = by_slug.get(u.slug)
        # Override enabled flag from DB; keep built-in body if user didn't
        # provide one.
        content = u.content_md or (existing.content_md if existing else "")
        post_re = u.post_process_re
        if post_re is None and existing is not None:
            post_re = existing.post_process_re
        by_slug[u.slug] = Skill(
            slug=u.slug,
            name=u.name or (existing.name if existing else u.slug),
            enabled=bool(u.enabled),
            content_md=content,
            post_process_re=post_re,
            builtin=bool(existing and existing.builtin),
            description=u.description or (existing.description if existing else ""),
            tags=u.tags or (existing.tags if existing else []),
        )
    return list(by_slug.values())


def get_skill(slug: str) -> Skill | None:
    for s in list_skills():
        if s.slug == slug:
            return s
    return None


def enabled_skills() -> list[Skill]:
    return [s for s in list_skills() if s.enabled]


# ---- Application --------------------------------------------------------


def apply_pre(user_prompt: str, *, system: str | None = None) -> str:
    """Return ``system`` with every enabled skill's body injected as a
    ``<skill>`` block, and the original user prompt untouched.

    If ``system`` is None, the function returns the user prompt unchanged —
    callers that don't already have a system prompt can still call
    :func:`build_system_prompt` first.
    """
    skills = enabled_skills()
    if not skills or system is None:
        return user_prompt
    blocks = []
    for s in skills:
        if not s.content_md:
            continue
        blocks.append(
            f"<skill name={s.name!r} slug={s.slug!r}>\n{s.content_md}\n</skill>"
        )
    if not blocks:
        return user_prompt
    return f"{system}\n\n" + "\n\n".join(blocks) + "\n\n" + user_prompt


def build_system_prompt(base: str = "") -> str:
    """Return just the system prompt with every enabled skill prepended.
    Useful when the caller is feeding an LLM via a structured messages
    list (system + user) rather than a single string."""
    skills = enabled_skills()
    parts = [base] if base else []
    for s in skills:
        if not s.content_md:
            continue
        parts.append(
            f"<skill name={s.name!r} slug={s.slug!r}>\n{s.content_md}\n</skill>"
        )
    return "\n\n".join(p for p in parts if p).strip()


def apply_post(text: str) -> str:
    """Apply every enabled skill's ``post_process_re`` to ``text``.

    Each skill's regex is applied once per skill, in skill order. Unknown
    regexes compile to ``re.error`` which is logged and skipped so one
    malformed skill doesn't break the pipeline.
    """
    out = text
    for s in enabled_skills():
        pat = s.post_process_re
        if not pat:
            continue
        try:
            out = re.sub(pat, "", out)
        except re.error as exc:
            log.warning("skill %s has invalid post_process_re: %s", s.slug, exc)
    return out


# ---- User skill authoring (DB-backed) ----------------------------------


def save_user_skill(*, slug: str, name: str | None = None,
                    enabled: bool = True, content_md: str = "",
                    post_process_re: str | None = None,
                    description: str = "",
                    tags: Iterable[str] | None = None,
                    builtin: bool = False) -> Skill:
    """Persist a user-authored skill. Returns the merged :class:`Skill`."""
    from .skills_store import upsert_user_skill

    upsert_user_skill(
        slug=slug,
        name=name or slug.replace("_", " ").title(),
        enabled=bool(enabled),
        content_md=content_md,
        post_process_re=post_process_re,
        description=description,
        tags=list(tags or []),
    )
    if builtin:
        log.info("upserted builtin override for %s", slug)
    skill = get_skill(slug)
    if skill is None:
        # New user skill that shadows nothing — return a fresh Skill.
        return Skill(
            slug=slug,
            name=name or slug.replace("_", " ").title(),
            enabled=bool(enabled),
            content_md=content_md,
            post_process_re=post_process_re,
            builtin=False,
            description=description,
            tags=list(tags or []),
        )
    return skill


def delete_user_skill(slug: str) -> bool:
    """Remove a user-authored skill. Built-ins cannot be deleted (only
    toggled off). Returns True if a row was removed."""
    from .skills_store import delete_user_skill as _delete
    return _delete(slug)


# ---- Filesystem sync ----------------------------------------------------


def sync_filesystem_to_db(user_dir: Path | None = None) -> dict[str, int]:
    """Mirror ``<user_dir>/*.md`` into the user_skills table.

    - Files on disk → upserted into DB (preserving the user's ``enabled`` if
      a row already exists; otherwise defaulting to True).
    - DB rows with no matching file are left in place (the UI can delete
      them explicitly).

    Returns ``{"added": N, "updated": M}`` for logging.
    """
    from .skills_store import upsert_user_skill_from_file

    user_dir = user_dir or (Path.home() / ".calypso" / "skills")
    added = updated = 0
    if not user_dir.exists():
        return {"added": 0, "updated": 0}
    for path in sorted(user_dir.glob("*.md")):
        slug = path.stem
        result = upsert_user_skill_from_file(slug, path)
        if result == "added":
            added += 1
        elif result == "updated":
            updated += 1
    if added or updated:
        log.info("skill sync: %d added, %d updated", added, updated)
    return {"added": added, "updated": updated}


def write_user_skill_to_disk(slug: str, user_dir: Path | None = None) -> Path | None:
    """Mirror a DB row back to disk so external editors can edit it.

    Returns the file path or None if no DB row exists."""
    from .skills_store import get_user_skill

    user_dir = user_dir or (Path.home() / ".calypso" / "skills")
    row = get_user_skill(slug)
    if row is None:
        return None
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{slug}.md"
    tags = ",".join(f'"{t}"' for t in (row.tags or []))
    lines = [
        "---",
        f"name: {row.name}",
        f"enabled: {'true' if row.enabled else 'false'}",
        f"description: {row.description or ''}",
        f"tags: [{tags}]" if tags else "tags: []",
    ]
    if row.post_process_re:
        lines.append(f"post_process_re: {row.post_process_re}")
    lines.append("---")
    lines.append("")
    lines.append(row.content_md or "")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
