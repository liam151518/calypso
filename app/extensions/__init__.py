"""app/extensions. Phase D plugin marketplace.

Public surface:
    discover(source=None)         : walk a directory for extension manifests
    enable(id, secret=None) / disable(id)
    is_enabled(id)
    list_extensions()             : JSON for the SPA marketplace page
    load_builtin_extensions()    : auto-discover + enable shipped extensions

Manifest format: see `app/extensions/manifest.py`. Hook names: see
`app/extensions/hooks.py`. CLI for signing: see `app/extensions/signing.py`.

Built-in extensions live under `app/extensions/builtin/` and are
auto-loaded at app startup. Community extensions are installed under
`$CALYPSO_EXTENSIONS_DIR/<id>/` (default `~/.calypso/extensions/<id>/`).
"""

from __future__ import annotations

from .hooks import (
    HOOK_CHANNEL_SEND,
    HOOK_FORM_CAPTURE,
    HOOK_IMPORT_RUN,
    HOOK_NODE_REGISTER,
    HOOK_PROVIDER_MODELS,
    HOOK_STAGE_REGISTER,
    call_channel,
    call_form_capture,
    call_import,
    registry,
)
from .loader import (
    BUILTIN_DIR,
    DEFAULT_EXT_DIR,
    disable,
    discover,
    enable,
    is_enabled,
    list_extensions,
    load_builtin_extensions,
    reset_for_tests,
    restore_state,
)
from .manifest import (
    ExtensionManifest,
    ManifestError,
    compute_checksum,
    parse_manifest,
    sign_manifest,
    verify_signature,
)

__all__ = [
    "BUILTIN_DIR",
    "DEFAULT_EXT_DIR",
    "ExtensionManifest",
    "HOOK_CHANNEL_SEND",
    "HOOK_FORM_CAPTURE",
    "HOOK_IMPORT_RUN",
    "HOOK_NODE_REGISTER",
    "HOOK_PROVIDER_MODELS",
    "HOOK_STAGE_REGISTER",
    "ManifestError",
    "call_channel",
    "call_form_capture",
    "call_import",
    "compute_checksum",
    "disable",
    "discover",
    "enable",
    "is_enabled",
    "list_extensions",
    "load_builtin_extensions",
    "parse_manifest",
    "registry",
    "reset_for_tests",
    "restore_state",
    "sign_manifest",
    "verify_signature",
]
