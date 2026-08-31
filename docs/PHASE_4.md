# Phase 4 — Optimization

**Goal:** Make the pipeline cheaper, faster, and better-looking based on real data.

**Time:** ~3 weeks

**Outcome:** Brand LoRA trained; local H3 benchmarked; Folder A re-weighted by real engagement; A/B test results in hand.

---

## 4.1 — Local MiniMax H3 benchmark

**Question:** can the RTX 5070 run quantized H3 fast enough to be worth it?

**Say to Adam:**

```
Benchmark local MiniMax H3 on the RTX 5070. Use the ComfyUI native nodes (MiniMaxH3ReferenceToVideo). Try: BF16 (probably OOM), int8, int4. Target: 5-second 768p clip in under 5 minutes. Report wall-clock time, peak VRAM, and output quality vs the cloud H3 reference.
```

What Adam does:
1. Tries the BF16 weights first (likely OOM at 12 GB)
2. Falls back to int8 quantization via `bitsandbytes` or ComfyUI's quant nodes
3. If int8 fits, measures wall-clock for a 5s 768p clip
4. If int8 is too slow, tries int4
5. Compares a side-by-side clip with the cloud H3 output (same prompt + same references)
6. Reports: speed, VRAM, quality verdict

**Outcome:**
- **If local < 5 min/clip AND quality is acceptable:** route a fraction of dailies to local. Save $15-20/mo.
- **If local > 5 min/clip OR quality degrades noticeably:** stick with cloud. Document why and revisit when hardware upgrades.

Write the benchmark results to `plan/benchmarks/h3-local-5070.md`.

---

## 4.2 — Train the Brand LoRA

The Brand LoRA is the model that injects Gatcha Kingdom's visual DNA into every image generation. Without it, the IP-Adapter just gives you "looks like the reference." With it, you get "looks like the reference, in our brand."

**Say to Adam:**

```
Train the Brand LoRA on the 30+ best published assets from the last 3 weeks. Use kohya-ss/sd-scripts with the RTX 5070 (Blackwell — may need the latest kohya-ss that supports sm_120). Target rank 8, alpha 16. Use the brand palette and the site screenshots from brand/screenshots/ as part of the training set.
```

What Adam does:
1. Curates the training set from your approved posts (not the inbox — only A-tier approvals)
2. Augments with brand assets from `brand/screenshots/` and `brand/logo/`
3. Configures kohya-ss with:
   - **Base model:** SDXL or Flux (you choose based on what ComfyUI is running)
   - **Network rank:** 8 (low — prevents memorization)
   - **Learning rate:** 1e-4 (standard for SDXL LoRA)
   - **Steps:** 1500 (enough for the small dataset, prevents overfit)
   - **Resolution:** 1024×1024
4. Trains overnight on the 5070
5. Validates by generating 10 test images with the new LoRA + IP-Adapter + ControlNet
6. You approve or reject the LoRA based on whether the brand DNA is now consistent across styles

**If rejected:** Adam increases the training set (more approved assets) or lowers the rank (less memorization).

**If approved:** Adam saves the LoRA at `comfyui/models/loras/gachakingdom-v1.safetensors` and updates `comfyui/01-image-with-style-reference.json` to load it.

---

## 4.3 — MiniMax H3 license review

**Say to Adam:**

```
Read the MiniMax H3 Community License Agreement. Tell me:
1. Can we use H3-generated video in paid social media ads?
2. Are there restrictions on revenue, user count, or use case?
3. Do we need to attribute H3 in the post?
4. If there are restrictions, what's the workaround (e.g., self-hosted H3-Base weights only)?
Write the analysis to plan/adr/0003-h3-license-posture.md.
```

Adam reads the license and writes an ADR (Architecture Decision Record). The verdict drives whether H3 stays in the production pipeline or gets swapped for an unrestricted alternative.

---

## 4.4 — Re-weight Folder A

Now you have ~3 weeks of engagement data. Time to let the data update the picker.

**Say to Adam:**

```
Analyze engagement from the last 3 weeks by reference style_tag. Which tags got the most likes/shares relative to follower count? Update the reference_picker.py weights: top tags get 3x, mid get 1x, bottom get 0.3x. Archive references whose tags didn't perform.
```

Adam reads the analytics (Social Stats has an API for this), groups by tag, re-weights, archives the dead weight. Result: future picks lean into what's working.

---

## 4.5 — A/B tests

Three A/B tests to run in parallel:

**A/B 1: post-processed vs raw**

For each generation, also save the raw (no watermark, no text overlay). Half the time, post the post-processed version. Compare engagement.

**A/B 2: UGC voiceover vs H3 native audio**

For H3 videos: half the time, mute H3's audio and overlay an ElevenLabs voiceover. Other half, use H3's native audio. Compare engagement.

**A/B 3: 5s vs 8s vs 10s clips**

Generate the same reference at three durations. Post each variant. Compare completion rate + engagement.

**Say to Adam:**

```
Set up three A/B tests in the generation router: post-processed vs raw, UGC voiceover vs H3 native audio, 5s vs 8s vs 10s. Use Telegram button callbacks to log which variant the user picked when they manually approve.
```

Wait ~2 weeks. Compare.

---

## 4.6 — Variant generator

The plan's optimization todo: one reference → 3 variants → pick best.

**Say to Adam:**

```
Build the variant generator. For each pick, generate 3 variants (different motion prompts, different aspect ratios, different captions). Telegram approval message shows 3 thumbnails; you tap the one you want. The other two get archived with the reason.
```

Builder adds:
- `scripts/variant_generator.py`
- New n8n node chain
- Telegram inline keyboard with 3 thumbnails

---

## Done with Phase 4?

**Say to Adam:**

```
Phase 4 is done. Run another council review. Compare against the Phase 3 council. What's improved? What regressed? What new risks emerged? Write to plan/council/2026-XX-XX-phase-4-review.md.
```

---

## Next phase

**→ `docs/PHASE_5.md`** — scale (TikTok, auto-reply, RSS triggers, evergreen bank, handoff prep)
