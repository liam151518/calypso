"""app/server.py — Flask app for Calypso's local web UI.

Routes:
    GET  /                          → redirect to /generate
    GET  /health                    → JSON liveness check
    GET  /generate                  → main generate page
    POST /generate                  → kick off generation (single or batch), return HTML
    GET  /generate/<id>/status      → HTMX-polled job status partial
    GET  /generate/batch/<id>/status→ HTMX-polled batch status partial
    GET  /outputs                   → gallery of past outputs
    GET  /outputs/<ts>/video.mp4    → serve a generated video file
    GET  /outputs/<id>/prompt       → HTMX partial: disclosure of the effective prompt
    GET  /references                → references library
    POST /references/upload         → upload a new reference image/video
    POST /references/<id>/delete    → delete a reference
    GET  /references/file/<id>      → serve a reference file
    POST /references/<id>/tags      → set tags on a reference (HTMX)
    GET  /brand                     → brand editor
    POST /brand/save                → create/update a brand
    POST /brand/<id>/delete         → delete a brand
    POST /brand/<id>/activate       → set active brand
    POST /brand/clear               → clear active brand
    POST /drafts/save               → create/update a draft
    POST /drafts/<id>/delete        → delete a draft
    POST /drafts/<id>/favorite      → toggle favorite
    GET  /settings                  → API key editor
    POST /settings/<key>            → save a key to .env
    POST /settings/<key>/delete     → remove a key

Run with: bash run.sh
"""

from __future__ import annotations

import json
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

from app import drafts
from app import jobs
from app import refs as refs_mod
from app import brand as brand_mod
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
    from app import db as app_db

    app = Flask(__name__, template_folder="templates", static_folder="static")
    # Secret key is required for flash() messages. In a desktop app this is local-only.
    app.config["SECRET_KEY"] = "calypso-local-dev"
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit

    @app.template_filter("basename")
    def _basename(path_str: str) -> str:
        return Path(path_str).name if path_str else ""

    # Make sure the structured-data DB exists before any route touches it.
    app_db.init_db()

    _register_routes(app)
    return app


# ---------- route helpers ----------

def _known_env_var_or_404(env_var: str) -> str:
    """Return env_var if it's a known key, else raise 404."""
    allowed = {k["env_var"] for k in KNOWN_KEYS}
    if env_var not in allowed:
        abort(404)
    return env_var


def _resolve_ref_path(filename: str | None) -> str | None:
    """Resolve a reference filename to its absolute path, with traversal guard."""
    if not filename:
        return None
    p = refs_mod.resolve_to_path(filename)
    return str(p) if p is not None else None


def _gather_ref_paths(ref_ids: list[str]) -> list[tuple[str, str | None]]:
    """Translate a list of reference ids into (id, absolute-path) pairs,
    silently dropping any that fail the traversal guard."""
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for rid in ref_ids:
        if not rid or rid in seen:
            continue
        seen.add(rid)
        path = _resolve_ref_path(rid)
        out.append((rid, path))
    return out


def _save_job_link(job: jobs.Job, *, effective_prompt: str) -> None:
    """Persist a job_links row so Outputs can re-derive the prompt later."""
    from app import db as app_db
    conn = app_db.get_conn()
    conn.execute(
        """
        INSERT INTO job_links(job_id, prompt_body, draft_id, brand_id, ref_ids_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            prompt_body = excluded.prompt_body,
            draft_id = excluded.draft_id,
            brand_id = excluded.brand_id,
            ref_ids_json = excluded.ref_ids_json
        """,
        (
            job.job_id,
            effective_prompt,
            job.draft_id,
            job.brand_id,
            json.dumps(job.ref_ids),
            time.time(),
        ),
    )


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


def _render_job_block(job: jobs.Job) -> str:
    """Render the job-region HTML block for a newly-created job."""
    return render_template(
        "job_block.html",
        job=job.to_dict(),
        status_url=url_for("generate_status", job_id=job.job_id),
    )


def _render_batch_block(batch_id: str) -> str:
    """Render a batch card listing all child jobs."""
    summary = jobs.get_batch_summary(batch_id)
    children = [j.to_dict() for j in jobs.list_jobs_for_batch(batch_id)]
    return render_template(
        "_partials/batch_block.html",
        batch_id=batch_id,
        summary=summary,
        children=children,
        status_url=url_for("batch_status", batch_id=batch_id),
        child_status_url=lambda jid: url_for("generate_status", job_id=jid),
    )


