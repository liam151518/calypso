---
name: dispatch-builder
description: Make the tests green without breaking adjacent tests.
---

# Dispatch-builder

**When to use:** After `tests-first` produces a failing suite.

**Inputs:** failing test output
**Outputs:** green pytest + the new scripts/workflows

**Behaviour:**
1. Read the failing test first; understand the contract you need to satisfy.
2. Write the minimum code to make it pass. No gold-plating.
3. After green, re-run the entire suite to confirm no regressions.
4. Update `verify.sh` if new directories or files are required by the contract.
