# Calypso Dev Log

> Living record of the Calypso project. Read this when picking up an old chat, onboarding a new contributor, or checking where we are.
>
> Last updated: **2026-09-01**
>
> Audience: future-me, new chat sessions, new contributors. Tone: terse, honest, dated.

---

## At a glance

| | |
|---|---|
| **Repo** | github.com/liam151518/calypso |
| **License** | MIT |
| **Vision** | Open-source marketing platform that runs on your laptop, hosts on a $5 VPS, or forks into a SaaS |
| **Status** | **v0.1.0-ready**. All six phases (0-5) and six sub-phases (A-F) complete. Pre-public-release polish. |
| **Stack** | Flask + SQLite (backend), React + Vite + Tailwind + shadcn (SPA), TanStack Query (data), Tauri 2 + PyInstaller (desktop), Docker + Caddy (self-host), fal.ai + MiniMax H3 (models) |
| **Tests** | 510 pytest + 15 vitest passing. 2 pre-existing date-sensitive tests fail. |
| **Cost to run** | ~$18-26/mo (steady state) or $0 if you own the hardware |
| **Primary author** | Liam Santos |

---

## What Calypso is (one paragraph)

Calypso is the open-source answer to Mautic + Flowy + ViMax in one box. It is a single-actor marketing operation tool: generate video and image ads with top AI models, chain them in visual pipelines, drive a multi-agent Studio from a brief, manage contacts and campaigns, post to social, track analytics, and extend it with community plugins. Run it on your laptop with `bash run.sh`, package it as a desktop app, or self-host with Docker. The whole thing is MIT so you can fork it into a SaaS without asking.

## What Calypso is not

- Not a multi-tenant SaaS out of the box. The architecture supports forking per-tenant, but the product is single-operator-first.
- Not a no-code tool. It assumes the operator knows shell, Python, and `.env`.
- Not opinionated about brand voice. Calypso ships defaults; you bring the brand.
- Not a hosted service. There is no `calypso.app`. You run it yourself or fork it.

---

## Vision and the three ancestors

Calypso stands on the shoulders of three tools, and the public docs explain that lineage so contributors and users understand what they're getting:

1. **Mautic** (open-source marketing automation). Calypso borrows the plugin model: every extension declares what it contributes (provider, stage, node, channel, form, importer) via a manifest. The manifest is signed with HMAC-SHA-256 and validated at load.
2. **Flowy** (visual workflow editor). Calypso borrows the canvas pattern for pipelines. Each node is a typed step with a JSON Schema that drives a dynamic form in the SPA.
3. **ViMax** (multi-agent narrative engine). Calypso borrows the agent chain pattern. Director sets tone, Screenwriter drafts scenes, Storyboard picks shots, Reference Selector finds assets, Asset Forge makes new ones, Producer wires it into a pipeline, QC gives it a once-over. Each agent is a small Python class with a shared `AgentContext`.

The product thesis: **all three, in one repo, MIT, runnable by one person.**

## Non-negotiables

These rules shape every decision. They are not aspirations; they are constraints.

- **Single operator, handoff-ready.** The pipeline must be runnable by one person and recoverable from a fresh clone in under 30 minutes.
- **`../Gacha Luka/` is read-only.** The pipeline pulls brand assets from it. It never writes there.
- **`packet/` is the operator's voice.** Sub-agents read it. They do not edit it.
- **`tests/` are written by Adam only.** Builders make tests green. They never edit test files.
- **MIT on the way out.** Every contribution stays MIT. No CLA, no dual-license traps.
- **One repo, one product.** No separate marketing-automation repo, no separate agent repo. Everything ships together.

---

## Current state (as of 2026-09-01)

### What works

