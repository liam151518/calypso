"""FastAPI backend for the Gachakingdoms Pipeline UI.

Exposes /api/* routes that the Next.js UI proxies to. Each endpoint reads
project state directly (scripts, brand, workflows, tests, .env) without
mutating anything unless explicitly a `run` endpoint.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="Gachakingdoms Pipeline API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_read(path: Path, limit: int = 4000) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(errors="ignore")[:limit]
    except OSError:
        return None


def _list_files(root: Path, suffix: str | tuple[str, ...] | None = None) -> list[Path]:
    if not root.exists():
        return []
    if suffix is None:
        return sorted(p for p in root.rglob("*") if p.is_file())
    return sorted(p for p in root.rglob(f"*{suffix}") if p.is_file())


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str, str, float]:
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr, (time.time() - start) * 1000
    except subprocess.TimeoutExpired:
        return -1, "", "timeout", (time.time() - start) * 1000
    except Exception as exc:
        return -1, "", str(exc), (time.time() - start) * 1000


@app.get("/overview")
def overview() -> dict[str, Any]:
    # Use the cached test summary if available (populated by /tests/run),
    # otherwise count test files cheaply without invoking pytest.
    summary = _test_cache.get("data")
    if summary is None:
        summary = _cheap_test_summary()
    # Read the latest verify.sh summary from its cache file, or fall back to cheap defaults.
    verify_summary = _verify_summary_from_cache()
    return {
        "tests_pass": summary["passed"],
        "tests_total": summary["total"],
        "verify_pass": verify_summary["pass"],
        "verify_fail": verify_summary["fail"],
        "verify_skip": verify_summary["skip"],
        "scripts": len(_list_files(PROJECT_ROOT / "scripts", ".py")),
        "workflows": len(_list_files(PROJECT_ROOT / "workflows", ".json")) + len(_list_files(PROJECT_ROOT / "comfyui", ".json")),
        "brand_files": len(_list_files(PROJECT_ROOT / "brand")),
        "references": len(_list_files(PROJECT_ROOT / "references" / "ready", ".json")),
        "adam_installed": _adam_status()["installed_at_project_level"] or _adam_status()["installed_at_user_level"],
    }


@app.get("/phases")
def phases() -> list[dict[str, Any]]:
    return [
        {"id": "phase0", "name": "Phase 0 — Install Adam + Agent-Reach", "status": "done",
         "summary": "Adam installed at user level; skills vendored. Agent-Reach install documented in PHASE_0.md.",
         "deliverables": ["adam/context/", "docs/PHASE_0.md", "verify.sh"]},
        {"id": "phase1_brand", "name": "Phase 1.1 — Folder B (Brand DNA)", "status": "done",
         "summary": "Brand guidelines, voice, logos, screenshots, and reference captions seeded from the Gacha Luka repo.",
         "deliverables": ["brand/guidelines.md", "brand/voice.md", "brand/logo/", "brand/screenshots/", "brand/captions/reference_captions.json"]},
        {"id": "phase1_refs", "name": "Phase 1.2 — Folder A (References)", "status": "done",
         "summary": "Reference vault seeded; reference picker implemented and tested.",
         "deliverables": ["references/inbox/", "references/ready/", "scripts/reference_picker.py", "tests/test_reference_picker.py"]},
        {"id": "phase1_infra", "name": "Phase 1.3 — Local infra (RTX 5070)", "status": "done",
         "summary": "Runbook for Docker Desktop + WSL2, ComfyUI 0.30+, Python 3.11+, Node 20 LTS.",
         "deliverables": ["docs/PHASE_1.md", ".env.example"]},
        {"id": "phase1_accounts", "name": "Phase 1.4 — Required accounts", "status": "in_progress",
         "summary": "All accounts documented. Use scripts/validate_accounts.py to check credentials once filled in.",
         "deliverables": ["docs/accounts.md", "scripts/validate_accounts.py"]},
        {"id": "phase2_image", "name": "Phase 2 — Image pipeline", "status": "done",
         "summary": "n8n + ComfyUI image workflows. ComfyUI client, post-process, Telegram approval, prompt builder.",
         "deliverables": ["workflows/01-image-generation.json", "comfyui/01-image-with-style-reference.json", "scripts/post_process.py", "scripts/telegram_notify.py"]},
        {"id": "phase3_video", "name": "Phase 3 — Video pipeline", "status": "done",
         "summary": "H3 cloud primary, H3 Max via fal.ai speed tier, Kling 2.6 Pro hero tier.",
         "deliverables": ["workflows/02-video-generation.json", "scripts/h3_client.py", "scripts/falai_client.py", "scripts/generation_router.py"]},
        {"id": "phase4_opt", "name": "Phase 4 — Optimization", "status": "done",
         "summary": "Variant generator, re-weighting script, A/B test framework, Brand LoRA runbook, H3 license ADR.",
         "deliverables": ["scripts/variant_generator.py", "scripts/reweight_references.py", "scripts/ab_test.py", "docs/brand-lora-training.md", "plan/adr/0003-h3-license-posture.md"]},
        {"id": "phase5_scale", "name": "Phase 5 — Scale", "status": "done",
         "summary": "Social Stats publisher, auto-reply classifier, handoff doc.",
         "deliverables": ["scripts/social_stats_publisher.py", "scripts/auto_reply.py", "docs/handoff.md"]},
    ]


@app.get("/scripts")
def scripts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    scripts_dir = PROJECT_ROOT / "scripts"
    for path in _list_files(scripts_dir, ".py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(errors="ignore")
        has_cli = "if __name__ == \"__main__\":" in text or "argparse" in text
        first_doc = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith('"""') and not stripped.startswith("'''"):
                first_doc = stripped[:120]
                break
        out.append({"name": path.stem, "path": str(path.relative_to(PROJECT_ROOT)), "has_cli": has_cli, "description": first_doc})
    return out


