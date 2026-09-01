# agent-control/. Durable orchestrator state

Adam uses this folder for **current-state** info that needs to survive between Cursor sessions. It's the analog of a run ledger.

Per Adam's design:

> `agent-control/` is durable orchestrator state in target projects.
> What's in flight, what landed, what the next session should do.

## What's typically here

```
agent-control/
├── README.md                       # this file
├── current-state.md                # what's running right now (pipeline status)
├── in-flight.md                    # slices currently being built by sub-agents
├── pending-approvals.md            # Telegram approvals waiting on you
├── run-ledger.md                   # append-only log of orchestration runs
└── next-session-brief.md           # what the next Cursor session should do first
```

## What goes where

| Type of info | Goes in |
|---|---|
| Stable facts about you and the project | `adam/context/*.md` |
| Stable product definition | `packet/*.md` |
| Architecture decisions, ADRs | `plan/adr/` |
| Phase plans | `plan/*.md` |
| Slice definitions | `slices/00X-*/brief.md` |
| **What slice is being built right now** | **`agent-control/in-flight.md`** |
| **What approvals are waiting on you** | **`agent-control/pending-approvals.md`** |
| **What's the next session's first action** | **`agent-control/next-session-brief.md`** |

## Status

Empty. Adam populates this as the pipeline runs.

## When `verify.sh` checks here

`verify.sh` doesn't currently validate agent-control contents. They're Adam's freeform notes. Adam uses them at session start to resume work.