- **Reference vault.** Upload images and clips, tag them, mark readiness, archive stale ones. SQLite-backed. Files live on disk, metadata in DB, deduped by SHA-256.
- **Image generation.** fal.ai image models behind a registry with live cost estimates. Top-10 model picker. Dedicated `/image` page with reference picker and live status.
- **Video generation.** MiniMax H3 (cloud) as primary, H3 Max via fal.ai as speed tier, Kling 2.6 Pro via fal.ai as hero tier. Cost-routed by `scripts/generation_router.py` with monthly hard cap and 80% / 95% threshold warnings. Background-thread job tracker with HTMX-polled status.
- **Visual pipelines.** Drag-and-drop canvas (`PipelineCanvas.tsx`, `NodePalette.tsx`, `Inspector.tsx`). JSON Schema-driven node forms. Topological executor. Live cost tracking per node. Persisted in SQLite.
- **Multi-agent Studio.** Chain of 7 agents takes a brief and produces a runnable pipeline with artifacts at each step. Surfaces live logs. Output: `/studio` page with a Run button and an inline expandable "What happens when I click Run?" so the chrome stays short.
- **Plugin marketplace.** Extension loader validates manifests, checksums, and signatures. Two built-in extensions ship: `calypso-logger-channel` (reference channel that prints to stdout) and `calypso-csv-importer` (reference importer for contacts/drafts). `/extensions` page lists installed extensions with reload/disable controls. `docs/marketplace/index.json` is the signed catalog that ships with releases.
- **Marketing surface.** Contacts (with consent + unsubscribe), Campaigns (drafts + scheduling + send), Landing Pages (with public form + submissions), Social Posts (multi-platform dispatch with approval gates), Analytics (lightweight event store), Scheduler (in-process, idle-when-empty), Compliance (GDPR/CCPA helpers).
- **Brand profiles.** One or more named brands, an "active" pointer, brand banner on the Generate page auto-prepends to prompts. Stored in SQLite.
- **Prompt drafts.** Saved prompt library with name + body + tags. Pull-up into the composer.
- **Approval gate.** Telegram bot integration: every generated post sends a Telegram message with Approve/Regenerate/Skip inline buttons. Approved items hit the dispatcher.
- **Desktop packaging.** Tauri 2 shell + PyInstaller sidecar (Python backend bundled into a single executable). `scripts/desktop-build.sh` produces `.dmg`, `.exe`, and `.AppImage`.
- **Docker self-host.** `docker-compose.yml` runs Flask behind Caddy with auto-HTTPS. `scripts/self-host.sh` is the one-shot bootstrap for a fresh VPS.
- **SPA + API.** React + Vite + Tailwind + shadcn SPA at `web/`. Flask API at `app/server.py`. TanStack Query manages data. Same-shape routes serve both SPA JSON and the legacy Jinja pages.
- **Release pipeline.** `verify.sh` is the hard gate (folder structure, brand pack, tests, env, infra, packaging). `.github/workflows/release.yml` runs pytest + vitest + builds the SPA + builds the Tauri installers + signs extensions + publishes the marketplace catalog.
- **Design system.** Single-token dark theme (`DESIGN.md`). Inter for chrome, JetBrains Mono for code/data. Signal-orange `#ff6a1f` as the only accent. No display fonts, no gradient text, no colored border-left stripes. `web/src/index.css` and `app/static/app.css` carry the same variables.

### What is partial

- **QC agent** uses a VLM that is optional and only runs if configured. Most operators skip it.
- **Auto-reply bot** is scaffolded in scripts but not wired into a live dispatcher yet (depends on a Social Stats integration that lives in a separate sibling repo).
- **TikTok publishing** needs a separate OAuth flow that is documented but not enabled by default.

### What is not started

- **Paid ads integrations** (Meta Ads, X Ads). Out of scope for v1; the agent surface leaves room for them but no code exists.
- **Localization.** Captions are English-only. The chain produces the language the prompt asks for.
- **Multi-account posting.** Single-account per platform for v1.

### Known issues

