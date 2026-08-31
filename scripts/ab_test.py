"""A/B test runner for the ad pipeline.

Three A/B tests from the Phase 4 plan:
- A/B 1: post-processed vs raw
- A/B 2: UGC voiceover vs H3 native audio
- A/B 3: 5s vs 8s vs 10s clips

Each post gets assigned to one variant per active test (deterministically by
post_id hash, so the same post always gets the same variant — prevents
mid-experiment confusion).

State lives in agent-control/ab-tests.json.

Tests: tests/test_ab_test.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / "agent-control" / "ab-tests.json"

TestName = Literal["post_process", "audio", "duration"]


@dataclass(frozen=True)
class Assignment:
    """Which variant of which test a given post_id is assigned to."""

    test: TestName
    post_id: str
    variant: str
    bucket: int  # 0..99, the random bucket used


# ---------- variant definitions ----------

POST_PROCESS_VARIANTS = ["post_processed", "raw"]
AUDIO_VARIANTS = ["h3_native", "ugc_elevenlabs"]
DURATION_VARIANTS = ["5s", "8s", "10s"]


def _bucket_for(post_id: str, test: TestName) -> int:
    """Deterministic 0-99 bucket for a post_id + test."""
    h = hashlib.sha256(f"{test}:{post_id}".encode()).hexdigest()
    return int(h[:8], 16) % 100


def assign(test: TestName, post_id: str) -> Assignment:
    """Assign a post_id to a variant of the given test."""
    bucket = _bucket_for(post_id, test)
    if test == "post_process":
        variant = POST_PROCESS_VARIANTS[bucket % len(POST_PROCESS_VARIANTS)]
    elif test == "audio":
        variant = AUDIO_VARIANTS[bucket % len(AUDIO_VARIANTS)]
    elif test == "duration":
        variant = DURATION_VARIANTS[bucket % len(DURATION_VARIANTS)]
    else:
        raise ValueError(f"unknown test: {test}")
    return Assignment(test=test, post_id=post_id, variant=variant, bucket=bucket)


def is_test_active(test: TestName, state_path: Path | None = None) -> bool:
    """Is the given test currently active?"""
    if state_path is None:
        state_path = STATE_FILE
    if not state_path.exists():
        return False
    state = json.loads(state_path.read_text())
    return state.get(test, {}).get("active", False)


def activate_test(test: TestName, state_path: Path | None = None) -> None:
    """Turn on a test."""
    if state_path is None:
        state_path = STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    state.setdefault(test, {})["active"] = True
    state[test]["activated_at"] = __import__("time").time()
    state_path.write_text(json.dumps(state, indent=2))


def deactivate_test(test: TestName, state_path: Path | None = None) -> None:
    """Turn off a test."""
    if state_path is None:
        state_path = STATE_FILE
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text())
    state.setdefault(test, {})["active"] = False
    state_path.write_text(json.dumps(state, indent=2))


# ---------- CLI ----------

def _cli() -> int:
    parser = argparse.ArgumentParser(description="A/B test assignment tool.")
    parser.add_argument("--test", choices=["post_process", "audio", "duration"], required=True)
    parser.add_argument("--post-id", required=True, help="Unique post identifier")
    parser.add_argument("--activate", action="store_true", help="Activate this test")
    parser.add_argument("--deactivate", action="store_true", help="Deactivate this test")
    args = parser.parse_args()

    if args.activate:
        activate_test(args.test)
        print(f"activated: {args.test}")
        return 0
    if args.deactivate:
        deactivate_test(args.test)
        print(f"deactivated: {args.test}")
        return 0

    if not is_test_active(args.test, state_path=STATE_FILE):
        print(f"test '{args.test}' is not active — variants will not be applied")
        return 0

    assignment = assign(args.test, args.post_id)
    print(json.dumps({
        "test": assignment.test,
        "post_id": assignment.post_id,
        "variant": assignment.variant,
        "bucket": assignment.bucket,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
