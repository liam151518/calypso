"""calypso-csv-importer extension. Registers a `csv.contacts` importer."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def register(hooks) -> None:
    def import_csv(source: Path, opts: dict[str, Any]) -> dict[str, Any]:
        """Read a CSV file and yield each row. The Phase F.1 contacts
        module uses this to onboard contact lists."""
        if not source.exists():
            return {"ok": False, "error": f"file not found: {source}"}
        rows: list[dict[str, str]] = []
        with source.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
        return {"ok": True, "rows": rows, "count": len(rows)}

    hooks("import.csv.contacts").append(import_csv)
