"""app/server.py — Flask app for Calypso's local web UI.

Routes:
    GET  /                       → redirect to /generate
    GET  /health                 → JSON liveness check (used by the offline banner)
    GET  /generate               → main generate page
    POST /generate               → kick off a generation job, return job_id
    GET  /generate/<id>/status   → HTMX-polled status partial (HTML)
    GET  /outputs                → gallery of past outputs
    GET  /outputs/<ts>/video.mp4 → serve a generated video file
    GET  /references             → references library
    POST /references/upload      → upload a new reference image/video
    POST /references/<id>/delete → delete a reference
    GET  /references/file/<id>   → serve a reference file
    GET  /settings               → API key editor
    POST /settings/<key>         → save a key to .env
    POST /settings/<key>/delete  → remove a key

Run with: bash run.sh
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from app import jobs
from app.settings import (
    KNOWN_KEYS,
    delete_key,
    get_raw,
    list_keys,
    save_key,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_UPLOAD_DIR = PROJECT_ROOT / "references" / "uploads"
ALLOWED_REFERENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"}


def create_app() -> Flask:
    """App factory. Used by both `python -m app.server` and the test suite."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    # Secret key is required for flash() messages. In a desktop app this is local-only.
    app.config["SECRET_KEY"] = "calypso-local-dev"
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit

    _register_routes(app)
    return app


# ---------- route helpers ----------

def _known_env_var_or_404(env_var: str) -> str:
    """Return env_var if it's a known key, else raise 404."""
    allowed = {k["env_var"] for k in KNOWN_KEYS}
    if env_var not in allowed:
        abort(404)
    return env_var


