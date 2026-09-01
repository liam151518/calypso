"""app/extensions/manifest.py. Extension manifest data model + validation.

Every Calypso extension ships a `calypso-extension.json` (or `.yaml`)
manifest. This module parses it, validates the schema, and exposes a
typed `ExtensionManifest` for the rest of the loader to consume.

The schema is intentionally tiny so community authors can grok it in
five minutes. Anything richer belongs in the extension code, not the
manifest.

Layout on disk:
    <CALYPSO_EXTENSIONS_DIR>/<extension-id>/
        calypso-extension.json
        extension.py          (optional: provides Provider/Stage/Node/etc.)
        static/               (optional: icons, default form schemas, etc.)

Extension types:
    provider   : adds models to app.models (replaces or augments TOP_MODELS)
    stage      : adds an agent to app.agents
    node       : adds a pipeline node type to app.pipeline_nodes
    channel    : sends messages (email, sms, slack, ...)
    form       : webhook source for Phase F landing pages
    import_    : bulk-imports data (CSV contacts, ZIP references, ...)
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ExtensionType = Literal[
    "provider",
    "stage",
    "node",
    "channel",
    "form",
    "import_",
]

ALLOWED_TYPES: tuple[str, ...] = (
    "provider",
    "stage",
    "node",
    "channel",
    "form",
    "import_",
)


@dataclass
class ExtensionManifest:
    id: str
    version: str
    type: str
    name: str
    author: str = ""
    description: str = ""
    homepage: str = ""
    license: str = "MIT"
    checksum: str = ""
    signature: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None


class ManifestError(ValueError):
    """Raised when a manifest fails validation."""


REQUIRED_FIELDS = ("id", "version", "type", "name")


def parse_manifest(path: Path) -> ExtensionManifest:
    """Parse `calypso-extension.json` into an ExtensionManifest."""
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError("manifest must be a JSON object")
    for field_name in REQUIRED_FIELDS:
        if not raw.get(field_name):
            raise ManifestError(f"manifest missing required field: {field_name}")
    etype = str(raw["type"])
    if etype not in ALLOWED_TYPES:
        raise ManifestError(f"unknown extension type: {etype!r}")
    ext_id = str(raw["id"])
    if "/" in ext_id or ext_id.startswith("."):
        raise ManifestError(
            f"invalid extension id {ext_id!r}: must be a simple slug"
        )
    return ExtensionManifest(
        id=ext_id,
        version=str(raw["version"]),
        type=etype,
        name=str(raw["name"]),
        author=str(raw.get("author", "")),
        description=str(raw.get("description", "")),
        homepage=str(raw.get("homepage", "")),
        license=str(raw.get("license", "MIT")),
        checksum=str(raw.get("checksum", "")),
        signature=str(raw.get("signature", "")),
        extra={k: v for k, v in raw.items()
               if k not in {"id", "version", "type", "name", "author",
                            "description", "homepage", "license",
                            "checksum", "signature"}},
        path=path.parent,
    )


def compute_checksum(ext_dir: Path) -> str:
    """Stable SHA-256 over every file under `ext_dir` (manifest excluded
    from the digest because it carries the digest itself)."""
    h = hashlib.sha256()
    for f in sorted(ext_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.name == "calypso-extension.json":
            continue
        rel = f.relative_to(ext_dir).as_posix().encode()
        h.update(rel + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def sign_manifest(manifest: ExtensionManifest, secret: str) -> str:
    """Generate an HMAC-SHA-256 signature over the canonical fields."""
    payload = json.dumps(
        {
            "id": manifest.id,
            "version": manifest.version,
            "type": manifest.type,
            "checksum": manifest.checksum,
        },
        sort_keys=True,
    ).encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_signature(manifest: ExtensionManifest, secret: str) -> bool:
    if not manifest.signature:
        return False
    expected = sign_manifest(manifest, secret)
    return hmac.compare_digest(expected, manifest.signature)