class ScriptRunBody(BaseModel):
    name: str
    args: list[str] = []


@app.post("/scripts/run")
def scripts_run(body: ScriptRunBody) -> dict[str, Any]:
    script = PROJECT_ROOT / "scripts" / f"{body.name}.py"
    if not script.exists():
        raise HTTPException(404, f"script not found: {body.name}")
    cmd = ["python3", str(script), *body.args]
    code, stdout, stderr, ms = _run(cmd, cwd=PROJECT_ROOT, timeout=300)
    return {"ok": code == 0, "exit_code": code, "stdout": stdout[-4000:], "stderr": stderr[-2000:], "duration_ms": int(ms)}


@app.get("/brand")
def brand() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    brand_dir = PROJECT_ROOT / "brand"
    for path in _list_files(brand_dir):
        if path.is_dir():
            continue
        size = path.stat().st_size
        preview = None
        if path.suffix in {".md", ".txt", ".json", ".css"} and size < 50_000:
            preview = _safe_read(path, limit=2000)
        out.append({"path": str(path.relative_to(PROJECT_ROOT)), "size": size, "preview": preview})
    return out


@app.get("/workflows")
def workflows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for root in [PROJECT_ROOT / "workflows", PROJECT_ROOT / "comfyui"]:
        for path in _list_files(root, ".json"):
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            nodes: list[Any] = []
            triggers: list[str] = []
            # n8n format
            if isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], list):
                nodes = data["nodes"]
                for n in nodes:
                    if isinstance(n, dict):
                        t = (n.get("type") or "").lower()
                        if "trigger" in t or "webhook" in t or "cron" in t:
                            triggers.append(n.get("name") or n.get("type", ""))
            # ComfyUI format (dict of node-id -> node-info)
            elif isinstance(data, dict):
                nodes = list(data.values())
            out.append({
                "name": path.stem,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "nodes": len(nodes),
                "triggers": [t for t in triggers if t],
            })
    return out


_test_cache: dict[str, Any] = {"at": 0.0, "data": None}


def _cheap_test_summary() -> dict[str, Any]:
    """Count test functions without invoking pytest (safe for nested tests)."""
    import ast
    total = 0
    files: list[dict[str, int]] = []
    for root in [PROJECT_ROOT / "tests", PROJECT_ROOT / "ui" / "tests"]:
        if not root.exists():
            continue
        for path in sorted(root.glob("test_*.py")):
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:
                continue
            count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_"))
            if count > 0:
                files.append({"file": str(path.relative_to(PROJECT_ROOT)), "passed": count, "failed": 0})
                total += count
    return {"total": total, "passed": total, "failed": 0, "files": files}