def _generate_outputs_for_gallery() -> list[dict]:
    """Walk outputs/<timestamp>/video.mp4 and return metadata for the gallery."""
    out: list[dict] = []
    if not jobs.OUTPUTS_DIR.exists():
        return out
    for run_dir in sorted(jobs.OUTPUTS_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        video = run_dir / "video.mp4"
        if not video.exists():
            continue
        size_mb = video.stat().st_size / (1024 * 1024)
        out.append(
            {
                "id": run_dir.name,
                "path": video,
                "rel_url": url_for("outputs_video", ts=run_dir.name),
                "size_mb": round(size_mb, 2),
                "created": run_dir.stat().st_mtime,
            }
        )
    return out


def _render_job_block(job) -> str:
    """Render the job-region HTML block for a newly-created job.

    Includes the job card and the HTMX polling wiring, so the page only needs
    to swap this string into #job-region.
    """
    from flask import render_template

    return render_template(
        "job_block.html",
        job=job.to_dict(),
        status_url=url_for("generate_status", job_id=job.job_id),
    )


def _references_for_library() -> list[dict]:
    """Walk references/uploads/ and return metadata for the references page."""
    out: list[dict] = []
    if not REFERENCES_UPLOAD_DIR.exists():
        return out
    for f in sorted(REFERENCES_UPLOAD_DIR.iterdir(), reverse=True):
        if not f.is_file():
            continue
        out.append(
            {
                "id": f.name,
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "ext": f.suffix.lower().lstrip("."),
                "rel_url": url_for("references_file", id=f.name),
            }
        )
    return out


# ---------- routes ----------

def _register_routes(app: Flask) -> None:

    @app.route("/")
    def home():
        return redirect(url_for("generate_page"))

    @app.route("/health")
    def health():
        """Liveness check used by the offline banner / smoke tests."""
        wants_html = "text/html" in (request.headers.get("Accept") or "")
        if wants_html:
            return render_template("_health.html"), 200
        return jsonify({"status": "ok", "service": "calypso", "version": "0.1.0"})

    @app.route("/health.json")
    def health_json():
        """Always JSON, used by smoke tests."""
        return jsonify({"status": "ok", "service": "calypso", "version": "0.1.0"})

    # ---------- generate ----------

    @app.route("/generate")
    def generate_page():
        keys = list_keys()
        return render_template(
            "generate.html",
            keys=keys,
            references=_references_for_library(),
            recent_jobs=jobs.list_jobs(limit=10),
            VALID_MODELS=jobs.VALID_MODELS,
            VALID_RESOLUTIONS=jobs.VALID_RESOLUTIONS,
        )

    @app.route("/generate", methods=["POST"])
    def generate_submit():
        prompt = (request.form.get("prompt") or "").strip()
        model = (request.form.get("model") or "auto").strip()
        # The dropdown sends a reference file's id (filename). Translate to absolute path.
        reference_id = (request.form.get("reference") or "").strip() or None
        reference_path = None
        if reference_id:
            candidate = REFERENCES_UPLOAD_DIR / reference_id
            # Safety: ensure the resolved path is still inside the upload dir
            if candidate.exists() and REFERENCES_UPLOAD_DIR in candidate.resolve().parents:
                reference_path = str(candidate)
        try:
            duration = int(request.form.get("duration") or 8)
        except ValueError:
            duration = 8
        resolution = (request.form.get("resolution") or "768p").strip()

        # Validate
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
        if model not in jobs.VALID_MODELS:
            return jsonify({"error": f"Unknown model: {model}"}), 400
        if resolution not in jobs.VALID_RESOLUTIONS:
            return jsonify({"error": f"Unknown resolution: {resolution}"}), 400
        if duration < 1 or duration > 60:
            return jsonify({"error": "Duration must be 1-60 seconds"}), 400

        # Pre-flight: at least one of fal/h3 keys must be set
        has_fal = bool(get_raw("FAL_API_KEY"))
        has_h3 = bool(get_raw("MINIMAX_API_KEY"))
        if not (has_fal or has_h3):
            return (
                jsonify(
                    {
                        "error": "No API keys configured. Open Settings and add at least one key.",
                        "redirect": url_for("settings_page"),
                    }
                ),
                400,
            )

        job = jobs.create_job(
            prompt,
            model=model,
            reference=reference_path,
            duration=duration,
            resolution=resolution,
        )
        jobs.start_job(job)
        # Return HTML for HTMX to swap in. The returned block sets up polling itself
        # so the page just needs to swap it into #job-region.
        return _render_job_block(job)

    @app.route("/generate/<job_id>/status")
    def generate_status(job_id: str):
        job = jobs.get_job(job_id)
        if job is None:
            abort(404)
        return render_template("job_status.html", job=job.to_dict())

    # ---------- outputs ----------

    @app.route("/outputs")
    def outputs_page():
        return render_template("outputs.html", items=_generate_outputs_for_gallery())

    @app.route("/outputs/<ts>/video.mp4")
    def outputs_video(ts: str):
        # ts is the timestamp directory name (e.g. 20260101-120000)
        video_dir = jobs.OUTPUTS_DIR / ts
        if not video_dir.exists() or not (video_dir / "video.mp4").exists():
            abort(404)
        return send_from_directory(video_dir, "video.mp4", mimetype="video/mp4")

    # ---------- references ----------

    @app.route("/references")
    def references_page():
        return render_template("references.html", items=_references_for_library())

    @app.route("/references/upload", methods=["POST"])
    def references_upload():
        file = request.files.get("file")
        if file is None or file.filename == "":
            flash("No file selected.", "error")
            return redirect(url_for("references_page"))
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_REFERENCE_EXTENSIONS:
            flash(f"Unsupported file type: {ext}", "error")
            return redirect(url_for("references_page"))
        REFERENCES_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # Save with a stable name to avoid collisions: <timestamp>_<safe-name>
        safe_name = Path(file.filename).name.replace("/", "_").replace("\\", "_")
        dest = REFERENCES_UPLOAD_DIR / f"{Path(safe_name).stem}_{int(time.time())}{ext}"
        file.save(dest)
        flash(f"Uploaded {dest.name}", "success")
        return redirect(url_for("references_page"))

    @app.route("/references/<id>/delete", methods=["POST"])
    def references_delete(id: str):
        target = REFERENCES_UPLOAD_DIR / id
        if not target.exists() or not target.is_file():
            abort(404)
        # Belt-and-suspenders: ensure the resolved path is still inside the upload dir
        if REFERENCES_UPLOAD_DIR not in target.resolve().parents:
            abort(404)
        target.unlink()
        flash(f"Deleted {id}", "success")
        return redirect(url_for("references_page"))

    @app.route("/references/file/<id>")
    def references_file(id: str):
        if not (REFERENCES_UPLOAD_DIR / id).exists():
            abort(404)
        return send_from_directory(REFERENCES_UPLOAD_DIR, id)

    # ---------- settings ----------

    @app.route("/settings")
    def settings_page():
        return render_template("settings.html", keys=list_keys())

    @app.route("/settings/<env_var>", methods=["POST"])
    def settings_save(env_var: str):
        env_var = _known_env_var_or_404(env_var)
        value = (request.form.get("value") or "").strip()
        if not value:
            flash("Value cannot be empty. Use Delete to remove a key.", "error")
            return redirect(url_for("settings_page"))
        try:
            save_key(env_var, value)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        flash(f"Saved {env_var}", "success")
        return redirect(url_for("settings_page"))

    @app.route("/settings/<env_var>/delete", methods=["POST"])
    def settings_delete(env_var: str):
        env_var = _known_env_var_or_404(env_var)
        try:
            delete_key(env_var)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        flash(f"Deleted {env_var}", "success")
        return redirect(url_for("settings_page"))

    # ---------- error handlers ----------

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404


def main() -> None:
    """Entrypoint for `python -m app.server` and `bash run.sh`."""
    import os

    host = os.environ.get("CALYPSO_HOST", "127.0.0.1")
    port = int(os.environ.get("CALYPSO_PORT", "8765"))
    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
