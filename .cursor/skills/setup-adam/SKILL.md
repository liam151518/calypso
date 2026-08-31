---
name: setup-adam
description: One-shot project bootstrap — creates packet/, plan/, slices/, agent-control/, .cursor/skills/.
---

# Setup-adam

**When to use:** First time this project is opened with Adam.

**Inputs:** none (idempotent)
**Outputs:** all required folders + a populated `.cursor/skills/` directory

**Behaviour:**
1. Ensure these folders exist: `packet/`, `plan/`, `plan/adr/`, `slices/`, `agent-control/`, `adam/context/`.
2. Ensure `.cursor/skills/` is populated with the canonical Adam skills
   (calibrate, intake, grill-me, research-and-plan, tests-first, dispatch-builder,
   review-via-graph, review-runtime, council, dev-launch-debug, session-steward).
3. Run `bash verify.sh` and confirm the gate passes.
4. Print a one-paragraph summary of what's now in place.
