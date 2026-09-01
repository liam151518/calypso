"""app/extensions/hooks.py. Typed hook names + helpers.

Centralised so the rest of the codebase has one canonical list of hook
names an extension can subscribe to.
"""

from __future__ import annotations

from typing import Any, Iterable

from .loader import iterate_hooks, registry


# ---- hook names ---------------------------------------------------------

# Phase D: provider. Extend the model registry.
HOOK_PROVIDER_MODELS = "provider.models"
# Phase D: stage. Add an agent.
HOOK_STAGE_REGISTER = "stage.register"
# Phase D: node. Add a pipeline node type.
HOOK_NODE_REGISTER = "node.register"
# Phase F.5: channel. Send a message somewhere.
HOOK_CHANNEL_SEND = "channel.send"
# Phase F.4: form. Capture a landing-page form submission.
HOOK_FORM_CAPTURE = "form.capture"
# Phase D: import. Bulk-import data.
HOOK_IMPORT_RUN = "import.run"


# ---- helpers ------------------------------------------------------------


def call_channel(channel_type: str, payload: dict[str, Any]) -> list[Any]:
    """Fan-out: call every registered `channel.<channel_type>` handler."""
    out: list[Any] = []
    for hook in iterate_hooks(f"channel.{channel_type}"):
        try:
            out.append(hook(payload))
        except Exception:  # noqa: BLE001
            out.append({"ok": False, "error": "channel handler raised"})
    return out


def call_form_capture(form_id: str, submission: dict[str, Any]) -> dict[str, Any]:
    """Run every registered form-capture handler until one succeeds."""
    for hook in iterate_hooks(HOOK_FORM_CAPTURE):
        try:
            result = hook(form_id, submission)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        if result and result.get("ok"):
            return result
    return {"ok": False, "error": "no handler accepted the submission"}


def call_import(kind: str, source: Path, opts: dict[str, Any]) -> dict[str, Any]:
    """Run every registered import handler for `kind`. Returns the first
    successful result."""
    for hook in iterate_hooks(f"import.{kind}"):
        try:
            res = hook(source, opts)
            if res and res.get("ok"):
                return res
        except Exception:  # noqa: BLE001
            continue
    return {"ok": False, "error": f"no importer for kind={kind!r}"}


__all__ = [
    "HOOK_PROVIDER_MODELS",
    "HOOK_STAGE_REGISTER",
    "HOOK_NODE_REGISTER",
    "HOOK_CHANNEL_SEND",
    "HOOK_FORM_CAPTURE",
    "HOOK_IMPORT_RUN",
    "call_channel",
    "call_form_capture",
    "call_import",
    "registry",
]
