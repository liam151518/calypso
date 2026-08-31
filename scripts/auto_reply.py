"""Auto-reply classifier — routes incoming DMs/comments to the right handler.

Per Phase 5.2: the Social Stats unified inbox collects DMs and comments.
This classifier decides what to do with each one:

- gacha_pull_question → answer with a reference to the relevant site feature
- support_request → forward to operator on Telegram
- spam → archive (don't reply)
- payment_related → forward to operator (NEVER auto-reply)
- other → forward to operator

Tests: tests/test_auto_reply.py
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Intent(str, Enum):
    GACHA_PULL_QUESTION = "gacha_pull_question"
    SUPPORT_REQUEST = "support_request"
    SPAM = "spam"
    PAYMENT_RELATED = "payment_related"
    OTHER = "other"


@dataclass(frozen=True)
class Classification:
    """The result of classifying a message."""

    intent: Intent
    confidence: float  # 0.0 to 1.0
    reason: str
    suggested_action: str  # auto_reply | forward_to_operator | archive


# ---------- keyword lists ----------

GACHA_KEYWORDS = [
    "pull", "spin", "open", "capsule", "cabinet", "tier list", "damascus",
    "which one", "should I", "what's in", "best figure", "rare drop",
    "machine", "rosebank", "binder", "collection",
]

SUPPORT_KEYWORDS = [
    "broken", "doesn't work", "didn't arrive", "missing", "wrong item",
    "where's my", "customer service", "refund", "return", "damaged",
    "help me", "support",
]

SPAM_KEYWORDS = [
    "crypto", "investment opportunity", "click here", "make money fast",
    "follow me back", "sub4sub", "f4f", "free iphone", "lottery winner",
]

PAYMENT_KEYWORDS = [
    "refund", "chargeback", "billing", "invoice", "payment", "credit card",
    "debit", "transaction", "money back", "double charge",
]


def classify(message: str) -> Classification:
    """Classify an incoming message into an intent."""
    text = message.lower()

    # Payment-related FIRST (always forward, never auto-reply)
    for kw in PAYMENT_KEYWORDS:
        if kw in text:
            return Classification(
                intent=Intent.PAYMENT_RELATED,
                confidence=0.95,
                reason=f"matched payment keyword: {kw!r}",
                suggested_action="forward_to_operator",
            )

    # Spam
    for kw in SPAM_KEYWORDS:
        if kw in text:
            return Classification(
                intent=Intent.SPAM,
                confidence=0.95,
                reason=f"matched spam keyword: {kw!r}",
                suggested_action="archive",
            )

    # Support requests
    for kw in SUPPORT_KEYWORDS:
        if kw in text:
            return Classification(
                intent=Intent.SUPPORT_REQUEST,
                confidence=0.85,
                reason=f"matched support keyword: {kw!r}",
                suggested_action="forward_to_operator",
            )

    # Gacha pull questions
    gacha_hits = sum(1 for kw in GACHA_KEYWORDS if kw in text)
    if gacha_hits >= 1:
        return Classification(
            intent=Intent.GACHA_PULL_QUESTION,
            confidence=min(0.5 + gacha_hits * 0.1, 0.95),
            reason=f"matched {gacha_hits} gacha keyword(s)",
            suggested_action="auto_reply",
        )

    # Default: forward to operator
    return Classification(
        intent=Intent.OTHER,
        confidence=0.5,
        reason="no clear keyword match",
        suggested_action="forward_to_operator",
    )


def generate_reply(message: str, brand_voice_terms: list[str] | None = None) -> str:
    """Generate a brand-voice-conditioned reply to a gacha-pull question.

    Uses simple templating — in production this would call the LLM with the
    brand voice from brand/voice.md as system prompt.
    """
    cls = classify(message)
    if cls.intent != Intent.GACHA_PULL_QUESTION:
        return ""  # No auto-reply for non-gacha

    text = message.lower()
    reply_templates = []

    if "tier list" in text or "best figure" in text:
        reply_templates.append("full tier list is up at gachakingdoms.com — S-tier is fewer figures than you'd expect")

    if "damascus" in text:
        reply_templates.append("the Damascus set is honestly the move right now. Damascus pink cabinet at Rosebank tends to have the best pulls.")

    if "rosebank" in text or "machine" in text or "cabinet" in text:
        reply_templates.append("Rosebank machine map is on the site. free spin if you scan the QR check-in.")

    if not reply_templates:
        reply_templates.append("spin on the site, pull list is up to date. drop a Tier list link if you want to know what's hot.")

    # Add brand-voice flavor if provided
    reply = " ".join(reply_templates)
    if brand_voice_terms:
        # Insert one brand-voice term somewhere natural
        reply += " — " + brand_voice_terms[0]

    return reply


# ---------- CLI ----------

def _cli() -> int:
    parser = argparse.ArgumentParser(description="Classify an incoming message.")
    parser.add_argument("message", help="The message text to classify")
    parser.add_argument("--reply", action="store_true", help="Also generate a reply (only for gacha intents)")
    args = parser.parse_args()

    cls = classify(args.message)
    output = {
        "intent": cls.intent.value,
        "confidence": cls.confidence,
        "reason": cls.reason,
        "suggested_action": cls.suggested_action,
    }
    if args.reply:
        output["reply"] = generate_reply(args.message)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
