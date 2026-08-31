---
name: research-and-plan
description: For a new vertical slice, research existing patterns and emit a design plan.
---

# Research-and-plan

**When to use:** Beginning of a new vertical slice (`slices/NNN-name/`).

**Inputs:** slice brief in `slices/NNN-name/brief.md`
**Outputs:** `slices/NNN-name/plan.md`

**Behaviour:**
1. Read existing patterns from the codebase (use the Explore agent for breadth).
2. Identify 1-2 viable designs; pick one with rationale.
3. List the contracts: functions to create, files to touch, tests to write.
4. List explicit non-goals.
5. Keep the plan ≤200 lines. No code in the plan — only design.
