"""app/agents/base.py. Common scaffolding for every Phase C agent.

Each agent:
    - has a `name` (used by the orchestrator for log lines and routing),
    - declares the `inputs` it needs (e.g. "treatment", "references"),
    - declares the `outputs` it produces (e.g. "scenes", "shot_list"),
    - implements `run(ctx) -> dict` synchronously.

The orchestrator (`app/agents/director.py`, `app/agents/producer.py`)
chains agents by mapping outputs → inputs. Each step writes a structured
artifact that the SPA renders and the user can edit before moving on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Shared mutable state passed between agents in a single Studio run.

    `brief` is the high-level idea the user typed; `brand` and
    `references` are pre-loaded. Each agent stores its outputs as
    top-level keys on this dict so the next agent can pick them up.
    """

    brief: str
    brand: dict[str, Any] = field(default_factory=dict)
    references: list[dict] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)
    spent_usd: float = 0.0

    def record(self, agent: str, msg: str) -> None:
        """Append a log entry. Surfaced live in the Studio UI."""
        self.log.append({"agent": agent, "msg": msg})


@dataclass
class AgentResult:
    """What an agent returns. Always wrap output dict, plus optional
    status / partial-flag."""

    outputs: dict[str, Any]
    status: str = "ok"
    note: str = ""


class Agent:
    """Base class. Subclasses override `name`, `inputs`, `outputs`, `run`."""

    name: str = "agent"
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    description: str = ""

    def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def _require(self, ctx: AgentContext, *keys: str) -> None:
        """Assert that upstream inputs are present. Raise a clear error
        if the orchestrator wired things wrong."""
        missing = [k for k in keys if k not in ctx.artifacts]
        if missing:
            raise RuntimeError(
                f"{self.name} needs inputs {missing} but they were not produced upstream"
            )