- Two pre-existing date-sensitive tests fail because `SpendState` resets the spend month on calendar roll-over. Verified to fail on pristine `main` before any v1 copy work. Tracked in `tests/test_video_clients.py` and `tests/test_video_pipeline.py`. Fix is to inject the clock into `SpendState`; will land in v0.1.1.
- One pre-existing ESLint warning in `web/src/pages/Pipeline.tsx` about a missing `useEffect` dependency. Verified pre-existing. Will land in v0.1.1.

---

## Architecture map (where to look)

```
Content Pipeline/
|-- app/                          Flask + SPA host + JSON API
|   |-- server.py                 Flask app factory + route registration
|   |-- models.py                 fal.ai model registry + cost estimator
|   |-- jobs.py                   video generation job tracker (background thread)
|   |-- image_jobs.py             image generation job tracker
|   |-- brand.py                  brand profiles + active brand pointer
|   |-- drafts.py                 prompt draft library
|   |-- refs.py                   reference library (files on disk + tags in SQLite)
|   |-- db.py                     SQLite layer (one schema, all tables)
|   |-- settings.py               .env reader/writer
|   |-- node_schema.py            JSON Schema for every pipeline node type
|   |-- pipelines.py              pipeline registry + topological executor
|   |-- pipeline_nodes.py         concrete node runners
|   |-- agents/                   multi-agent Studio
|   |   |-- base.py               shared AgentContext + logging hooks
|   |   |-- director.py           brief -> treatment
|   |   |-- screenwriter.py       treatment -> scene list (regex parser)
|   |   |-- storyboard.py         scene list -> shot list
|   |   |-- reference_selector.py pick matching refs from the library
|   |   |-- asset_forge.py        mint brand-new refs from the brief
|   |   |-- producer.py           topological scheduler
|   |   `-- qc.py                 optional VLM-based best-of-k
|   |-- extensions/               plugin marketplace (Phase D)
|   |   |-- manifest.py           ExtensionManifest dataclass + JSON Schema
|   |   |-- loader.py             discover + validate + activate
|   |   |-- hooks.py              typed hook names
|   |   |-- signing.py            HMAC-SHA-256 signing CLI helpers
|   |   `-- builtin/              two reference extensions
|   `-- marketing/                marketing surface (Phase F)
|       |-- contacts.py           consent + unsubscribe
|       |-- campaigns.py          drafts + scheduling + send
|       |-- pages.py              landing pages + submissions
|       |-- social.py             multi-platform social posts
|       |-- analytics.py          lightweight event store
|       |-- scheduler.py          in-process idle-when-empty scheduler
|       `-- compliance.py         GDPR/CCPA helpers
|-- web/                          React SPA
|   |-- src/
|   |   |-- pages/                Generate, Image, Pipeline, PipelineList, Studio, Extensions, Outputs, Marketing, Settings
|   |   |-- components/
|   |   |   |-- domain/           BrandBanner, PromptComposer, ModelPicker, JobCard, ImageJobCard, ...
|   |   |   |-- pipeline/         PipelineCanvas, NodePalette, Inspector (drag-and-drop builder)
|   |   |   `-- layout/           AppShell
|   |   `-- lib/                  api.ts (typed API client), query.ts (TanStack Query hooks), types.ts, utils.ts
|   `-- index.html                SPA shell
|-- scripts/                       CLI tools (single-command entry points)
|   |-- generate.py               the unified generator CLI
|   |-- generation_router.py      backend chooser + cost cap
|   |-- falai_client.py           fal.ai client wrapper
|   |-- h3_client.py              MiniMax H3 client wrapper
|   |-- prompt_builder.py         prompt assembly + caption templating
|   |-- desktop-build.sh          builds PyInstaller sidecar + Tauri installers
|   |-- self-host.sh              bootstraps a fresh VPS
|   `-- validate_accounts.py      checks that all API keys are present
|-- tests/                         tests-first contracts (Adam writes, builders make green)
|-- docs/                          user-facing runbooks
|   |-- PHASE_0.md to PHASE_5.md  historical phase briefs
|   |-- accounts.md               required accounts per tier
|   |-- brand-lora-training.md    LoRA training runbook
|   |-- RELEASE.md                release process
|   `-- marketplace/              public extension catalog (index.html + index.json)
|-- desktop/                       Tauri 2 source (Rust + WebView)
|-- comfyui/                       ComfyUI workflow JSON + H3 native node templates
|-- workflows/                     n8n workflow JSON exports
|-- brand/                         brand pack (logo variants, screenshots, voice, guidelines, captions)
|-- references/                    seeded brand-A references (the "what works" vault)
|-- packet/                        the operator's product brief (sub-agents read but do not edit)
|-- plan/                          plans + ADRs
|-- slices/                        vertical-slice task breakdowns
|-- adam/                          Adam calibration + memory
|-- agent-control/                 durable orchestrator state across sessions
|-- app/agents/, app/marketing/,  see "Architecture map" above
|-- .github/workflows/
|   `-- release.yml               CI: pytest + vitest + spa build + tauri build + release
|-- Caddyfile                      reverse proxy with auto-HTTPS
|-- Dockerfile                     single-image Python backend + built SPA
|-- docker-compose.yml            Calypso + Caddy + volumes
|-- run.sh                         one-command launcher (venv + deps + SPA build + run)
|-- verify.sh                      the single hard gate (run before any merge)
|-- README.md                      product README (the public face)
|-- DEV_LOG.md                     this file (project state + history for new chats)
|-- LICENSE                        MIT
`-- .env.example                   every env var, grouped by tier
```

---

## Phase history

This section is append-only. Every entry is dated. Entries describe **what shipped**, not what was planned. Read older entries to recover reasoning.

### 2026-08-31

- **Initial commit.** `4e75ae1`. Gachakingdoms Reference-Driven Ad Pipeline. Repo started as a single-purpose tool for the Gatcha Kingdom storefront. All brand content (logo, voice, captions, screenshots, references) is Gatcha Kingdom-specific. The product name and product brief have since generalized to "Calypso" while the brand content keeps the original look.

### 2026-08-31 (later)

- **`9daa707`. Replace Next.js UI with local-first Flask dashboard.** The first version shipped with a Next.js SPA. Replaced with a Flask + Jinja + HTMX UI to drop the Node dependency and keep the single-operator constraint.
- **`a5376a0`. Overhaul Flask UI with producer's console design and fix generate flow.** The producer's console design (dark, signal-orange, single accent) is the ancestor of the current design system. The generate flow was the first end-to-end path through the system.
- **`9d7bf55`. Add start_server.sh launcher for persistent execution.** Background-launcher for the demo PC. Replaced by the global `run.sh`.

### 2026-08-31 (later still)

- **`5e05a19`. Reset UI to operator-console (Operate mode); add SQLite backend.** The big pivot. SQLite becomes the source of truth for brand profiles, drafts, references, jobs, tags. The Flask UI goes full operator-console. Inter replaces any display font. Signal-orange becomes the only accent. `DESIGN.md` is born here.
- **`2f7e212`. Add React + Tailwind + shadcn SPA over existing Flask API.** Adds the modern SPA without throwing away the Flask API. Both surfaces serve the same data. The SPA becomes the primary face.
- **`2f83e97`. Add top-10 fal.ai model selector, live cost estimates, and dedicated Image page.** The breadth-first moment. Image generation gets its own first-class page. The cost estimator surfaces per-model prices live in the picker.

### 2026-09-01

- **Phases A-F complete.** Pipeline builder (A), Desktop + Docker packaging (B), Multi-agent Studio (C), Plugin marketplace (D), Public release prep (E), Marketing surface (F). All land in this window. The repo's feature set matches the vision doc.
- **Cleanup pass.** All user-visible copy rewritten using copywrite principles: simple over complex, specific over vague, active over passive, confident over qualified. Em dashes removed from UI strings and replaced with periods, colons, or rewrites. Inline `<details>` expand-for-depth blocks added on `PipelineList`, `Studio`, and `Marketing` so the chrome stays short. Runbook section headings (## Step N - Title) keep their em dashes; that is a Markdown convention, not AI prose.
- **Dev log added.** This file. Pushed to the repo so anyone who clones has the same project context a fresh chat session gets.

---

## Open work (next 4 weeks)

Ordered by impact. Items roll forward into new phase briefs (Phase 6+) when they accumulate.

1. **`SpendState` clock injection.** v0.1.1. The two failing tests lose their date sensitivity, all tests pass green.
2. **`PipelineCanvas` useEffect dependency.** v0.1.1. Trivial. Just trim the lint warning.
3. **Tag-batch actions.** Selecting N tags and re-tagging in one move. 1 day.
4. **Auto-reply dispatcher.** Wire the Social Stats incoming webhook to the auto-reply classifier and the Telegram approval gate. ~1 week. Depends on a sibling repo for the unified inbox.
5. **Quorum on extension activations.** Allow operators to require N of M extensions to be present before a run starts. Belongs in the loader.
6. **Browser-side image diff.** Right-click a reference, see a 1-pixel swipe against the active generation. Cheap, high-trust.
7. **Per-extension audit log.** Every hook call logged with source + signed timestamp. Helps with compliance and debugging.

## Parked ideas (do not start without a fresh phase brief)

- **Paid ads integrations.** Out of scope. If anyone proposes it, write a packet first.
- **Multi-tenant SaaS mode.** The architecture supports it but the SQLite + file-on-disk story does not. Will need Postgres + object storage. Phased rewrite.
- **Localization.** Right now only English captions ship. Add a `lang` field to `reference_captions.json` when needed.
- **Live pricing from providers.** Currently we maintain the price table in `app/models.py`. A model that hits each provider's API nightly would be better, but maintenance is non-trivial.

---

## Conventions and gotchas

These are the things the README does not say but every contributor trips over.

- **The brand is Gatcha Kingdom.** The product is Calypso. Brand content (logo, voice, captions, references) stays Gatcha Kingdom until someone forks the brand. Do not conflate the two.
- **One Python venv, one node_modules.** `run.sh` creates both. Do not invent a second venv.
- **Em dashes are banned in user-facing copy.** Not a hard rule but a strong convention. They are kept in regex patterns, JSON values that tests assert against, and Markdown heading separators.
- **Tests are Adam's.** Builders do not edit `tests/`. If a test is wrong, file a finding and let the orchestrator decide.
- **`verify.sh` is the gate.** Before any PR-equivalent action, run `bash verify.sh`. It is the single source of truth for "done".
- **`GACHA_LUKA` boundary.** Never write to `../Gacha Luka/`. The pipeline reads from it.
- **The `app/agents/__init__.py` orchestrates the run order.** When you add an agent, you must add it to that list or the studio will silently skip it.
- **The marketplace catalog is signed.** `docs/marketplace/index.json` carries a signature. Re-publishing requires `python -m app.extensions.signing sign` before commit, or the GitHub release will reject it.

---

## How to use this log

- **Picking up an old chat.** Read "Current state" first. Skim the open work list. Then start from the section that matches what the user asks.
- **Onboarding a contributor.** Read "Vision and the three ancestors" then "Architecture map" then "Conventions and gotchas". The phase history is reference.
- **Recovering from a mistake.** Phase history is append-only. If you broke something, find the last working phase entry and start from there.
- **Planning the next phase.** The "Open work" list is the seed. Promote items into a new `slices/NNN-topic/plan.md` and let `dispatch-builder` turn it into a vertical slice.

---

## Maintenance

This log is updated when:

- A phase ships (add a phase entry).
- A new open-work item is identified (add to the list).
- The architecture changes shape (update the map).
- A new convention is set (add to the list).
- A new gotcha is discovered (add to the list).

When the log gets too long, move the phase history into `docs/PHASE_6.md`, `docs/PHASE_7.md`, etc. Keep this file focused on the current state and the open work. The phase briefs stay separate.

Last verified: 2026-09-01.
