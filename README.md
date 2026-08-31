# Gatcha Kingdom Ad Pipeline

Reference-driven ad content engine for **gachakingdoms.com** (the live Gatcha Kingdom site at `../Gacha Luka/`).

This repo is the **orchestration backbone** that drives:
- **Folder A** — competitor / niche reference library (what works)
- **Folder B** — Gatcha Kingdom brand DNA (who we are)
- **Image pipeline** — ComfyUI on the local RTX 5070
- **Video pipeline** — MiniMax H3 (cloud) + fal.ai (speed & hero tiers)
- **Approval gate** — Telegram bot
- **Publisher** — Social Stats to X, Instagram, TikTok

The brain that designs and manages this whole thing is **Adam** (The Adam Repo), installed into Cursor.

---

## Run it locally (the dashboard)

There's a Flask + Jinja + HTMX web UI under `app/`. One command to start it:

```bash
git clone https://github.com/liam151518/calypso.git
cd calypso
bash run.sh
```

Opens <http://localhost:8765>. (Override with `CALYPSO_PORT=9000 bash run.sh` if 8765 is taken.)

What you can do from the browser:

1. **Settings** — paste your `FAL_API_KEY` (and optionally `MINIMAX_API_KEY`). They go into the local `.env`.
2. **References** — upload any images or clips you want as style anchors. Stored locally under `references/uploads/`.
3. **Generate** — type a prompt, optionally pick a reference, hit Generate. The job runs in a background thread; the UI polls every 2 s. When it's done, the video plays inline.
4. **Outputs** — gallery of every generated video, with download links.

No npm. No Docker. No cloud. Just Python.

---

## Quick start (pipeline build, not the dashboard)

If you want to *build out* the pipeline (not just use it):

1. **Read `docs/PHASE_0.md`** — installs Adam + Agent-Reach into Cursor (~30 min)
2. **Read `docs/PHASE_1.md`** — sets up the rest of the foundation (~1 week)
3. From Phase 2 onward, you just talk to Adam in Cursor — it drives everything else

The dashboard (above) is the *runtime* — once the pipeline is built, you use the dashboard to actually generate content.

---

## CLI usage (alternative to the dashboard)

If you'd rather not use the browser:

```bash
# Check your keys
python3 scripts/generate.py --check-keys

# Generate a video
python3 scripts/generate.py "damascus cabinet reveal, cinematic, 4K"

# Pick a reference from Folder A automatically
python3 scripts/generate.py --model h3-max "summer drop teaser"

# Use a specific reference file
python3 scripts/generate.py --reference ~/Downloads/damascus.png "spin the cabinet"
```

The CLI does the same routing as the dashboard — it just doesn't have a UI.

---

## Boundary rules

These are non-negotiable:

- **`../Gacha Luka/` is read-only.** The pipeline pulls brand assets (logos, screenshots) from it but never writes there. All pipeline output lives here, in `Content Pipeline/`.
- **`packet/` is yours.** Adam reads it; sub-agents don't edit it.
- **`tests/` are written by Adam only** via the `tests-first` skill. Builders make tests green; they never edit test files.
- **Solo operator.** Everything is built to be runnable by one person, with handoff in mind (Phase 5).

---

## Folder layout

```
Content Pipeline/
├── README.md                      # this file
├── .gitignore
├── run.sh                         # one-command launcher for the Flask UI
├── verify.sh                      # the single hard gate (Adam re-runs before merge)
├── packet/                        # YOUR product brief (you + Adam write it, never touched by builders)
├── plan/                          # Adam's plans + ADRs
├── slices/                        # vertical-slice task breakdowns
├── adam/
│   ├── context/                   # calibration: who you are, your prefs, the project
│   └── memory/                    # decisions, handoffs, research dumps
├── agent-control/                 # durable orchestrator state across sessions
├── brand/                         # Folder B — Gatcha Kingdom identity
├── references/                    # Folder A — what works (inbox / ready / archived / uploads)
├── workflows/                     # n8n workflow JSON exports
├── comfyui/                       # ComfyUI workflow JSON + H3 native node templates
├── scripts/                       # reference picker, post-process, scrapers, generate.py (CLI)
├── app/                           # Flask web UI (server.py, templates/, static/)
├── tests/                         # tests-first contracts
└── docs/                          # the runbooks you read
```

---

## Cost summary (steady state)

| Layer | Where | Cost |
|---|---|---|
| VPS | None — local on your Windows PC | $0/mo |
| Images | ComfyUI on RTX 5070 | $0/mo |
| Video (primary) | MiniMax H3 API (cloud) | ~$10-15/mo |
| Video (speed) | MiniMax H3 Max via fal.ai | ~$3-5/mo |
| Video (hero) | fal.ai Kling 2.6 Pro | ~$2-3/mo |
| Voice | ElevenLabs free tier (UGC only; H3 generates native audio) | $0/mo |
| CDN | Cloudflare R2 (free tier) | $0/mo |
| Electricity | RTX 5070, ~2 hrs/day | ~$3/mo |
| **Total** | | **~$18-26/mo** |
| **Upfront** | | **$0** (you own the hardware) |

---

## Status

- [x] **Phase 0** — folder structure + Adam install runbook
- [x] **Phase 1.1** — Folder B (brand DNA)
- [x] **Phase 1.2** — Folder A (reference vault)
- [x] **Phase 1.3** — local infra (Docker, ComfyUI, Python, Node)
- [x] **Phase 1.4** — accounts (MiniMax, fal.ai, Telegram, Cloudflare, X, Meta, TikTok, ElevenLabs)
- [x] **Phase 2** — image pipeline
- [x] **Phase 3** — video pipeline (MiniMax H3 primary)
- [x] **Phase 4** — optimization (council review, local H3 benchmark, Brand LoRA)
- [x] **Phase 5** — scale + handoff prep
- [x] **Dashboard UI** — Flask + Jinja + HTMX at `app/`, launched by `bash run.sh`

See `/Users/liamsantos/.cursor/plans/gachakingdoms_ad_pipeline_plan_ca486772.plan.md` for the full plan this repo implements.

---

## Verify

Run the hard gate (everything passes):

```bash
bash verify.sh
```

Run the test suite:

```bash
python3 -m pytest tests/ -v
```

Currently **254 tests pass** across 13 test files.
