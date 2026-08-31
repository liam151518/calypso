"""Re-weight Folder A based on engagement data.

After Phase 2-3 has been running for 2-3 weeks, Social Stats has real engagement
data per post. Each reference asset has been used to generate N posts. The
re-weighting task:

1. For each reference in references/ready/, compute the average engagement
   rate (likes+shares+comments) / impressions of the posts it generated.
2. Re-derive engagement_tier based on actual performance.
3. Update the picker weights so high-performers get picked more often.
4. Archive references whose post engagement fell below median.

Input: engagement data from Social Stats API (or manual CSV import).
Output: updated engagement_tier on each reference JSON.

Setup: docs/accounts.md → Social Stats (after Phase 5)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
READY_DIR = REPO_ROOT / "references" / "ready"
ARCHIVED_DIR = REPO_ROOT / "references" / "archived"


def load_engagement_csv(path: Path) -> dict[str, dict[str, float]]:
    """Load a CSV mapping reference_id -> engagement metrics.

    Expected columns: reference_id, posts_generated, avg_likes, avg_shares,
    avg_comments, avg_impressions
    """
    import csv
    out: dict[str, dict[str, float]] = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["reference_id"]] = {
                "posts_generated": int(row.get("posts_generated", 0)),
                "avg_likes": float(row.get("avg_likes", 0)),
                "avg_shares": float(row.get("avg_shares", 0)),
                "avg_comments": float(row.get("avg_comments", 0)),
                "avg_impressions": float(row.get("avg_impressions", 1)),
            }
    return out


def compute_engagement_rate(metrics: dict[str, float]) -> float:
    """Engagement rate = (likes + shares + comments) / impressions."""
    if metrics["avg_impressions"] <= 0:
        return 0.0
    return (metrics["avg_likes"] + metrics["avg_shares"] + metrics["avg_comments"]) / metrics["avg_impressions"]


def reweight(
    ready_dir: Path = READY_DIR,
    archived_dir: Path = ARCHIVED_DIR,
    *,
    dry_run: bool = True,
    archive_threshold: float = 0.0,
) -> dict[str, Any]:
    """Re-weight Folder A. Returns a summary dict.

    Args:
        ready_dir: path to references/ready/
        archived_dir: path to references/archived/
        dry_run: if True, don't write changes; just report
        archive_threshold: engagement_rate below which to archive (0 = only archive if rate=0)
    """
    if not ready_dir.exists():
        return {"error": f"ready_dir does not exist: {ready_dir}"}

    references = list(ready_dir.glob("*.json"))
    if not references:
        return {"processed": 0, "message": "no references to process"}

    # Engagement data is loaded externally — this is a placeholder for the
    # full re-weighting. The script returns a summary based on existing
    # engagement_tier values so it can be tested.
    tiers: dict[str, int] = {}
    for ref_path in references:
        data = json.loads(ref_path.read_text())
        tier = data.get("engagement_tier", "")
        tiers[tier] = tiers.get(tier, 0) + 1

    summary = {
        "processed": len(references),
        "tiers": tiers,
        "dry_run": dry_run,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-weight Folder A references.")
    parser.add_argument("--engagement-csv", type=Path, help="CSV with engagement metrics per reference")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually write changes")
    parser.add_argument("--archive-below", type=float, default=0.0, help="Archive refs below this engagement rate")
    args = parser.parse_args()

    summary = reweight(dry_run=not args.no_dry_run, archive_threshold=args.archive_below)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
