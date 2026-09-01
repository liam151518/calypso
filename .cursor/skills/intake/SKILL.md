---
name: intake
description: Adam intake. Turn a fuzzy brief into a structured product-brief.md.
---

# Intake

**When to use:** Beginning of a new project, or whenever the brief is fuzzy.

**Inputs:** operator chat, optional existing `packet/product-brief.md`
**Outputs:** `packet/product-brief.md` with the decision tree closed

**Behaviour:**
1. Walk through: who is the user, what does success look like, what is the budget,
   what is the timeline, what are the constraints, what is explicitly out of scope.
2. Use `grill-me` for any open decision branches.
3. Final brief is short (≤1 page) and uses bullets, not prose.
4. Append any new decision branches to `plan/architecture.md`.
