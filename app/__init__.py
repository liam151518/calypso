"""Calypso Flask web UI — local-first video generation dashboard.

The app is intentionally tiny: a single Flask process, Jinja templates, and
HTMX for lightweight interactivity. No build step, no npm, no Docker.

Run with `bash run.sh` from the repo root (or `python -m app.server`).
"""

__version__ = "0.1.0"
