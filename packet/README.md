# packet/ — The product brief

This folder holds the **stable product brief** that defines what we're building. Adam reads it at the start of every meaningful planning conversation.

Per the Adam rules:
- **You own this folder.** Operators write to it; Adam reads from it.
- **Sub-agents (builders, researchers) cannot edit it.** If a builder finds something in `packet/` that's wrong, it files an issue rather than editing.

The initial brief is created during Phase 0's `calibrate` interview and Phase 1's `intake` skill. Adam drafts it; you approve each section.

## What's in here

When fully populated, expect:

```
packet/
├── README.md                    # this file
├── product-brief.md             # what Gatcha Kingdom is, who's it for, what we're building
├── success-metrics.md           # how we measure if the pipeline is working
├── constraints.md               # budget caps, license posture, banned-content rules
└── stakeholders.md              # who cares about what (you, future hires, legal)
```

These documents are intentionally **durable** — they change slowly. Day-to-day changes go in `agent-control/` (current state) or `adam/memory/decisions/` (ADRs).

## Status

Empty placeholder. Phase 0 (`docs/PHASE_0.md`) walks through Adam's `calibrate` and `intake` skills that fill this in.
