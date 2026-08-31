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

## Quick start (in this order)

1. **Read `docs/PHASE_0.md`** — installs Adam + Agent-Reach into Cursor (~30 min)
2. **Read `docs/PHASE_1.md`** — sets up the rest of the foundation (~1 week)
3. From Phase 2 onward, you just talk to Adam in Cursor — it drives everything else

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
├── verify.sh                      # the single hard gate (Adam re-runs before merge)
├── packet/                        # YOUR product brief (you + Adam write it, never touched by builders)
├── plan/                          # Adam's plans + ADRs
├── slices/                        # vertical-slice task breakdowns
├── adam/
│   ├── context/                   # calibration: who you are, your prefs, the project
│   └── memory/                    # decisions, handoffs, research dumps
├── agent-control/                 # durable orchestrator state across sessions
├── brand/                         # Folder B — Gatcha Kingdom identity
├── references/                    # Folder A — what works (inbox / ready / archived)
├── workflows/                     # n8n workflow JSON exports
├── comfyui/                       # ComfyUI workflow JSON + H3 native node templates
├── scripts/                       # reference picker, post-process, scrapers
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
- [x] **UI** — Next.js 14 dashboard at `ui/` (Overview, Phases, Scripts, Brand, Workflows, Tests, Accounts, Adam)

See `/Users/liamsantos/.cursor/plans/gachakingdoms_ad_pipeline_plan_ca486772.plan.md` for the full plan this repo implements.

---

## Local dashboard UI

There's a Next.js 14 dashboard at `ui/` that surfaces the whole project.

```bash
cd ui
npm install                  # one-time (already done if you've run the scaffold)
npm run dev:all              # starts backend (8765) + frontend (3001) together
# or run them separately:
npm run backend              # FastAPI on :8765
npm run dev                  # Next.js on :3001
```

Open <http://localhost:3001>.

Pages:

- **Overview** — counts (tests, scripts, workflows, brand files), gate status
- **Phases** — six-phase rollout status with deliverables per phase
- **Scripts** — every script with `--help` and a click-to-run UI
- **Brand Pack** — Folder B files with live previews
- **Workflows** — n8n + ComfyUI workflows with node/trigger counts
- **Tests** — pytest breakdown by file; one-click "run all tests"
- **Accounts** — required third-party accounts and which env vars are set
- **Adam** — Adam skill install state (user + project level) and context files

The backend (`ui/server/app.py`) wraps every script so the UI can run them, plus the verify gate, plus account/brand/workflow/test inspection.
