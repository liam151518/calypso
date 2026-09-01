"""app/agents. Phase C Multi-agent Studio.

Public surface:
    AGENTS                 : ordered list of every agent (used by `run_studio`)
    run_studio(brief) -> dict : execute the full chain end-to-end

Each agent is a small, offline, deterministic unit. Together they take a
single-line brief and emit a runnable Pipeline (Phase A). The SPA renders
each artifact card live so the user can intervene between agents.

Adding a new agent:
    1. Subclass `app.agents.base.Agent`.
    2. Append the class to `AGENTS` in the order it should run.
    3. If it produces a new artifact, also wire it into `Producer.inputs`.

Phase D plugins can register additional agents via `register_agent()`.
"""

from __future__ import annotations

from typing import Any, Callable

from .asset_forge import AssetForge
from .base import Agent, AgentContext, AgentResult
from .director import Director
from .producer import Producer
from .qc import QC
from .reference_selector import ReferenceSelector
from .screenwriter import Screenwriter
from .storyboard import Storyboard

# Ordered chain. Each `inputs` field must be satisfied by the upstream
# `outputs` set. `orchestrator` validates this on every run.
AGENTS: list[Agent] = [
    Director(),
    Screenwriter(),
    ReferenceSelector(),
    Storyboard(),
    AssetForge(),
    Producer(),
    QC(),
]

# Optional extension hook. Phase D plugins can call this to register
# extra agents (e.g. "Hook Writer", "Legal Review"). They will be appended
# in registration order, AFTER Producer + QC, so they see the final
# pipeline. They cannot mutate the pipeline.
_PLUGIN_AGENTS: list[Agent] = []


def register_agent(agent: Agent) -> None:
    """Append a plugin-supplied agent to the chain (Phase D)."""
    if any(a.name == agent.name for a in AGENTS + _PLUGIN_AGENTS):
        raise ValueError(f"agent name already registered: {agent.name}")
    _PLUGIN_AGENTS.append(agent)


def all_agents() -> list[Agent]:
    return list(AGENTS) + list(_PLUGIN_AGENTS)


# ---------- orchestrator ----------


class StudioError(RuntimeError):
    """Raised on wiring or runtime failures in the studio chain."""


def run_studio(
    brief: str,
    *,
    brand: dict[str, Any] | None = None,
    references: list[dict] | None = None,
) -> dict[str, Any]:
    """Run the full agent chain synchronously and return every artifact."""
    ctx = AgentContext(
        brief=(brief or "").strip(),
        brand=brand or {},
        references=list(references or []),
    )
    if not ctx.brief:
        raise StudioError("brief is required")
    _validate_wiring()
    for agent in all_agents():
        ctx.record(agent.name, "start")
        try:
            result = agent.run(ctx)
            ctx.artifacts.update(result.outputs)
            ctx.record(agent.name, f"ok -> {sorted(result.outputs.keys())}")
        except Exception as exc:  # noqa: BLE001
            ctx.record(agent.name, f"FAILED: {exc}")
            raise StudioError(f"{agent.name} failed: {exc}") from exc
    return {
        "brief": ctx.brief,
        "log": ctx.log,
        "artifacts": ctx.artifacts,
        "spent_usd": ctx.spent_usd,
    }


def _validate_wiring() -> None:
    """Every agent's `inputs` must be produced by some upstream agent."""
    produced: set[str] = set()
    for agent in all_agents():
        for key in agent.inputs:
            if key not in produced:
                raise StudioError(
                    f"agent {agent.name!r} requires input {key!r} "
                    f"but no upstream agent produces it"
                )
        produced.update(agent.outputs)


__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "AGENTS",
    "all_agents",
    "register_agent",
    "run_studio",
    "StudioError",
]
