---
name: calibrate
description: One-time Adam calibration. Interviews the operator to fill in adam/context/.
---

# Calibrate

**When to use:** First time Adam runs in a new project, or whenever the operator's
preferences change materially.

**Inputs:** operator chat
**Outputs:** `adam/context/preferences.md`, `adam/context/operator-profile.md`,
`adam/context/project-goals.md`

**Behaviour:**
1. Ask 5-7 short, focused questions (no marathon interviews):
   - Technical level (junior / senior / staff / principal)
   - Preferred response length (terse / balanced / detailed)
   - Tone preference (direct / warm / dry)
   - Decision style (defer-to-me / decide-and-tell / consensus)
   - Tooling constraints (offline-only / cloud-ok / hybrid)
   - Top-3 success metrics for this project
2. Write the answers to `adam/context/*.md` with stable filenames.
3. Confirm with a one-paragraph summary; ask the operator to confirm or correct.

**Don't:** ask more than 8 questions in one go.
