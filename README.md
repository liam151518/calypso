# Calypso

Calypso is an open-source marketing platform. Run it on your laptop, host it on a $5 VPS, or fork it into a SaaS. It does the same thing either way.

Use it to:

- Generate video and image ads with the top AI models
- Run them as visual pipelines (trigger, brand, prompt, model, export)
- Drive a multi-agent Studio that takes a brief and produces a campaign
- Manage contacts, send campaigns, post to social, see analytics
- Extend it with community plugins (models, agents, channels, importers)

MIT licensed. No per-seat fees. No vendor lock-in.

---

## Run the dashboard

```bash
git clone https://github.com/liam151518/calypso.git
cd calypso
bash run.sh
```

Opens <http://localhost:8765>. Override with `CALYPSO_PORT=9000 bash run.sh` if 8765 is taken.

In the browser:

1. **Settings**. Paste your `FAL_API_KEY` (and optionally `MINIMAX_API_KEY`). They go into the local `.env`.
2. **References**. Upload images or clips you want as style anchors. Stored locally.
3. **Generate**. Type a prompt, optionally pick a reference, hit Generate. The job runs in a background thread. The UI polls every 2 seconds. When it's done, the video plays inline.
4. **Outputs**. Gallery of every generated video, with download links.

No npm. No Docker. No cloud. Just Python.

Need to install on a different surface?

- **Desktop app** (Tauri + PyInstaller): `bash scripts/desktop-build.sh`. Produces a `.dmg`, `.exe`, and `.AppImage`.
- **Docker**: `docker compose up`. Ships with Caddy for HTTPS.
- **PyPI**: `pip install calypso` for headless mode.

---

## Where to start

| You want to... | Go here |
|---|---|
| Use the dashboard | this README |
| Build visual pipelines | `docs/pipelines.md` |
| Run the multi-agent Studio | `docs/studio.md` |
| Author extensions | `docs/extensions.md` |
| Self-host on a VPS | `docs/self-host.md` |
| Email deliverability | `docs/deliverability.md` |
| Compliance | `docs/compliance.md` |
| API reference | `docs/api.md` |

---

## CLI usage

If you'd rather not use the browser:

```bash
# Check your keys
python3 scripts/generate.py --check-keys

# Generate a video
python3 scripts/generate.py "damascus cabinet reveal, cinematic, 4K"

# Pick a reference automatically
python3 scripts/generate.py --model h3-max "summer drop teaser"

# Use a specific reference file
python3 scripts/generate.py --reference ~/Downloads/damascus.png "spin the cabinet"
```

The CLI does the same routing as the dashboard. It just doesn't have a UI.

---

## Boundary rules

These are non-negotiable:

- **`../Gacha Luka/` is read-only.** The pipeline pulls brand assets (logos, screenshots) from it but never writes there.
- **`packet/` is yours.** Sub-agents read it but don't edit it.
- **`tests/` are written by Adam only** via the `tests-first` skill. Builders make tests green. They never edit test files.
- **Solo operator.** Everything is built to be runnable by one person, with handoff in mind.

---

## Folder layout

```
Content Pipeline/
├── README.md                      # this file
├── .gitignore
├── run.sh                         # one-command launcher for the Flask UI
├── verify.sh                      # the single hard gate (re-run before merge)
├── packet/                        # YOUR product brief (never touched by builders)
├── plan/                          # plans + ADRs
├── slices/                        # vertical-slice task breakdowns
├── adam/
│   ├── context/                   # calibration: who you are, your prefs, the project
│   └── memory/                    # decisions, handoffs, research dumps
├── agent-control/                 # durable orchestrator state across sessions
├── brand/                         # Gatcha Kingdom identity
├── references/                    # what works (inbox / ready / archived / uploads)
├── workflows/                     # n8n workflow JSON exports
├── comfyui/                       # ComfyUI workflow JSON + H3 native node templates
├── scripts/                       # reference picker, post-process, scrapers, generate.py
├── app/                           # Flask web UI (server.py, templates/, static/)
├── tests/                         # tests-first contracts
├── docs/                          # the runbooks you read
├── desktop/                       # Tauri 2 desktop app source
├── Dockerfile, docker-compose.yml # self-host deployment
└── .github/workflows/             # CI, release, packaging
```

---

## Cost summary (steady state)

| Layer | Where | Cost |
|---|---|---|
| VPS | None. Local on your machine | $0/mo |
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

- [x] Phase 0. Folder structure + Adam install runbook
- [x] Phase 1.1. Brand DNA
- [x] Phase 1.2. Reference vault
- [x] Phase 1.3. Local infra (Docker, ComfyUI, Python, Node)
- [x] Phase 1.4. Accounts (MiniMax, fal.ai, Telegram, Cloudflare, X, Meta, TikTok, ElevenLabs)
- [x] Phase 2. Image pipeline
- [x] Phase 3. Video pipeline (MiniMax H3 primary)
- [x] Phase 4. Optimization (council review, local H3 benchmark, Brand LoRA)
- [x] Phase 5. Scale + handoff prep
- [x] Dashboard UI. Flask + Jinja + HTMX at `app/`, launched by `bash run.sh`
- [x] Phase A. Pipeline builder
- [x] Phase B. Desktop + Docker packaging
- [x] Phase C. Multi-agent Studio
- [x] Phase D. Plugin marketplace
- [x] Phase F. Marketing surface

See `docs/` for the runbooks.

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

Currently 254+ tests pass across 13+ test files.
