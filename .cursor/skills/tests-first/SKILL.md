---
name: tests-first
description: Write the test suite FIRST, then hand off to dispatch-builder to make it green.
---

# Tests-first

**When to use:** Whenever a new vertical slice introduces new scripts or workflows.

**Inputs:** `slices/NNN-name/plan.md`
**Outputs:** `tests/test_*.py` with failing tests

**Behaviour:**
1. Write tests for: happy path, each error path, each edge case named in the plan.
2. Use fakes/monkeypatch where appropriate — no live network calls in tests.
3. Run pytest once to confirm tests fail in the expected way.
4. Hand off to `dispatch-builder` with the failure log.
