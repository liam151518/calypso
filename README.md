<div align="center">

# Calypso

### The open-source marketing studio that lives on your laptop.

Generate video and image ads with the top AI models. Edit them layer by layer. Schedule them to Instagram, Telegram, and the feed of your choice. All from a single dashboard. All local-first. All MIT.

<br />

<p align="center">
  <a href="https://github.com/liam151518/calypso/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge"></a>
  <a href="https://github.com/liam151518/calypso/stargazers"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/liam151518/calypso?style=for-the-badge&logo=github"></a>
  <a href="https://github.com/liam151518/calypso/releases"><img alt="Release" src="https://img.shields.io/github/v/release/liam151518/calypso?style=for-the-badge&color=ff6a1f"></a>
  <a href="https://github.com/liam151518/calypso/actions"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/liam151518/calypso/release.yml?style=for-the-badge&label=CI"></a>
  <a href="#-quickstart"><img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://github.com/liam151518/calypso#-quickstart"><b>Quickstart</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="https://github.com/liam151518/calypso#-features"><b>Features</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="https://github.com/liam151518/calypso/tree/main/docs"><b>User Guide</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="https://github.com/liam151518/calypso#-screenshots"><b>Screenshots</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="https://github.com/liam151518/calypso#-contributing"><b>Contributing</b></a>
</p>

</div>

---

## Why Calypso?

Most "AI marketing tools" charge you $99/seat and lock your brand assets behind a subscription. Calypso is the opposite.

- **Own your stack.** Python + SQLite + React. No cloud lock-in. Fork it into a SaaS or run it on a Raspberry Pi.
- **Use every model.** MiniMax H3, Fal.ai, Kling 2.6, OpenAI, Anthropic, Local Real-ESRGAN. Switch providers per request, per job, per layer.
- **Edit the output, don't re-roll it.** The Refinement Studio lets you regenerate a single layer, upscale 2x-8x, swap fonts, change timing, and save versions without losing the original.
- **Stay in one window.** Brief → Model → Edit → Refine → Schedule → Publish. The whole pipeline lives at `localhost:8765`.

---

## ⚡ Quickstart

```bash
git clone https://github.com/liam151518/calypso.git
cd calypso
bash run.sh
```

Opens **`http://localhost:8765`**. First boot is a guided onboarding: paste your `FAL_API_KEY` and (optionally) `MINIMAX_API_KEY` from the Settings page.

> Prefer a different port? `CALYPSO_PORT=9000 bash run.sh`

That's it. No Docker. No Kubernetes. No telemetry. The same one-line launcher runs on macOS, Linux, and Windows (WSL).

---

## ✨ Features

<details open>
<summary><b>🎬 Generation</b> — Run the top models from one place</summary>

<br />

| Capability | What it does |
|---|---|
| **Video generation** | MiniMax H3, H3 Max, Kling 2.6 Pro via Fal.ai. Reference-driven, prompt-only, or template-based. |
| **Image generation** | Flux Pro 1.1, Flux Dev, SDXL, Ideogram. Cost caps, live previews, batch mode. |
| **Layered templates** | JSON-defined canvas with AI background, product cutout, text, watermark. Variable substitution and safe zones. |
| **Live cost estimate** | USD shown before every run. Caps per project and per month. |
| **Reference vault** | Upload images and clips as style anchors. Tag them. Auto-pick by similarity. |

</details>

<details>
<summary><b>🎨 Refinement Studio</b> — Edit every output, layer by layer</summary>

<br />

- **Per-layer regeneration.** The AI background is wrong? Click *Regenerate Background*. Your product, text, and logo stay exactly where they were.
- **Version history.** Every save creates a new row in `output_versions`. Promote any version to canonical. Compare side by side.
- **Upscaling.** Local Real-ESRGAN (free, RTX fast) or Fal.ai cloud (better quality). 2x, 4x, 8x. Face enhance, denoise, grain.
- **Color grading.** Curves, HSL, temperature/tint, split toning. Save as a preset.
- **VFX timeline** *(video)*. Scrub scene boundaries, shift motion graphics, change easing per clip.