def _references_for_library() -> list[dict]:
    """Return references with their tags for the library view."""
    return refs_mod.list_refs()


def _all_tags_for_filter() -> list[dict]:
    """Tag list with counts for the sidebar filter."""
    return refs_mod.all_tags()


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
            all_tags=_all_tags_for_filter(),
            drafts=drafts.list_drafts(limit=50),
            active_brand=brand_mod.get_active_brand(),
            brands=brand_mod.list_brands(),
            categories=drafts.categories(),
            recent_jobs=jobs.list_jobs(limit=10),
            VALID_MODELS=jobs.VALID_MODELS,
            VALID_RESOLUTIONS=jobs.VALID_RESOLUTIONS,
        )

    @app.route("/generate", methods=["POST"])
    def generate_submit():
        prompt = (request.form.get("prompt") or "").strip()
        model = (request.form.get("model") or "auto").strip()
        try:
            duration = int(request.form.get("duration") or 8)
        except ValueError:
            duration = 8
        resolution = (request.form.get("resolution") or "768p").strip()

        # Multi-ref picker sends ref_ids[]; legacy single-ref posts use `reference`.
        ref_ids_raw = request.form.getlist("ref_ids")
        legacy_ref = (request.form.get("reference") or "").strip()
        ref_ids: list[str] = [r for r in ref_ids_raw if r]
        if not ref_ids and legacy_ref:
            ref_ids = [legacy_ref]

        draft_id_raw = (request.form.get("draft_id") or "").strip()
        brand_id_raw = (request.form.get("brand_id") or "").strip()
        draft_id: int | None = None
        brand_id: int | None = None
        if draft_id_raw:
            try:
                draft_id = int(draft_id_raw)
            except ValueError:
                draft_id = None
        if brand_id_raw:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                brand_id = None

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

        # Resolve refs (silently drop invalid/traversal attempts).
        ref_pairs = _gather_ref_paths(ref_ids)

        # Compose prompt with brand block (if any).
        effective_prompt = brand_mod.compose_prompt(prompt, brand_id=brand_id)

        if len(ref_pairs) > 1:
            # Multi-ref becomes a batch.
            batch_id, created_jobs = jobs.create_batch(
                effective_prompt,
                refs=ref_pairs,
                model=model,
                duration=duration,
                resolution=resolution,
                effective_prompt=effective_prompt,
                draft_id=draft_id,
                brand_id=brand_id,
            )
            for job in created_jobs:
                jobs.start_job(job)
                _save_job_link(job, effective_prompt=effective_prompt)
            return _render_batch_block(batch_id)

        # Single-ref or no-ref path.
        ref_id, ref_path = (ref_pairs[0] if ref_pairs else ("", None))
        job = jobs.create_job(
            effective_prompt,
            model=model,
            reference=ref_path,
            duration=duration,
            resolution=resolution,
            effective_prompt=effective_prompt,
            ref_ids=[ref_id] if ref_id else [],
            draft_id=draft_id,
            brand_id=brand_id,
        )
        jobs.start_job(job)
        _save_job_link(job, effective_prompt=effective_prompt)
        return _render_job_block(job)

    @app.route("/generate/<job_id>/status")
    def generate_status(job_id: str):
        job = jobs.get_job(job_id)
        if job is None:
            abort(404)
        return render_template("job_status.html", job=job.to_dict())

    @app.route("/generate/batch/<batch_id>/status")
    def batch_status(batch_id: str):
        summary = jobs.get_batch_summary(batch_id)
        if summary is None:
            abort(404)
        children = [j.to_dict() for j in jobs.list_jobs_for_batch(batch_id)]
        return render_template(
            "_partials/batch_children.html",
            batch_id=batch_id,
            summary=summary,
            children=children,
            child_status_url=lambda jid: url_for("generate_status", job_id=jid),
        )

    # ---------- outputs ----------

    @app.route("/outputs")
    def outputs_page():
        # Decorate each output with its job_link (prompt + refs) for re-derivation.
        from app import db as app_db

        conn = app_db.get_conn()
        items = _generate_outputs_for_gallery()
        decorated: list[dict] = []
        for item in items:
            row = conn.execute(
                "SELECT prompt_body, ref_ids_json FROM job_links WHERE job_id = ?",
                (item["id"],),
            ).fetchone()
            if row:
                try:
                    ref_ids = json.loads(row["ref_ids_json"] or "[]")
                except json.JSONDecodeError:
                    ref_ids = []
                item["prompt"] = row["prompt_body"]
                item["ref_ids"] = ref_ids
            else:
                item["prompt"] = None
                item["ref_ids"] = []
            decorated.append(item)
        return render_template("outputs.html", items=decorated)

    @app.route("/outputs/<ts>/video.mp4")
    def outputs_video(ts: str):
        video_dir = jobs.OUTPUTS_DIR / ts
        if not video_dir.exists() or not (video_dir / "video.mp4").exists():
            abort(404)
        return send_from_directory(video_dir, "video.mp4", mimetype="video/mp4")

    @app.route("/outputs/<job_id>/prompt")
    def outputs_prompt(job_id: str):
        """Disclosure partial: shows the effective prompt for a job."""
        from app import db as app_db

        conn = app_db.get_conn()
        row = conn.execute(
            """
            SELECT jl.prompt_body, jl.ref_ids_json,
                   bp.name AS brand_name,
                   d.name AS draft_name
            FROM job_links jl
            LEFT JOIN brand_profiles bp ON bp.id = jl.brand_id
            LEFT JOIN drafts d ON d.id = jl.draft_id
            WHERE jl.job_id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            abort(404)
        try:
            ref_ids = json.loads(row["ref_ids_json"] or "[]")
        except json.JSONDecodeError:
            ref_ids = []
        refs_detail = refs_mod.list_refs()
        ref_lookup = {r["id"]: r for r in refs_detail}
        refs_for_job = [
            {"id": rid, "name": rid, "rel_url": ref_lookup[rid]["rel_url"]}
            for rid in ref_ids
            if rid in ref_lookup
        ]
        return render_template(
            "_partials/prompt_disclosure.html",
            job_id=job_id,
            prompt=row["prompt_body"],
            brand_name=row["brand_name"],
            draft_name=row["draft_name"],
            refs=refs_for_job,
        )

    # ---------- references ----------

    @app.route("/references")
    def references_page():
        tag_filter = (request.args.get("tag") or "").strip() or None
        return render_template(
            "references.html",
            items=refs_mod.list_refs(tag=tag_filter),
            all_tags=refs_mod.all_tags(),
            active_tag=tag_filter,
        )

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
        safe_name = Path(file.filename).name.replace("/", "_").replace("\\", "_")
        dest = REFERENCES_UPLOAD_DIR / f"{Path(safe_name).stem}_{int(time.time())}{ext}"
        file.save(dest)
        # Persist any tags the user typed into the upload form.
        raw_tags = (request.form.get("tags") or "").strip()
        if raw_tags:
            tag_names = [refs_mod.normalise_tag(t) for t in raw_tags.split(",")]
            tag_names = [t for t in tag_names if t]
            if tag_names:
                refs_mod.set_tags(dest.name, tag_names)
        flash(f"Uploaded {dest.name}", "success")
        return redirect(url_for("references_page"))

    @app.route("/references/<id>/delete", methods=["POST"])
    def references_delete(id: str):
        target = REFERENCES_UPLOAD_DIR / id
        if not target.exists() or not target.is_file():
            abort(404)
        if REFERENCES_UPLOAD_DIR not in target.resolve().parents:
            abort(404)
        target.unlink()
        # Drop tag associations so the DB doesn't keep dangling rows.
        from app import db as app_db

        conn = app_db.get_conn()
        conn.execute("DELETE FROM reference_tags WHERE reference_id = ?", (id,))
        flash(f"Deleted {id}", "success")
        return redirect(url_for("references_page"))

    @app.route("/references/<id>/tags", methods=["POST"])
    def references_set_tags(id: str):
        """Set the tags on a reference. HTMX partial returns the tag pills."""
        if not (REFERENCES_UPLOAD_DIR / id).exists():
            abort(404)
        raw = (request.form.get("tags") or "").strip()
        names = [refs_mod.normalise_tag(t) for t in raw.split(",") if t.strip()]
        names = [n for n in names if n]
        refs_mod.set_tags(id, names)
        ref_payload = {"id": id, "tags": sorted(refs_mod.get_tags(id)), "name": id}
        return render_template("_partials/ref_tag_editor.html", ref=ref_payload)

    @app.route("/references/file/<id>")
    def references_file(id: str):
        if not (REFERENCES_UPLOAD_DIR / id).exists():
            abort(404)
        return send_from_directory(REFERENCES_UPLOAD_DIR, id)

    # ---------- brand ----------

    @app.route("/brand")
    def brand_page():
        return render_template(
            "brand.html",
            brands=brand_mod.list_brands(),
            active_brand=brand_mod.get_active_brand(),
        )

    @app.route("/brand/save", methods=["POST"])
    def brand_save():
        brand_id_raw = (request.form.get("brand_id") or "").strip()
        brand_id = int(brand_id_raw) if brand_id_raw else None
        try:
            saved = brand_mod.save_brand(
                name=request.form.get("name") or "",
                tagline=request.form.get("tagline") or "",
                audience=request.form.get("audience") or "",
                palette=request.form.get("palette") or "",
                typography=request.form.get("typography") or "",
                voice=request.form.get("voice") or "",
                do_examples=request.form.get("do_examples") or "",
                dont_examples=request.form.get("dont_examples") or "",
                style_guide=request.form.get("style_guide") or "",
                brand_id=brand_id,
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("brand_page"))
        if request.form.get("set_active"):
            brand_mod.set_active_brand(saved["id"])
            flash(f"Saved '{saved['name']}' and set as active brand.", "success")
        else:
            flash(f"Saved '{saved['name']}'.", "success")
        return redirect(url_for("brand_page"))

    @app.route("/brand/<int:brand_id>/delete", methods=["POST"])
    def brand_delete(brand_id: int):
        brand_mod.delete_brand(brand_id)
        flash("Brand deleted.", "success")
        return redirect(url_for("brand_page"))

    @app.route("/brand/<int:brand_id>/activate", methods=["POST"])
    def brand_activate(brand_id: int):
        try:
            brand_mod.set_active_brand(brand_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("Active brand updated.", "success")
        return redirect(url_for("brand_page"))

    @app.route("/brand/clear", methods=["POST"])
    def brand_clear():
        brand_mod.clear_active_brand()
        flash("Active brand cleared.", "success")
        return redirect(url_for("brand_page"))

    # ---------- drafts ----------

    @app.route("/drafts/save", methods=["POST"])
    def draft_save():
        draft_id_raw = (request.form.get("draft_id") or "").strip()
        draft_id = int(draft_id_raw) if draft_id_raw else None
        try:
            drafts.save_draft(
                name=request.form.get("name") or "",
                body=request.form.get("body") or "",
                category=request.form.get("category") or "",
                draft_id=draft_id,
                is_favorite=str(request.form.get("is_favorite") or "").lower() in ("1", "true"),
            )
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("Draft saved.", "success")
        return redirect(request.referrer or url_for("generate_page"))

    @app.route("/drafts/<int:draft_id>/delete", methods=["POST"])
    def draft_delete(draft_id: int):
        drafts.delete_draft(draft_id)
        flash("Draft deleted.", "success")
        return redirect(request.referrer or url_for("generate_page"))

    @app.route("/drafts/<int:draft_id>/favorite", methods=["POST"])
    def draft_favorite(draft_id: int):
        drafts.toggle_favorite(draft_id)
        if request.headers.get("HX-Request"):
            return ("", 204)
        return redirect(request.referrer or url_for("generate_page"))

    @app.route("/drafts/api")
    def drafts_api():
        """HTMX-target endpoint: returns just the result list HTML."""
        query = (request.args.get("draft_query") or "").strip() or None
        category = (request.args.get("draft_category") or "").strip() or None
        favorites_only = request.args.get("favorites_only") == "on"
        items = drafts.list_drafts(
            query=query,
            category=category,
            favorites_only=favorites_only,
            limit=50,
        )
        return render_template("_partials/draft_results.html", drafts=items)

    # ---------- settings ----------

    @app.route("/settings")
    def settings_page():
        from pathlib import Path as _Path
        return render_template("settings.html", keys=list_keys(), project_root=str(_Path(__file__).resolve().parent.parent))

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