# Phase 3 — Video Pipeline

**Goal:** 1 image + 1 video per day, both via Telegram approval.

**Time:** ~2 weeks

**Outcome:** Daily mix of images and videos; H3 generates native audio so most clips ship without ElevenLabs.

---

## Video model stack (recap from the plan)

| Tier | Model | Where | Use | Cost |
|---|---|---|---|---|
| **Primary** | MiniMax H3 (Ref2VA) | Cloud `api.minimax.io` | Daily clips — best quality, native stereo audio, matches our reference-driven philosophy | ~$10-15/mo |
| **Speed** | MiniMax H3 Max | fal.ai | High-volume dailies (faster variant of H3, 480p/768p only) | ~$3-5/mo |
| **Hero** | fal.ai Kling 2.6 Pro | fal.ai | 1 clip/week when nothing else cuts it | ~$2-3/mo |
| **Local** | MiniMax H3 (quantized) | RTX 5070 via ComfyUI | Optional — benchmarked in Phase 4 | ~$0 (electricity) |

**Why H3:** it has a `MiniMaxH3ReferenceToVideo` node. Feed it Folder A references + brand assets from Folder B, get a coherent gacha-style clip with native 32 kHz stereo audio. That's exactly the anti-slop reference-driven philosophy, but for video.

---

## What Adam builds

Adam follows the same loop as Phase 2:

```
research-and-plan → tests-first → dispatch-builder → review-via-graph → review-runtime
```

This phase produces:

1. **n8n workflow** at `workflows/02-video-generation.json`
2. **ComfyUI workflow** at `comfyui/02-h3-reference-to-video.json` (for the local benchmark)
3. **Test suite** additions in `tests/`
4. **Python clients** for both MiniMax H3 API and fal.ai (H3 Max + Kling):
   - `scripts/h3_client.py` — talks to `api.minimax.io` (H3-Context-IR → H3-Base → H3-Regenerate-2K)
   - `scripts/falai_client.py` — H3 Max and Kling 2.6 Pro endpoints
   - `scripts/generation_router.py` — picks which backend based on tier, queue depth, cost budget
5. **Caption generator upgrade** — the prompt builder now emits motion descriptions + audio cues

---

## Step-by-step

### Step 1 — Cloud setup

**Say to Adam:**

```
Walk me through creating the MiniMax H3 video via the API. Show me a curl request for the 3-stage pipeline (H3-Context-IR → H3-Base → H3-Regenerate-2K) using a reference image from references/ready/.
```

Adam walks you through the API. Once you see it work, you know the auth + payload format.

### Step 2 — Research + plan

**Say to Adam:**

```
Run research-and-plan to design the video pipeline. We're using MiniMax H3 API as primary, H3 Max via fal.ai as speed tier, Kling 2.6 Pro as hero tier. Plan the router logic, the fallback chain, and the cost cap.
```

Adam produces `plan/03-video-pipeline.md` + slice breakdown.

### Step 3 — Tests first

**Say to Adam:**

```
Use tests-first to write the failing tests for the video pipeline. Include tests for: H3 client returns a valid task_id, fal.ai client returns a valid request_id, generation router picks the right tier based on the spec, generation_router respects the monthly cost cap.
```

### Step 4 — Build

**Say to Adam:**

```
Run dispatch-builder on slices/005-n8n-video-workflow-h3/. Make the tests green.
```

Builder implements:
- `scripts/h3_client.py`
- `scripts/falai_client.py`
- `scripts/generation_router.py`
- Upgraded `scripts/post_process.py` (now handles video: FFmpeg trim + MoviePy captions + audio mix)
- `workflows/02-video-generation.json`
- `comfyui/02-h3-reference-to-video.json` (for the Phase 4 benchmark)

### Step 5 — ComfyUI H3 template

**Say to Adam:**

```
Open the MiniMax H3 native ComfyUI nodes and generate a 6-node workflow template using MiniMaxH3ReferenceToVideo. Save it as comfyui/02-h3-reference-to-video.json. This is for the Phase 4 local benchmark — don't run it yet.
```

The template is the one MiniMax ships in ComfyUI's template gallery; Adam copies the structure into this repo.

### Step 6 — Test week

Let the video pipeline run for a week, ~7 video posts. The Telegram approval messages now include the audio — listen, don't just look.

**Say to Adam:**

```
Review the last 7 video generations. Compare native H3 audio vs the posts where we used ElevenLabs. Tell me which performed better by your taste (we don't have engagement data yet). Suggest adjustments.
```

---

## Cost cap setup

The plan assumes ~$20/mo on cloud video. Add a hard cap so a runaway cron doesn't blow the budget.

**Say to Adam:**

```
Add a monthly cost cap of $30 to the generation router. If projected spend exceeds 80% of the cap, fall back to the cheapest tier (LTX 2.0 via fal.ai at $0.04/s). If it exceeds 95%, send me a Telegram alert and pause generation until I ack.
```

Adam implements the cap in `scripts/generation_router.py` and writes tests for it.

---

## License review (mini-council)

Even though the full license review happens in Phase 4, do a quick check now since you're about to publish H3-generated content.

**Say to Adam:**

```
Read the MiniMax H3 Community License Agreement (it's bundled with the open-source release on Hugging Face). Tell me whether the license allows commercial use of H3-generated video in paid social media ads. Quote the relevant clause.
```

Adam reads it and reports. If there's a restriction, you have time to pivot to a different model before posting.

---

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| H3 returns a 2K video but Telegram rejects the upload | Telegram bots have a 50 MB upload limit | Downscale to 1080p in `post_process.py` (FFmpeg `-vf scale=1920:-2`) |
| H3 native audio is silent or stuttering | Encoding mismatch when re-muxing | Verify FFmpeg uses `-c:a copy` for the audio stream |
| H3 generation takes 5+ minutes for a 10s clip | You're hitting the H3-Context-IR step, which is hosted and may have queue | Acceptable — primary tier is allowed 10 min budget |
| fal.ai H3 Max returns "model not found" | H3 Max is still rolling out — check fal.ai docs | Fall back to base H3 via MiniMax API until H3 Max is GA |
| Kling 2.6 Pro clips look generic | Kling is text-to-video heavy, not reference-driven | Use H3 for reference-driven; only use Kling for cinematic hero shots |
| Cost cap triggers every day | Cost-per-clip estimate was off | Adam re-benchmarks with real numbers; raise cap or lower resolution |

---

## Done with Phase 3?

**Say to Adam:**

```
Phase 3 is done. Run a council review of the full image + video loop. Include the H3 license review. Write the council output to plan/council/2026-XX-XX-full-loop-review.md.
```

Adam's council runs seven perspectives:
1. Visual quality (A-tier references still anchoring?)
2. Brand consistency (watermark, palette, voice)
3. Cost (within budget?)
4. Reliability (uptime, failure modes)
5. Anti-slop (any AI tells creeping in?)
6. Engagement (proxy metrics from week 1-3)
7. **License posture** (H3 Community License compatibility with commercial ads)

Output is a Phase 4 to-do list.

---

## Next phase

**→ `docs/PHASE_4.md`** — optimization (local H3 benchmark, Brand LoRA training, A/B tests, re-weighted Folder A)
