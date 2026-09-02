# Calypso — User Guide

Welcome to Calypso, your local-first marketing studio. This guide walks a
non-technical operator through their first end-to-end workflow: pick a
brand, generate a poster, refine it, schedule it, and publish it.

## What is Calypso?

Calypso is a single-operator marketing platform that runs on your laptop
or a $5 VPS. It bundles:

- A **brand poster studio** with 11 templates, 5 filters, a WYSIWYG editor
- A **UGC video generator** that turns a brief into a 30-second MP4
- A **multi-agent Studio Pro** that suggests campaigns from one paragraph
- A **refinement studio** to iterate on every generated output
- A **scheduler** with Telegram approvals
- **Instagram publishing** via `instagrapi`
- A **plugin marketplace** you can extend with HMAC-signed extensions

Everything is yours. No cloud lock-in, no per-seat fees, no telemetry.

## Step 1 — Set up your brand

1. Open the SPA, navigate to **Brand**.
2. Fill in the form:
   - **Name** — your brand or product line
   - **Voice tone** — `bold`, `playful`, `luxury`, `minimal`, `casual`, `cinematic`
   - **Palette** — hex colors, one per line
   - **Banned words** — comma-separated
   - **Default filter** — `moody`, `bright`, `vintage`, `minimal`, `neon`
   - **Default aspect ratio** — `1:1`, `4:5`, `9:16`, `16:9`
3. Click **Save**.

The active brand is now used everywhere downstream.

## Step 2 — Add a product

1. **Products** → **Add product**.
2. Either fill the form or paste a CSV with columns
   `name,price,category,collection,description,tags`.
3. Upload a hero image. Calypso auto-cuts the background with `rembg` on
   the first render — the cutout is cached so subsequent renders skip the
   model call.

## Step 3 — Generate your first poster

1. **Generate** → choose **Bold Drop** (or any template).
2. Write a prompt:
   > Hero model wearing the new sneaker, low angle, neon rim-light,
   > cinematic, midnight black background.
3. Pick a model. Default is `MiniMax H3`; pick **Flux Pro 1.1** for static
   stills.
4. Click **Run generation**. The job runs in the background.

When the job finishes, the file appears under **Outputs**. Click it to
open the **Refinement Studio**.

## Step 4 — Refine the result

The Refinement Studio has three columns:

- **Left (Layers):** every layer the compositor produced. Click any to
  reveal controls:
  - `ai_background` / `ai_image` — change the prompt, seed, or model and
    re-render just that layer.
  - `text` — edit the text in place.
  - `image` — replace the cutout.
- **Center (Preview):** the current render. Click **Compare** on any
  version in the right column to see them side-by-side.
- **Right (Refine):**
  - **Quality** tab — upscale to 2x / 4x via local Real-ESRGAN or cloud
    `fal.ai`. Toggle face enhancement.
  - **Variants** tab — every saved version. Click **Promote** to make one
    the canonical output, **Delete** to drop it.
  - **VFX** tab — for video outputs, edit motion-graphic timing and
    easing (coming soon).

### The most powerful trick: regenerate a single layer

Don't like the background? Don't regenerate everything. Click the
**Background** layer, change the prompt, click **Regenerate layer**. Your
product, text, and logo stay exactly where they are. The new version
appears in **Variants** so you can compare it against the original.

## Step 5 — Generate a caption

1. Click **Generate caption** on the output (or open it under **Outputs**
   and click the caption icon).
2. By default Calypso uses a per-tone word bank — no API key needed.
3. To get LLM-powered captions, go to **Settings → API keys**, set
   `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` / `MINIMAX_API_KEY`), and pick
   a provider with `LLM_PROVIDER`. The heuristic path is the fallback —
   you can keep using it forever.

## Step 6 — Schedule + publish

1. From the output page, click **Schedule**.
2. Pick a date, time, and platform (`instagram`, `tiktok`, `x`, `linkedin`,
   `facebook`).
3. Calypso sends the post to your Telegram chat for approval. Approve,
   reject, or skip. Approved posts go to the configured publisher.
4. With `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` set, Calypso will
   actually upload to Instagram using `instagrapi`. Without them, the
   scheduler logs the publish as a dry-run and you'll need to manually
   copy the asset to the platform.

## Optional — Enable skills

**Skills** are markdown files injected into every LLM call. Four built-ins
ship:

- `ugc_video` — UGC scripting patterns
- `image_ad` — direct-response ad patterns for static posts
- `prompt_enhancement` — generic prompt-quality upgrades
- `caption_optimizer` — tightens captions, strips filler words

Open **Skills**, toggle each on/off, edit their markdown inline, and add
your own custom skills. See [`SKILLS.md`](SKILLS.md) for the frontmatter
spec.

## Optional — Install a desktop build

```bash
./scripts/desktop-build.sh
```

This produces a Tauri shell that wraps the local Flask backend. See
[`RELEASE.md`](RELEASE.md) for packaging details.

## What's next?

- **Iterate.** Watch the outputs, refine the ones you like, drop the rest.
- **Customize.** Edit brand voice, swap fonts, change the default filter.
- **Extend.** Browse the extension marketplace for new templates, filters,
  publishers, and AI backends.
- **Read more.** [`REFINEMENT_STUDIO.md`](REFINEMENT_STUDIO.md) covers the
  editing surface in depth; [`SKILLS.md`](SKILLS.md) shows how to write
  your own skills.
