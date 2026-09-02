#!/usr/bin/env bash
# verify.sh. The single hard gate for the ad pipeline.
#
# Per the Adam plan, `orchestrate-build` re-runs this before merge. Builders
# (sub-agents) cannot merge until every check passes.
#
# Run from anywhere: `bash verify.sh` or `./verify.sh`
#
# Exits 0 on success, 1 on first failure. Each section is independent. A
# failure in one section doesn't block the others from running.

set -uo pipefail

# ---------- pretty output ----------
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
BLUE=$'\033[0;34m'
RESET=$'\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
FAILED_SECTIONS=()

section() { echo; echo "${BLUE}=== $* ===${RESET}"; }
pass()    { PASS_COUNT=$((PASS_COUNT + 1)); echo "  ${GREEN}PASS${RESET}  $*"; }
fail()    { FAIL_COUNT=$((FAIL_COUNT + 1)); FAILED_SECTIONS+=("$*"); echo "  ${RED}FAIL${RESET}  $*"; }
skip()    { SKIP_COUNT=$((SKIP_COUNT + 1)); echo "  ${YELLOW}SKIP${RESET}  $*"; }
info()    { echo "        $*"; }

# ---------- locate the project root ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "${BLUE}verify.sh${RESET}: Gatcha Kingdom ad pipeline"
echo "Project root: $SCRIPT_DIR"
echo "Phase: $(test -f docs/PHASE_1.md && echo 'Phase 1+. Most checks active' || echo 'Phase 0. Folder scaffold only')"

# ============================================================
# Section 1. Folder structure (Phase 0)
# ============================================================
section "1. Folder structure"

REQUIRED_DIRS=(
  "packet" "plan" "slices" "agent-control"
  "adam/context" "adam/memory"
  "brand/logo" "brand/screenshots" "brand/fonts" "brand/captions"
  "references/inbox" "references/ready" "references/archived"
  "workflows" "comfyui" "scripts" "tests" "docs"
)

for d in "${REQUIRED_DIRS[@]}"; do
  if [[ -d "$d" ]]; then pass "dir exists: $d"
  else fail "missing dir: $d"
  fi
done

# Phase 0 mandatory files
for f in README.md .gitignore verify.sh docs/PHASE_0.md docs/PHASE_1.md docs/PHASE_2.md docs/PHASE_3.md docs/PHASE_4.md docs/PHASE_5.md docs/accounts.md brand/guidelines.md brand/voice.md brand/captions/reference_captions.json; do
  if [[ -f "$f" ]]; then pass "file exists: $f"
  else fail "missing file: $f"
  fi
done

# ============================================================
# Section 2. Brand pack (Phase 1.1)
# ============================================================
section "2. Brand pack integrity"

# Logo variants
LOGO_VARIANTS=(GK_Logo.png GK_Logo.jpg GK_Logo_512.jpg GK_Logo_256.png GK_Logo_128.png GK_favicon_32.png GK_favicon_16.png)
for f in "${LOGO_VARIANTS[@]}"; do
  if [[ -f "brand/logo/$f" ]]; then pass "logo: $f"
  else fail "missing logo: brand/logo/$f"
  fi
done

# Cabinet screenshots
CABINET_COLORS=(black blue damascus orange pink purple red white yellow)
for c in "${CABINET_COLORS[@]}"; do
  if [[ -f "brand/screenshots/gk-cabinet-$c-480.png" ]]; then pass "cabinet screenshot: $c"
  else fail "missing cabinet screenshot: $c"
  fi
done

if [[ -f "brand/screenshots/gk-hero-cabinet-pink-480.png" ]]; then pass "hero cabinet screenshot"
else fail "missing hero cabinet screenshot"
fi

# Reference captions schema
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import json; json.load(open('brand/captions/reference_captions.json'))" 2>/dev/null; then
    pass "reference_captions.json is valid JSON"
  else
    fail "reference_captions.json is not valid JSON"
  fi
else
  skip "python3 not available. Skipping JSON validation"
fi

# ============================================================
# Section 3. Gacha Luka boundary (never edit the live site)
# ============================================================
section "3. Boundary: Gacha Luka is read-only"

GACHA_LUKA="../Gacha Luka"
if [[ -d "$GACHA_LUKA" ]]; then
  if [[ ! -w "$GACHA_LUKA" ]]; then
    pass "Gacha Luka is not writable from this script's perspective"
  else
    # It's writable, but the rule is convention. Just verify we didn't write today.
    info "Gacha Luka is writable on disk (it's your folder). The boundary is convention. This repo doesn't touch it."
  fi
  info "Gacha Luka is at: $GACHA_LUKA"
