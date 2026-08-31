# slices/ — Vertical-slice task breakdowns

Adam breaks each phase into **vertical slices** during `slice-to-tasks`. Each slice is a user-visible behavior change, not a layer (per the Adam rules: "Build in vertical slices, not layers").

A slice lives in its own folder:

```
slices/
├── README.md
├── 001-folder-a-scraper/         # one slice per folder
│   ├── brief.md                  # what this slice delivers
│   ├── tasks.md                  # task list for the builder
│   ├── tests/                    # tests for this slice (written by Adam only)
│   └── notes.md                  # anything the builder flagged during execution
├── 002-folder-b-brand-pack/
├── 003-local-comfyui-setup/
├── 004-n8n-image-workflow/
├── 005-n8n-video-workflow-h3/
└── ...
```

## What goes in a slice

Per Adam's `slice-to-tasks` skill:

- **One user-visible behavior.** E.g., "post a single image to Telegram for approval" is one slice. "Configure ComfyUI" is not.
- **Vertical.** Each slice touches every layer it needs (script + n8n node + ComfyUI workflow + test + Telegram wiring).
- **Testable.** The slice has its own `tests/` which Adam writes via `tests-first` and the builder makes green.
- **Reversible.** If a slice fails review, it can be reverted without breaking other slices.

## When folders appear

Phase 0: empty.
Phase 1+: Adam populates `00X-...` folders as it executes each phase.

Don't pre-write slices. They're Adam's domain.
