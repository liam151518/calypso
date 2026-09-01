"""app.motion.prompts. Phase E.4 — Omni prompt templates per kind.

Exactly the spec §6.3 `OMNI_PROMPTS` dict, parameterized at call time so
operators can override copy without editing Python.
"""

from __future__ import annotations


OMNI_PROMPTS: dict[str, str] = {
    "text_bounce_in": (
        "{text} bounces into frame with elastic easeOutBack; scale 0 → 1; "
        "centered on a transparent background."
    ),
    "lower_third_slide": (
        "Lower-third title '{text}' slides in from the bottom edge of the "
        "frame with a subtle motion blur; a thin accent line appears behind it."
    ),
    "sticker_pop": (
        "{text} pops onto the frame like a sticker — overshoot bounce; "
        "white outline + drop shadow; transparent background."
    ),
    "transition_wipe": (
        "A clean {color} wipe slides across the frame from left to right, "
        "revealing the next scene underneath."
    ),
    "countdown_pulse": (
        "Large numeric countdown '{text}' pulses in the center of the frame; "
        "each tick grows then settles; saturated accent color."
    ),
    "fade": (
        "{text} fades in from transparent; no motion; subtle ease-in-out."
    ),
    "slide_up": (
        "{text} slides upward into its final position; linear easing; "
        "no overshoot."
    ),
    "pulse": (
        "{text} pulses gently in place; scale oscillates +/- 10%; "
        "no movement."
    ),
}


def render_prompt(kind: str, **params: object) -> str:
    """Render an Omni prompt for the given kind, substituting params."""
    template = OMNI_PROMPTS.get(kind)
    if template is None:
        raise ValueError(f"no Omni prompt for motion kind: {kind!r}")
    safe = {k: ("" if v is None else v) for k, v in params.items()}
    return template.format(**safe)


__all__ = ["OMNI_PROMPTS", "render_prompt"]