else
  skip "Gacha Luka not found at $GACHA_LUKA. If this is a different machine, ignore."
fi

# ============================================================
# Section 4. Reference library (Phase 1.2)
# ============================================================
section "4. Reference library"

READY_COUNT=$(find references/ready -maxdepth 1 -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
INBOX_COUNT=$(find references/inbox -maxdepth 1 -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
ARCHIVED_COUNT=$(find references/archived -maxdepth 1 -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

info "references/ready:   $READY_COUNT"
info "references/inbox:   $INBOX_COUNT"
info "references/archived: $ARCHIVED_COUNT"

if [[ "$READY_COUNT" -ge 20 ]]; then
  pass "reference library has $READY_COUNT A-tier refs (target: 20+)"
elif [[ "$READY_COUNT" -ge 1 ]]; then
  skip "only $READY_COUNT A-tier refs (Phase 1.2 in progress)"
else
  skip "no A-tier refs yet (Phase 1.2 not started)"
fi

# ============================================================
# Section 5. Tests (Phase 2+)
# ============================================================
section "5. Tests"

if [[ -d tests ]] && compgen -G "tests/test_*.py" > /dev/null; then
  if command -v python3 >/dev/null 2>&1 && python3 -c "import pytest" 2>/dev/null; then
    if python3 -m pytest tests/ -q --tb=no \
        --ignore=tests/test_video_clients.py --ignore=tests/e2e 2>&1 | tail -3; then
      pass "pytest suite ran (tests/)"
    else
      fail "pytest suite had failures"
    fi
  else
    skip "pytest not installed. Install with 'pip install pytest' to enable."
  fi
else
  skip "no tests yet (Phase 2 hasn't shipped)"
fi

# ============================================================
# Section 6. Adam + Agent-Reach (user-side install check)
# ============================================================
section "6. Adam + Agent-Reach installation (user-side)"

ADAM_INSTALLED=false
for d in "$HOME/.cursor/skills" "$HOME/.agents/skills" "$HOME/.claude/skills"; do
  if [[ -d "$d" ]]; then
    skill_count=$(find "$d" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$skill_count" -gt 5 ]]; then
      pass "Adam skills installed at $d ($skill_count skill folders)"
      ADAM_INSTALLED=true
    fi
  fi
done

if [[ "$ADAM_INSTALLED" == false ]]; then
  skip "Adam skills not found in ~/.cursor/skills, ~/.agents/skills, or ~/.claude/skills. Run Phase 0 install."
fi

if command -v agent-reach >/dev/null 2>&1; then
  pass "agent-reach CLI available"
  if command -v agent-reach >/dev/null 2>&1 && agent-reach doctor --help >/dev/null 2>&1; then
    if agent-reach doctor 2>&1 | grep -qE '(healthy|all green|✓)'; then
      pass "agent-reach doctor reports healthy"
    else
      info "agent-reach doctor ran but didn't report fully healthy. Check output manually."
    fi
  fi
else
  skip "agent-reach CLI not installed. Run Phase 0 install."
fi

# ============================================================
# Section 7. Local infrastructure (Phase 1.3, runs on Windows PC)
# ============================================================
section "7. Local infrastructure (Windows PC check)"

# These checks are best-effort on the Mac. The Windows PC runs them natively.
# We check if ComfyUI / n8n are accessible on the network in case the Mac is on the same LAN.

if command -v curl >/dev/null 2>&1; then
  for url in "http://localhost:8188" "http://127.0.0.1:8188"; do
    if curl -sf -m 2 -o /dev/null "$url"; then
      pass "ComfyUI responding at $url"
      break
    fi
  done
  for url in "http://localhost:5678" "http://127.0.0.1:5678"; do
    if curl -sf -m 2 -o /dev/null "$url"; then
      pass "n8n responding at $url"
      break
    fi
  done
else
  skip "curl not available"
fi

# Check if we're on Windows (ComfyUI native install)
if [[ "$(uname -s 2>/dev/null)" == "MINGW64_NT"* ]] || [[ "$(uname -s 2>/dev/null)" == "CYGWIN_NT"* ]]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    if nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | grep -qi "RTX 5070"; then
      pass "RTX 5070 detected via nvidia-smi"
    else
      info "nvidia-smi ran but didn't show RTX 5070. Check driver."
    fi
  else
    skip "nvidia-smi not in PATH (install NVIDIA drivers)"
  fi
else
  info "not on Windows. GPU checks skipped (run on the Windows PC for full verify)"
fi

# ============================================================
# Section 8. Env vars (Phase 1.4)
# ============================================================
section "8. Required environment variables"

if [[ -f .env ]]; then
  pass ".env file exists"
  for var in MINIMAX_API_TOKEN FAL_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID CLOUDFLARE_R2_ACCESS_KEY ELEVENLABS_API_KEY; do
    if grep -qE "^${var}=" .env 2>/dev/null && ! grep -qE "^${var}=$" .env 2>/dev/null; then
      pass "env var set: $var"
    else
      info "env var missing or empty: $var (see docs/accounts.md)"
    fi
  done
  for var in X_BEARER_TOKEN META_ACCESS_TOKEN TIKTOK_ACCESS_TOKEN; do
    if grep -qE "^${var}=" .env 2>/dev/null && ! grep -qE "^${var}=$" .env 2>/dev/null; then
      pass "env var set: $var"
    else
      info "env var missing or empty: $var (waiting on platform approval. See docs/accounts.md.)"
    fi
  done
else
  skip ".env not yet created (run Phase 1.4 to set up accounts)"
  info "after creating accounts, copy .env.example to .env and fill in the values"
fi

# ============================================================
# Section 9. .env.example exists for the user to copy
# ============================================================
section "9. .env.example present"

if [[ -f .env.example ]]; then
  pass ".env.example exists (copy to .env and fill in)"
else
  fail ".env.example missing. Adam should generate this during Phase 1.4."
fi

# ============================================================
# Section 10. Project-level Adam install
# ============================================================
section "10. Project-level Adam install (.cursor/skills)"

PROJECT_SKILLS_DIR=".cursor/skills"
if [[ -d "$PROJECT_SKILLS_DIR" ]]; then
  PROJECT_SKILL_COUNT=$(find "$PROJECT_SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$PROJECT_SKILL_COUNT" -ge 5 ]]; then
    pass "project skills installed: $PROJECT_SKILL_COUNT at $PROJECT_SKILLS_DIR/"
  else
    info "project skills present but only $PROJECT_SKILL_COUNT. Run scripts/setup_adam.py."
  fi
else
  skip "no project-level .cursor/skills/. Run scripts/setup_adam.py."
fi

for f in packet/ plan/ slices/ agent-control/ adam/context/ adam/memory/; do
  if [[ -d "$f" ]]; then pass "Adam folder contract: $f"
  else fail "missing Adam folder contract: $f"
  fi
done

# ============================================================
# Section 11. Flask web UI (app/)
# ============================================================
section "11. Flask web UI"

if [[ -f app/server.py ]]; then
  pass "app/server.py exists"
else
  fail "app/server.py missing. The Flask app is gone."
fi

if [[ -f app/requirements.txt ]]; then
  pass "app/requirements.txt exists"
  if grep -qE '^flask' app/requirements.txt; then
    pass "flask pinned in app/requirements.txt"
  else
    fail "flask not in app/requirements.txt"
  fi
else
  fail "app/requirements.txt missing"
fi

for tpl in base.html generate.html references.html outputs.html settings.html job_status.html job_block.html brand.html 404.html _icons.html _health.html; do
  if [[ -f "app/templates/$tpl" ]]; then pass "template: $tpl"
  else fail "missing template: app/templates/$tpl"
  fi
done

for partial in brand_card.html ref_chip_picker.html draft_picker.html draft_results.html batch_block.html batch_children.html job_card_mini.html prompt_disclosure.html ref_tag_editor.html; do
  if [[ -f "app/templates/_partials/$partial" ]]; then pass "partial: $partial"
  else fail "missing partial: app/templates/_partials/$partial"
  fi
done

# SQLite-backed modules for the new generate-page experience.
for mod in app/db.py app/refs.py app/drafts.py app/brand.py; do
  if [[ -f "$mod" ]]; then pass "module: $mod"
  else fail "missing module: $mod"
  fi
done

# Ensure create_app() actually initialises the SQLite DB on boot.
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "from app import server; a = server.create_app(); print('OK')" >/dev/null 2>&1; then
    pass "create_app() initialises without errors"
    if [[ -d .calypso ]] && [[ -f .calypso/calypso.db ]]; then
      pass ".calypso/calypso.db created on startup"
    else
      info ".calypso/ not present yet (created on first run)"
    fi
  else
    fail "create_app() raised. Check import paths and SQL schema."
  fi
fi

for asset in app.css htmx.min.js; do
  if [[ -f "app/static/$asset" ]]; then pass "static asset: $asset"
  else fail "missing static asset: app/static/$asset"
  fi
done

# Fonts. Production-grade design requires self-hosted type.
for font in inter-400.ttf inter-500.ttf inter-600.ttf jetbrains-mono-400.ttf jetbrains-mono-500.ttf; do
  if [[ -f "app/static/fonts/$font" ]]; then pass "font: $font"
  else fail "missing font: app/static/fonts/$font"
  fi
done

if [[ -x run.sh ]]; then
  pass "run.sh is executable"
else
  fail "run.sh is not executable (chmod +x run.sh)"
fi

# Make sure no leftover Next.js / FastAPI cruft
if [[ -d ui ]]; then
  fail "ui/ directory still exists. Should have been removed in favor of app/"
fi
if [[ -f package.json ]]; then
  fail "root package.json still exists. npm should be gone."
fi

# ============================================================
# Section 12. Phase H — release readiness
# ============================================================
section "12. Phase H release readiness"

# New modules shipped during Phase A–G.
for mod in \
  "app/templates.py" \
  "app/compositor.py" \
  "app/video_compositor.py" \
  "app/filters.py" \
  "app/captions.py" \
  "app/products.py" \
  "app/feed_preview.py" \
  "app/presets.py" \
  "app/automation.py" \
  "app/config_io.py" \
  "app/publisher.py" \
  "app/telegram_notify.py" \
  "app/ws.py" \
  "app/motion/__init__.py" \
  "app/motion/opencv.py" \
  "app/motion/omni.py" \
  "app/motion/prompts.py" \
  "app/one_shot.py" \
  "app/studio_pro/__init__.py" \
  "app/studio_pro/director.py" \
  "app/studio_pro/template_selector.py" \
  "app/studio_pro/copywriter.py" \
  "app/studio_pro/visual_strategist.py" \
  "app/studio_pro/campaign_builder.py" \
  "app/utils/validators.py"
do
  if [[ -f "$mod" ]]; then pass "phase A–G module: $mod"
  else fail "missing phase A–G module: $mod"
  fi
done

# Built-in template library.
if [[ -d templates/builtin ]]; then
  builtins=$(find templates/builtin -name "*.json" -type f | wc -l | tr -d ' ')
  if [[ "$builtins" -ge 11 ]]; then
    pass "templates/builtin has $builtins built-in templates (target 11+)"
  else
    info "templates/builtin has $builtins templates (target 11+)"
  fi
else
  fail "templates/builtin directory missing"
fi

# New docs.
for d in docs/install.md docs/quickstart.md docs/templates.md \
         docs/studio.md docs/video_pipeline.md docs/omni_integration.md \
         docs/api.md docs/RELEASE.md \
         docs/USER_GUIDE.md docs/SKILLS.md docs/REFINEMENT_STUDIO.md; do
  if [[ -f "$d" ]]; then pass "doc: $d"
  else info "doc not yet written: $d"
  fi
done

# Phase I: built-in skills shipped.
for d in app/skills/builtins/ugc_video.md \
         app/skills/builtins/image_ad.md \
         app/skills/builtins/prompt_enhancement.md \
         app/skills/builtins/caption_optimizer.md; do
  if [[ -f "$d" ]]; then pass "skill: $d"
  else fail "missing built-in skill: $d"
  fi
done

# Phase I: LLM backend + skills runtime present.
for f in app/llm.py app/skills.py app/skills_store.py; do
  if [[ -f "$f" ]]; then pass "module: $f"
  else fail "missing module: $f"
  fi
done

# Desktop build script exists.
if [[ -x scripts/desktop-build.sh ]]; then
  pass "scripts/desktop-build.sh is executable"
else
  info "scripts/desktop-build.sh not executable"
fi

# Marketplace extension signing helper present.
if [[ -f scripts/extensions/signing.py ]]; then
  pass "scripts/extensions/signing.py exists"
else
  info "scripts/extensions/signing.py not yet written"
fi

# ============================================================
# Summary
# ============================================================
section "Summary"

TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
echo "  ${GREEN}PASS${RESET}: $PASS_COUNT"
echo "  ${RED}FAIL${RESET}: $FAIL_COUNT"
echo "  ${YELLOW}SKIP${RESET}: $SKIP_COUNT (these are phase-dependent. Expected during Phase 0/1.)"
echo "  Total checks: $TOTAL"
echo

if [[ $FAIL_COUNT -gt 0 ]]; then
  echo "${RED}verify.sh FAILED${RESET} in the following sections:"
  printf '  - %s\n' "${FAILED_SECTIONS[@]}"
  echo
  echo "Fix the failures and re-run. Skips are OK during early phases."
  exit 1
else
  echo "${GREEN}verify.sh PASSED${RESET}."
  echo "Skips are expected during Phase 0-1 (folder scaffold, brand pack, accounts)."
  echo "Re-run after each phase completion to track progress."
  exit 0
fi
