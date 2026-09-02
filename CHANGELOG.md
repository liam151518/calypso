# Changelog

All notable changes to Calypso are documented here. Versions follow
[SemVer](https://semver.org/). The format is borrowed from
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- **Refinement Studio** (`/refine/:outputId`) — three-column layout
  with layer isolation, version history, and 2x/4x upscaling.
- **Per-layer regeneration** — re-render any `ai_background`,
  `ai_image`, or `text` layer without touching the rest of the
  composition.
- **Output version history** — every refine action persists a row to
  `output_versions`; promote any version to canonical.
- **Upscaling** — local Real-ESRGAN (when `realesrgan-ncnn-vulkan` is
  installed) or cloud `fal.ai`, with a PIL-based fallback for local
  development.
- **Unified LLM backend** (`app/llm.py`) — pluggable providers
  (OpenAI, Anthropic, MiniMax) with a single `complete()` interface.
  `app/captions.py` now uses the configured provider instead of the
  inline `fal.run/llm` wrapper.
- **Skills system** — four built-in skills (`ugc_video`, `image_ad`,
  `prompt_enhancement`, `caption_optimizer`) injected as `<skill>`
  blocks in every LLM call, with optional `post_process_re` regex
  transforms. Stored in the `user_skills` table + `~/.calypso/skills/`
  markdown files.
- **Skills page** (`/skills`) — toggle, edit, and test skills; preview
  the rendered prompt diff before saving.
- **"Active skills" chip** on the Generate page — shows which skills
  are firing.
- **Code splitting** — heavy routes (`/editor`, `/refine/:id`, `/skills`,
  etc.) are lazy-loaded; Konva, react-query, react-dnd, and motion are
  split into vendor chunks.
- **Settings UI overhaul** — keys now expose `service`, `docs_url`,
  `required`, `description`, and a **Test** button; arbitrary custom
  keys can be managed via the "Add a custom key" section.

### Changed

- `outputs` table now persists `layers_json` and `filter_settings`
  columns (Refinement Studio needs them).
- `outputs.get_output()` deserializes layers + filters on read.
- `app.publisher.dispatch` prioritizes real publishers (Instagram)
  over `DryRunPublisher`.
- `KNOWN_KEYS` now lists every API key the app reads (not just the
  ones used by the legacy Settings form).
- `verify.sh` continues to gate every phase on green backend + frontend
  tests.

### Fixed

- `SpendState` month-rollover regression: hardcoded test month no longer
  triggers an unintended reset.
- `test_e2e_pipeline_smoke` Flask bootstrap fixture so the suite can
  boot the backend on a free port.
- Settings page typo that implied keys required manual `.env` editing.

## [0.1.0] — 2026-08-15

### Added

- Initial public release.
- Brand poster studio: 11 built-in templates, 5 filter presets,
  WYSIWYG editor, product catalog, CSV import, auto-cutout.
- Caption generator (heuristic + LLM).
- Video pipeline: scene stitching, UGC templates, one-shot brief
  generator, OpenCV motion graphics.
- Multi-agent Studio Pro (director → template_selector → copywriter →
  visual_strategist → campaign_builder).
- Presets + automation rules.
- Config import/export.
- HMAC-signed extension marketplace.
- Scheduler with Telegram approvals.
- APScheduler-based scheduler v2.
- PyInstaller + Tauri desktop packaging.
- Docker + Caddy self-hosting.
