# Phase 2 — Image Pipeline

**Goal:** First automated image post hits your Telegram for approval.

**Time:** ~2 weeks (one for build, one for refinement)

**Outcome:** 2 image posts per day land in your Telegram; you Approve / Regenerate / Skip; approved ones auto-publish to X and Instagram.

---

## What Adam builds

Adam follows the loop from the Adam README:

```
research-and-plan → tests-first → dispatch-builder → review-via-graph → review-runtime
```

This phase produces **three deliverables** in this repo:

1. **n8n workflow** at `workflows/01-image-generation.json`
2. **ComfyUI workflow** at `comfyui/01-image-with-style-reference.json`
3. **Test suite** at `tests/` (5+ files, all written by Adam via `tests-first`)

Plus supporting Python scripts in `scripts/`:

- `reference_picker.py` — weighted random over `references/ready/*.json`
- `prompt_builder.py` — assembles generation prompt from reference + brand
- `comfyui_client.py` — HTTP wrapper around ComfyUI's API
- `post_process.py` — Pillow: watermark + text overlay + color grade
- `telegram_notify.py` — sends preview to Telegram with inline buttons

---

## Step-by-step

### Step 1 — Research + plan

**Say to Adam:**

```
We need to build the image pipeline. Phase 1 is done. Run research-and-plan to design the n8n workflow and the ComfyUI image workflow. Reference the blueprint in /Users/liamsantos/.cursor/plans/gachakingdoms_ad_pipeline_plan_ca486772.plan.md (sections Phase 2 and 1.1/1.2/1.3). Write the plan to plan/02-image-pipeline.md and break it into vertical slices under slices/.
```

Adam researches:
- ComfyUI's HTTP API surface
- IP-Adapter Plus node parameters
- The reference-picker weighting scheme
- Telegram bot inline button callback format
- Pillow text overlay on the brand palette

Then writes a plan doc + ADR + slice breakdown.

### Step 2 — Tests first

**Say to Adam:**

```
Use tests-first to write the failing tests for the image pipeline. Builders will make them green.
```

Adam writes tests at:

```
tests/test_reference_picker.py
tests/test_prompt_builder.py
tests/test_comfyui_client.py
tests/test_post_process.py
tests/test_telegram_notify.py
```

You verify they fail (red) — that's the whole point of red-green-refactor. Adam verifies, you confirm.

### Step 3 — Build

**Say to Adam:**

```
Run dispatch-builder on slices/004-n8n-image-workflow/. Make the tests green. Use the Brand LoRA placeholder pattern from the plan — we'll train the real LoRA in Phase 4.
```

A builder (sub-agent) implements:
- `scripts/reference_picker.py`
- `scripts/prompt_builder.py`
- `scripts/comfyui_client.py`
- `scripts/post_process.py`
- `scripts/telegram_notify.py`
- `workflows/01-image-generation.json`
- `comfyui/01-image-with-style-reference.json`

You should **never see this builder's work directly** — it commits to a branch and Adam reviews before merging.

### Step 4 — Review

**Say to Adam:**

```
Run review-via-graph on the image pipeline slice, then review-runtime if you have Chrome DevTools MCP available.
```

Two checks:
1. **Graph review** — does the code structure match the plan? Are the imports clean? Are the tests actually testing what they claim?
2. **Runtime review** — does the workflow actually generate an image when triggered manually in n8n? Does the Telegram approval flow round-trip?

Adam reports findings. If anything's broken, `dispatch-builder` retries.

### Step 5 — Run for real

**Say to Adam:**

```
Run the image workflow manually with a test reference. Show me the Telegram approval flow end-to-end.
```

Adam triggers n8n with a fake reference, you see a Telegram message with the preview image + Approve / Regenerate / Skip buttons. You approve it. The post goes nowhere (no platform creds wired yet — that's Phase 5 work).

### Step 6 — Schedule

**Say to Adam:**

```
Set the cron to fire at 12:00 and 18:00 SAST. We're in South Africa, so use Africa/Johannesburg timezone.
```

Adam configures the cron trigger.

---

## Test week

Let it run for a week. You'll get 14 posts in Telegram. **Don't approve anything that looks even slightly off** — the approval gate is the only thing standing between the pipeline and slop.

At end of week:

**Say to Adam:**

```
Review the last 14 generations. Tell me which references got picked, which brand voice terms survived, which posts you would have approved vs rejected. Then suggest adjustments to the reference picker weights and the prompt builder.
```

Adam analyzes and proposes changes. You approve or reject each.

---

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| ComfyUI hangs on generation | Out of VRAM — Brand LoRA + IP-Adapter + ControlNet + SDXL exceeds 12 GB | Reduce resolution to 1024×1024; or run ControlNet at half precision; or drop Brand LoRA temporarily |
| Telegram buttons don't work | Bot token missing `inline_keyboard` permission | Re-create bot via @BotFather → /setinline |
| Reference picker keeps returning the same 5 references | Weighting bug — check `engagement_tier` is read correctly | Adam fixes in `dispatch-builder` |
| Generated images all look like the reference (no brand) | IP-Adapter strength too high, Brand LoRA strength too low | Adjust in ComfyUI workflow JSON (Adam handles) |
| Generated images all look like the brand (no style) | IP-Adapter strength too low | Same as above |
| Watermark covers key visual | Watermark placement rule needs tuning | Update `scripts/post_process.py` |

---

## Done with Phase 2?

**Say to Adam:**

```
Phase 2 is done. I've approved 14 image posts. Run verify.sh and run a council review of the whole image loop.
```

Adam runs `council` — seven perspectives on the running image pipeline. The output is a list of Phase 4 optimization candidates. You triage them.

---

## Next phase

**→ `docs/PHASE_3.md`** — add video (MiniMax H3 cloud primary, H3 Max via fal.ai speed tier, Kling hero tier)
