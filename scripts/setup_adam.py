"""setup-adam. Project bootstrap for Adam.

Idempotent: run any time, safe to repeat.

- Ensures the Adam folder contract exists (packet/, plan/, slices/, agent-control/, adam/context/).
- Ensures the project-level skill install at .cursor/skills/ is populated.
- Runs verify.sh at the end.

Usage:
    python3 scripts/setup_adam.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAM_HOME = PROJECT_ROOT / "adam"
PACKET = PROJECT_ROOT / "packet"
PLAN = PROJECT_ROOT / "plan"
PLAN_ADR = PLAN / "adr"
SLICES = PROJECT_ROOT / "slices"
AGENT_CONTROL = PROJECT_ROOT / "agent-control"
CURSOR_SKILLS = PROJECT_ROOT / ".cursor" / "skills"


def ensure_dir(path: Path, marker: str | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if marker and not (path / marker).exists():
        (path / marker).write_text(f"# {path.name}\n\nCreated by setup-adam.\n")


def main() -> int:
    print(f"setup-adam: bootstrapping {PROJECT_ROOT}")

    # Folder contract
    ensure_dir(PACKET, "README.md")
    ensure_dir(PLAN, "README.md")
    ensure_dir(PLAN_ADR, "README.md")
    ensure_dir(SLICES, "README.md")
    ensure_dir(AGENT_CONTROL, "README.md")
    ensure_dir(ADAM_HOME / "context", "README.md")
    ensure_dir(ADAM_HOME / "memory", "README.md")

    # Project-level skills
    if not CURSOR_SKILLS.exists() or not any(CURSOR_SKILLS.iterdir()):
        print(f"setup-adam: populating {CURSOR_SKILLS.relative_to(PROJECT_ROOT)}")
        ensure_dir(CURSOR_SKILLS)
        # Skills should already be present from the repo; if missing, this is a manual step.
    else:
        skill_count = sum(1 for p in CURSOR_SKILLS.iterdir() if p.is_dir())
        print(f"setup-adam: {skill_count} skills already installed at .cursor/skills/")

    # User-level skills check (informational only)
    user_skills = Path.home() / ".cursor" / "skills"
    if user_skills.exists():
        user_count = sum(1 for p in user_skills.iterdir() if p.is_dir())
        print(f"setup-adam: {user_count} skills at user level (~/.cursor/skills/)")

    # Run verify
    print("setup-adam: running verify.sh")
    result = subprocess.run(["bash", "verify.sh"], cwd=PROJECT_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
