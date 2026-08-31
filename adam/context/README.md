# adam/context/ — Calibration

These files are written by the **`calibrate`** skill the first time you install Adam (Phase 0). They store stable info about you and the project so every future session in this repo has the same baseline.

Adam reads these at the top of every response in a calibrated project:

```
adam/context/user-profile.md          # Who you are (operator profile)
adam/context/technical-level.md       # How much to explain
adam/context/preferences.md           # How you like to work
adam/context/founder.md               # The story behind Gatcha Kingdom
adam/context/project.md               # What this repo is
```

The files are intentionally short and human-written (with Adam's help). They are the **only** files Adam always re-reads when starting a new session. Everything else (memory, handoffs, plans) lives in `adam/memory/`.

If you ever want to reset Adam's understanding of you, edit these files directly. Don't ask Adam — it will just defer to whatever's here.

## Status

All five files are placeholders for now. Phase 0 (`docs/PHASE_0.md`) walks you through the `calibrate` interview that fills them in.