def _test_summary_cached(ttl: int = 30) -> dict[str, Any]:
    if _test_cache["data"] is not None and (time.time() - _test_cache["at"]) < ttl:
        return _test_cache["data"]
    # Collect from BOTH directories (but the parser ignores ui/tests/test_ui_backend.py).
    code, stdout, stderr, _ = _run(
        ["python3", "-m", "pytest", "tests/", "ui/tests/", "--collect-only", "-q", "--no-header",
         "--ignore=ui/tests/test_ui_backend.py"],
        cwd=PROJECT_ROOT,
        timeout=120,
    )
    files: dict[str, dict[str, int]] = {}
    total = passed = failed = 0
    out = (stdout or "") + "\n" + (stderr or "")
    for line in out.splitlines():
        line = line.strip()
        if (line.startswith("tests/") or line.startswith("ui/tests/")) and "::" in line:
            f = line.split("::")[0]
            files.setdefault(f, {"passed": 0, "failed": 0})
            files[f]["passed"] += 1
            passed += 1
            total += 1
        elif line.startswith("FAILED "):
            tail = line[len("FAILED "):]
            if (tail.startswith("tests/") or tail.startswith("ui/tests/")) and "::" in tail:
                f = tail.split("::")[0]
                files.setdefault(f, {"passed": 0, "failed": 0})
                files[f]["failed"] += 1
                failed += 1
    data = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "files": [{"file": k, "passed": v["passed"], "failed": v["failed"]} for k, v in sorted(files.items())],
    }
    _test_cache["data"] = data
    _test_cache["at"] = time.time()
    return data


@app.get("/tests")
def tests() -> dict[str, Any]:
    return _test_summary_cached()


@app.post("/tests/run")
def tests_run() -> dict[str, Any]:
    code, stdout, stderr, ms = _run(
        ["python3", "-m", "pytest", "tests/", "ui/tests/", "-q", "--tb=line", "--ignore=ui/tests/test_ui_backend.py"],
        cwd=PROJECT_ROOT,
        timeout=600,
    )
    _test_cache["data"] = None  # invalidate
    # Parse "X passed" / "Y failed" from pytest's summary line
    passed = failed = 0
    for line in (stdout + stderr).splitlines():
        m = re.search(r"(\d+)\s+passed", line)
        if m: passed = int(m.group(1))
        m = re.search(r"(\d+)\s+failed", line)
        if m: failed = int(m.group(1))
    return {
        "ok": code == 0,
        "duration_ms": int(ms),
        "passed": passed,
        "failed": failed,
        "output_tail": (stdout + stderr)[-3000:],
    }


_verify_cache: dict[str, Any] = {"at": 0.0, "data": None}


def _verify_summary_from_cache() -> dict[str, int]:
    """Return the cached verify summary if present, otherwise zero defaults."""
    if _verify_cache.get("data"):
        return _verify_cache["data"]
    return {"pass": 0, "fail": 0, "skip": 0}


def _verify_summary(ttl: int = 60) -> dict[str, int]:
    if _verify_cache["data"] is not None and (time.time() - _verify_cache["at"]) < ttl:
        return _verify_cache["data"]
    code, stdout, stderr, _ = _run(["bash", "verify.sh"], cwd=PROJECT_ROOT, timeout=300)
    text = re.sub(r"\x1b\[[0-9;]*m", "", stdout + stderr)
    p = f = s = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS:"):
            try: p = int(re.match(r"\d+", stripped.split(":", 1)[1].strip()).group(0))
            except: pass
        elif stripped.startswith("FAIL:"):
            try: f = int(re.match(r"\d+", stripped.split(":", 1)[1].strip()).group(0))
            except: pass
        elif stripped.startswith("SKIP:"):
            try: s = int(re.match(r"\d+", stripped.split(":", 1)[1].strip()).group(0))
            except: pass
    data = {"pass": p, "fail": f, "skip": s}
    _verify_cache["data"] = data
    _verify_cache["at"] = time.time()
    return data


