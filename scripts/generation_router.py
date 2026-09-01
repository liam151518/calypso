"""Generation router. Picks the right video backend per request.

Given a video request spec (duration, resolution, tier), the router decides:
- MiniMax H3 cloud (primary, best quality, native audio, matches reference-driven philosophy)
- MiniMax H3 Max via fal.ai (speed tier, high-volume dailies)
- fal.ai Kling 2.6 Pro (hero tier, 1/week)
- LTX 2.0 via fal.ai (fallback when at cost cap)

Cost cap: monthly hard cap, default $30. Fallback to cheapest tier at 80% of cap.
Pause at 95%.

State: the router tracks cumulative spend in a JSON file at agent-control/spend.json.

Tests: tests/test_generation_router.py
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEND_FILE = REPO_ROOT / "agent-control" / "spend.json"

Tier = Literal["primary", "speed", "hero", "fallback", "paused"]


@dataclass(frozen=True)
class RoutingDecision:
    """The router's pick for a request."""

    backend: Literal["h3_cloud", "h3_max_falai", "kling_falai", "ltx_falai", "pause"]
    tier: Tier
    estimated_cost_usd: float
    reason: str


@dataclass
class SpendState:
    """Cumulative spend for the current month."""

    month: str  # YYYY-MM
    spend_usd: float = 0.0
    requests: int = 0
    cap_usd: float = 30.0  # default; can be overridden via env

    @classmethod
    def load(cls, path: Path | None = None) -> "SpendState":
        """Load spend state, resetting on month change."""
        if path is None:
            path = SPEND_FILE
        if not path.exists():
            return cls(month=_current_month())
        data = json.loads(path.read_text())
        loaded = cls(
            month=data.get("month", _current_month()),
            spend_usd=float(data.get("spend_usd", 0.0)),
            requests=int(data.get("requests", 0)),
            cap_usd=float(data.get("cap_usd", os.environ.get("MONTHLY_COST_CAP_USD", 30))),
        )
        # Reset if we've crossed a month boundary
        if loaded.month != _current_month():
            return cls(month=_current_month(), cap_usd=loaded.cap_usd)
        return loaded

    def save(self, path: Path | None = None) -> None:
        if path is None:
            path = SPEND_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "month": self.month,
            "spend_usd": self.spend_usd,
            "requests": self.requests,
            "cap_usd": self.cap_usd,
        }, indent=2))

    def projected_pct(self) -> float:
        """What % of the cap we'd hit at current spend rate (projected linearly through month-end)."""
        return (self.spend_usd / self.cap_usd) * 100 if self.cap_usd else 0.0


def _current_month() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m")


class GenerationRouter:
    """Picks the right video backend per request spec."""

    def __init__(self, spend_state: SpendState | None = None) -> None:
        self.spend = spend_state or SpendState.load()
        self._lock = threading.Lock()

    # ---------- routing logic ----------

    def route(
        self,
        *,
        duration_seconds: int = 8,
        resolution: str = "768p",
        tier_preference: Tier | None = None,
        is_hero: bool = False,
    ) -> RoutingDecision:
        """Decide which backend to use for this request.

        Logic:
        1. If projected spend > 95% of cap: PAUSE
        2. If is_hero and projected spend < 80%: kling_falai (hero)
        3. If projected spend > 80%: ltx_falai (fallback, cheapest)
        4. If tier_preference == "speed": h3_max_falai
        5. Default: h3_cloud (primary)
        """
        with self._lock:
            pct = self.spend.projected_pct()
            cost_estimate = self._estimate_cost("h3_cloud", duration_seconds, resolution)

            # Hard stop at 95%
            if pct >= 95:
                return RoutingDecision(
                    backend="pause",
                    tier="paused",
                    estimated_cost_usd=cost_estimate,
                    reason=f"spend at {pct:.0f}% of monthly cap; pausing until next month",
                )

            # Hero tier (only when explicitly requested AND budget allows)
            if is_hero and pct < 80:
                return RoutingDecision(
                    backend="kling_falai",
                    tier="hero",
                    estimated_cost_usd=self._estimate_cost("kling_falai", duration_seconds, resolution),
                    reason="hero tier requested",
                )

            # Cost cap fallback
            if pct >= 80:
                return RoutingDecision(
                    backend="ltx_falai",
                    tier="fallback",
                    estimated_cost_usd=self._estimate_cost("ltx_falai", duration_seconds, resolution),
                    reason=f"spend at {pct:.0f}% of cap; using cheapest fallback",
                )

            # Speed tier (only when explicitly requested)
            if tier_preference == "speed":
                return RoutingDecision(
                    backend="h3_max_falai",
                    tier="speed",
                    estimated_cost_usd=self._estimate_cost("h3_max_falai", duration_seconds, resolution),
                    reason="speed tier requested",
                )

            # Default: primary H3 cloud
            return RoutingDecision(
                backend="h3_cloud",
                tier="primary",
                estimated_cost_usd=cost_estimate,
                reason="default to primary H3 cloud",
            )

    # ---------- spend tracking ----------

    def record_spend(self, decision: RoutingDecision) -> None:
        """Record actual spend after a generation completes. Persists to disk."""
        if decision.backend == "pause":
            return
        with self._lock:
            self.spend.spend_usd += decision.estimated_cost_usd
            self.spend.requests += 1
            self.spend.save()

    # ---------- helpers ----------

    @staticmethod
    def _estimate_cost(backend: str, duration: int, resolution: str) -> float:
        """Rough cost estimate per backend/resolution/duration."""
        rates: dict[str, dict[str, float]] = {
            "h3_cloud": {"480p": 0.04, "768p": 0.07, "1080p": 0.10, "2k": 0.14},
            "h3_max_falai": {"480p": 0.03, "768p": 0.05, "1080p": 0.08},
            "kling_falai": {"480p": 0.05, "768p": 0.07, "1080p": 0.10},
            "ltx_falai": {"480p": 0.02, "768p": 0.04, "1080p": 0.06},
            "pause": {"480p": 0, "768p": 0, "1080p": 0, "2k": 0},
        }
        rate = rates.get(backend, {}).get(resolution, 0.07)
        return rate * duration


# ---------- CLI ----------

def _cli() -> int:
    parser = argparse.ArgumentParser(description="Show current generation routing decision.")
    parser.add_argument("--duration", type=int, default=8, help="Duration in seconds")
    parser.add_argument("--resolution", default="768p", choices=["480p", "768p", "1080p", "2k"])
    parser.add_argument("--tier", choices=["primary", "speed", "hero"], help="Tier preference")
    parser.add_argument("--hero", action="store_true", help="Treat as hero post")
    parser.add_argument("--record", help="Record actual spend for a completed backend call")
    args = parser.parse_args()

    router = GenerationRouter()
    decision = router.route(
        duration_seconds=args.duration,
        resolution=args.resolution,
        tier_preference=args.tier,
        is_hero=args.hero,
    )
    print(json.dumps({
        "backend": decision.backend,
        "tier": decision.tier,
        "estimated_cost_usd": round(decision.estimated_cost_usd, 4),
        "reason": decision.reason,
        "current_month_spend_usd": round(router.spend.spend_usd, 2),
        "cap_pct": round(router.spend.projected_pct(), 1),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
