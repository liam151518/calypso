---
name: grill-me
description: Drill down on a decision branch until it's closed (one open question at a time).
---

# Grill-me

**When to use:** Anytime `intake` or `council` surfaces a decision branch with >2 viable options.

**Inputs:** open decision branch
**Outputs:** closed decision (added to `plan/architecture.md` or `plan/adr/NNNN-*.md`)

**Behaviour:**
1. Ask ONE question at a time. The question must be a binary or forced choice.
2. After each answer, restate the remaining open branches and pick the next most-blocking one.
3. Stop when no branches remain or the operator says "stop grilling".
4. Never loop on the same question more than twice without escalating.