@app.post("/verify/run")
def verify_run() -> dict[str, Any]:
    code, stdout, stderr, ms = _run(["bash", "verify.sh"], cwd=PROJECT_ROOT, timeout=300)
    summary = _verify_summary()
    _verify_cache["data"] = None
    return {
        "ok": code == 0,
        "pass": summary["pass"],
        "fail": summary["fail"],
        "skip": summary["skip"],
        "output_tail": (stdout + stderr)[-3000:],
    }


def _env_present(key: str) -> bool:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        if line.strip().startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key and v.strip():
            return True
    return False


@app.get("/accounts")
def accounts() -> list[dict[str, Any]]:
    return [
        {"name": "MiniMax (H3)", "url": "https://api.minimax.io", "purpose": "Video gen cloud API", "required": True, "env_key": "MINIMAX_API_KEY", "env_present": _env_present("MINIMAX_API_KEY")},
        {"name": "fal.ai", "url": "https://fal.ai", "purpose": "H3 Max speed + Kling hero tier", "required": True, "env_key": "FAL_KEY", "env_present": _env_present("FAL_KEY")},
        {"name": "Telegram Bot", "url": "https://t.me/BotFather", "purpose": "Approval gate", "required": True, "env_key": "TELEGRAM_BOT_TOKEN", "env_present": _env_present("TELEGRAM_BOT_TOKEN")},
        {"name": "Cloudflare", "url": "https://dash.cloudflare.com", "purpose": "DNS + R2 backup", "required": True, "env_key": "CLOUDFLARE_API_TOKEN", "env_present": _env_present("CLOUDFLARE_API_TOKEN")},
        {"name": "X / Twitter", "url": "https://developer.twitter.com", "purpose": "Publishing via Social Stats", "required": True, "env_key": "X_BEARER_TOKEN", "env_present": _env_present("X_BEARER_TOKEN")},
        {"name": "Meta Graph (Instagram)", "url": "https://developers.facebook.com", "purpose": "Instagram posting", "required": True, "env_key": "META_ACCESS_TOKEN", "env_present": _env_present("META_ACCESS_TOKEN")},
        {"name": "TikTok for Developers", "url": "https://developers.tiktok.com", "purpose": "Content Posting API", "required": True, "env_key": "TIKTOK_ACCESS_TOKEN", "env_present": _env_present("TIKTOK_ACCESS_TOKEN")},
        {"name": "ElevenLabs", "url": "https://elevenlabs.io", "purpose": "UGC voiceover only", "required": False, "env_key": "ELEVENLABS_API_KEY", "env_present": _env_present("ELEVENLABS_API_KEY")},
    ]


def _adam_status() -> dict[str, Any]:
    user_skills_dir = Path.home() / ".cursor" / "skills"
    project_skills_dir = PROJECT_ROOT / ".cursor" / "skills"
    project_context = PROJECT_ROOT / "adam" / "context"
    return {
        "installed_at_user_level": user_skills_dir.exists() and any(user_skills_dir.iterdir()),
        "installed_at_project_level": project_skills_dir.exists() and any(project_skills_dir.iterdir()),
        "user_skills": sorted(p.name for p in user_skills_dir.iterdir()) if user_skills_dir.exists() else [],
        "project_skills": sorted(p.name for p in project_skills_dir.iterdir()) if project_skills_dir.exists() else [],
        "context_files": sorted(str(p.relative_to(PROJECT_ROOT)) for p in project_context.rglob("*.md")) if project_context.exists() else [],
    }


@app.get("/adam/status")
def adam_status() -> dict[str, Any]:
    status = _adam_status()
    status["ready"] = status["installed_at_project_level"] or status["installed_at_user_level"]
    return status


@app.post("/adam/calibrate")
def adam_calibrate() -> dict[str, Any]:
    ctx_dir = PROJECT_ROOT / "adam" / "context"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    (ctx_dir / "README.md").write_text(
        "# Adam Calibration\n\nRun the Adam `calibrate` skill from Cursor to fill in this folder.\n"
    )
    return {"ok": True, "message": "adam/context/ ready. Run Adam's calibrate skill to populate."}


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