> See [`docs/REFINEMENT_STUDIO.md`](docs/REFINEMENT_STUDIO.md) for the full tour.

</details>

<details>
<summary><b>🤖 Multi-agent Studio Pro</b> — Brief in, campaign out</summary>

<br />

Five agents take a one-paragraph brief and produce a runnable campaign:

1. **Director** reads the brief, picks tone + energy.
2. **Template selector** finds the best template match in your catalog.
4. **Copywriter** writes the caption in your brand voice (with banned words enforced).
5. **Visual strategist** tunes the color grade and filters.
6. **Campaign builder** assembles the runnable suggestion with a `confidence_score`.

Confidence formula: `0.4·brand_compat + 0.3·template_score + 0.2·novelty + 0.1·cost_feasibility`.

> Read the playbook in [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

</details>

<details>
<summary><b>🧠 Skills System</b> — Encapsulate prompt engineering as pluggable Markdown</summary>

<br />

Skills are `.md` files with YAML frontmatter that inject pre-prompts and post-process rules into the pipeline. Four ship out of the box:

- **`ugc_video`** — UGC scripting patterns: hook in 2 seconds, conversational tone, no overclaims.
- **`image_ad`** — Composition rules: visual hierarchy, contrast, brand-safe colors.
- **`prompt_enhancement`** — Rewrites your prompt for better model performance.
- **`caption_optimizer`** — Cleans filler words, enforces brand banned-words list.

Write your own in `~/.calypso/skills/`. Toggle from the UI.

> Read the spec in [`docs/SKILLS.md`](docs/SKILLS.md).

</details>

<details>
<summary><b>📦 Publishing & Scheduling</b> — Telegram approvals, Instagram auto-post</summary>

<br />

- **Telegram approval gate.** Schedule a post → get a Telegram message with *Approve* / *Edit* / *Cancel* → on approval, it ships.
- **Instagram publisher.** `instagrapi` plugin uploads photos and reels directly. Session persists across restarts.
- **Scheduler v2.** APScheduler with cost caps, retry, dead-letter queue.
- **Dry-run mode.** Test the full flow without spending API credits.

</details>

<details>
<summary><b>🔌 Extension marketplace</b> — Drop-in plugins with HMAC signing</summary>

<br />

Manifest-driven loader. Add new models, agents, publishers, importers. Manifests are signed with HMAC-SHA256. Hook into the pipeline without editing core.

```
extensions/
  ├── my-video-model/
  │   ├── manifest.json
  │   ├── plugin.py
  │   └── tests/
```

> Architecture in [`docs/RELEASE.md`](docs/RELEASE.md).

</details>

<details>
<summary><b>🖥️ Multi-surface</b> — Local, desktop, Docker, PyPI</summary>

<br />

| Surface | How |
|---|---|
| **Local Flask** | `bash run.sh` → `localhost:8765` |
| **Desktop** | `bash scripts/desktop-build.sh` → `.dmg` / `.exe` / `.AppImage` |
| **Docker** | `docker compose up` → Caddy for HTTPS |
| **Headless / CI** | `pip install calypso` → use the Python API directly |
| **Tauri shell** | `web/` + native menu bar |

</details>

---

## 📸 Screenshots

<p align="center">
  <em>Drop-in screenshots once you generate your first campaign. The product is dark-mode native with an operator-console aesthetic.</em>
</p>

> **Screenshots coming soon.** The product is dark-mode native with an operator-console aesthetic (think Linear meets Vercel). Drop a PNG into `docs/img/` and open a PR if you want to contribute your workflow shots.

---

## 🏗️ Architecture

```
                        ┌─────────────────────────────────┐
                        │   React SPA (Vite + Tailwind)   │
                        │  Generate · Refine · Studio Pro │
                        │  Templates · Products · Skills  │
                        └────────────────┬────────────────┘
                                         │  fetch / SSE
                                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                          Flask  +  SQLite                          │
│  server.py · scheduler · compositor · generation_router            │
└─────┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
      │          │          │          │          │
      ▼          ▼          ▼          ▼          ▼
  MiniMax H3   Fal.ai    Real-ESRGAN  Instagrapi   OpenAI/Anthropic
```

**Stack:**
- **Backend:** Python 3.11+, Flask, SQLite, APScheduler, Pydantic.
- **Frontend:** React 18, Vite, TanStack Query, Tailwind, shadcn primitives, Konva (editor), Framer Motion.
- **AI:** MiniMax H3 (cloud), Fal.ai (H3 Max / Kling / ESRGAN), OpenAI, Anthropic.
- **Local models:** Real-ESRGAN (upscale), ComfyUI (image), Whisper (transcription).
- **Desktop:** Tauri 2 + PyInstaller.
- **CI:** GitHub Actions for lint, tests, signed installers.

---

## 📊 Cost summary

Run the whole stack on a single laptop or a $5 VPS.

| Layer | Where | Cost |
|---|---|---|
| VPS | None. Local on your machine. | **$0/mo** |
| Image gen | ComfyUI on RTX 5070 / Flux via Fal.ai | **$0-5/mo** |
| Video (primary) | MiniMax H3 API | **~$10-15/mo** |
| Video (speed) | MiniMax H3 Max via Fal.ai | **~$3-5/mo** |
| Video (hero) | Fal.ai Kling 2.6 Pro | **~$2-3/mo** |
| Voice | ElevenLabs free tier | **$0/mo** |
| CDN | Cloudflare R2 free tier | **$0/mo** |
| Electricity | RTX 5070, ~2 hrs/day | **~$3/mo** |
| **Total** | | **~$18-31/mo** |
| **Upfront** | | **$0** (you own the hardware) |

---

## 📚 Documentation

| You want to... | Read this |
|---|---|
| Use the dashboard | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) |
| Edit a generated image or video | [`docs/REFINEMENT_STUDIO.md`](docs/REFINEMENT_STUDIO.md) |
| Tune prompts with skills | [`docs/SKILLS.md`](docs/SKILLS.md) |
| Build visual pipelines | [`docs/quickstart.md`](docs/quickstart.md) |
| Run multi-agent Studio Pro | [`docs/studio.md`](docs/studio.md) |
| Author extensions | [`docs/RELEASE.md`](docs/RELEASE.md) |
| Self-host on a VPS | [`docs/install.md`](docs/install.md) |
| API reference | [`docs/api.md`](docs/api.md) |
| Phase history | [`docs/PHASE_0.md`](docs/PHASE_0.md) → [`PHASE_5.md`](docs/PHASE_5.md) |
| What's changed | [`CHANGELOG.md`](CHANGELOG.md) |

---

## ✅ Verify

Run the hard gate (everything passes):

```bash
bash verify.sh
```

Run the test suite:

```bash
python3 -m pytest tests/ -v
```

**Status:** 660+ tests passing across 50+ test files. Frontend + backend coverage.

---

## 🤝 Contributing

Calypso is solo-first by design. Every contributor is welcome.

1. Fork the repo.
2. Read [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) to understand the surface.
3. Open an issue describing the change. We use the `tests-first` skill: write the failing test, then the implementation.
4. Make `bash verify.sh` green.
5. PR with a clear "why this matters" line.

---

## 📜 License

[MIT](LICENSE) — do whatever you want, just don't blame us.

Built by [@liam151518](https://github.com/liam151518). Inspired by the operator-first aesthetic of Linear, Vercel, and a refusal to pay monthly fees for software you could run yourself.

---

<div align="center">
  <sub>If Calypso saves you time, consider ⭐ starring the repo. It helps more than coffee.</sub>
</div>