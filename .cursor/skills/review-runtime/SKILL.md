---
name: review-runtime
description: Drive the live UI/service via Chrome DevTools MCP to confirm the user-visible flow works.
---

# Review-runtime

**When to use:** After `dispatch-builder` reports green; before merging the slice.

**Inputs:** URL to inspect, scenario to exercise
**Outputs:** runtime review notes appended to `slices/NNN-name/review.md`

**Behaviour:**
1. Open the URL; capture the page state.
2. Exercise the happy path through the UI (or via direct API calls if no UI).
3. Capture a screenshot or response payload.
4. If anything looks wrong, file a regression bug and re-dispatch.
