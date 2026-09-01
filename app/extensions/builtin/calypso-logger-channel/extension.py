"""calypso-logger-channel extension. Registers a `logger` channel."""

from __future__ import annotations

import json


def register(hooks) -> None:
    def send(payload: dict) -> dict:
        # Pretty-print for terminal debugging; never block, never fail.
        print("[logger-channel]", json.dumps(payload, default=str))
        return {"ok": True, "channel": "logger"}

    hooks("channel.logger").append(send)
