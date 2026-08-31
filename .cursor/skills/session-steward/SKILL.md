---
name: session-steward
description: At ~50-60% token usage, archive current session state for a clean handoff.
---

# Session-steward

**When to use:** When the chat context is getting long; before closing the laptop.

**Inputs:** current session state
**Outputs:** entry in `agent-control/handoff/<timestamp>.md`

**Behaviour:**
1. Write a compact summary: decisions made, what's next, what's blocked.
2. Update `adam/context/*` if preferences changed.
3. Note any TODO that spans multiple sessions.
4. Tell the operator: "you can close; resume by reading the handoff file."
