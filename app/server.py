"""app/server.py — Flask app for Calypso's local web UI + JSON API.

Legacy HTML routes (for the existing Jinja UI and tests):
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

JSON API consumed by the React frontend:
    GET    /api/health
    GET    /api/keys
    POST   /api/keys/<env_var>
    DELETE /api/keys/<env_var>
    GET    /api/refs
    POST   /api/refs                 (multipart)
    PATCH  /api/refs/<id>/tags
    DELETE /api/refs/<id>
    GET    /api/brands
    POST   /api/brands
    PATCH  /api/brands/<id>
    DELETE /api/brands/<id>
    POST   /api/brands/<id>/activate
    DELETE /api/brands/active
    GET    /api/drafts
    POST   /api/drafts
    DELETE /api/drafts/<id>
    POST   /api/drafts/<id>/favorite
    GET    /api/jobs
    GET    /api/jobs/<id>
    POST   /api/generate              (same payload as POST /generate, returns JSON)

Static SPA:
    When web/dist/ exists, GET / returns web/dist/index.html, and any
    unmatched GET (that isn't /api/ or /static/ or /outputs/ or /references/file/
    or /generate/<id>/status or /generate/batch/<id>/status) falls through to
    the SPA index so client-side routing works.

Run with: bash run.sh
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

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
WEB_DIST = PROJECT_ROOT / "web" / "dist"
ALLOWED_REFERENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"}


def create_app() -> Flask:
    """App factory. Used by both `python -m app.server` and the test suite."""
    from app import db as app_db

    app = Flask(__name__, template_folder="templates", static_folder="static")
    # Secret key is required for flash() messages. In a desktop app this is local-only.
    app.config["SECRET_KEY"] = "calypso-local-dev"
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit
    app.config["JSON_SORT_KEYS"] = False

    @app.template_filter("basename")
    def _basename(path_str: str) -> str:
        return Path(path_str).name if path_str else ""

    # Make sure the structured-data DB exists before any route touches it.
    app_db.init_db()

    _register_routes(app)
    _register_api_routes(app)
    _register_spa_fallback(app)
    return app


# ---------- content negotiation ----------

def wants_json() -> bool:
    """True if the client prefers JSON. Honors explicit ?json=1 too."""
    if request.args.get("json") == "1":
        return True
    accept = (request.headers.get("Accept") or "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False


def spa_serving_enabled() -> bool:
    """True when the built SPA bundle is present — in which case page routes
    should defer to the SPA for browser requests."""
    return (WEB_DIST / "index.html").exists()


def serve_spa_or_fallback():
    """Return the SPA's index.html for browser requests, else None."""
    if not spa_serving_enabled():
        return None
    # HTMX partial requests still want HTML fragments, not the SPA shell.
    if request.headers.get("HX-Request"):
        return None
    return send_from_directory(WEB_DIST, "index.html")


def ok(payload: Any | None = None) -> Any:
    """Standard success JSON."""
    body: dict[str, Any] = {"ok": True}
    if payload:
        body.update(payload)
    return jsonify(body)


def err(message: str, *, code: int = 400, **extra: Any) -> tuple[Any, int]:
    """Standard error JSON."""
    body: dict[str, Any] = {"ok": False, "error": message}
    body.update(extra)
    return jsonify(body), code


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


def _job_to_json(job: jobs.Job) -> dict:
    """Project an in-memory Job into the JSON shape the SPA wants."""
    d = job.to_dict()
    return {
        "id": d["job_id"],
        "status": d["status"],
        "prompt": d["prompt"],
        "effective_prompt": d.get("effective_prompt"),
        "model": d["model"],
        "duration": d["duration"],
        "resolution": d["resolution"],
        "reference": d.get("reference"),
        "references": d.get("references") or [],
        "ref_ids": d.get("ref_ids") or [],
        "draft_id": d.get("draft_id"),
        "brand_id": d.get("brand_id"),
        "batch_id": d.get("batch_id"),
        "output_rel": url_for("outputs_video", ts=d["job_id"]) if d.get("status") == "succeeded" else None,
        "elapsed_seconds": d.get("elapsed_seconds"),
        "cost_usd": d.get("cost_usd"),
        "error": d.get("error"),
    }


def _job_link_payload(job_id: str) -> dict | None:
    """Pull the saved job_link row + joined brand/draft names for an output."""
    from app import db as app_db
    conn = app_db.get_conn()
    row = conn.execute(
        """
        SELECT jl.prompt_body, jl.ref_ids_json, jl.draft_id, jl.brand_id,
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
        return None
    try:
        ref_ids = json.loads(row["ref_ids_json"] or "[]")
    except json.JSONDecodeError:
        ref_ids = []
    refs_detail = refs_mod.list_refs()
    ref_lookup = {r["id"]: r for r in refs_detail}
    return {
        "job_id": job_id,
        "prompt": row["prompt_body"],
        "ref_ids": ref_ids,
        "brand_id": row["brand_id"],
        "brand_name": row["brand_name"],
        "draft_id": row["draft_id"],
        "draft_name": row["draft_name"],
        "refs": [
            {"id": rid, "name": rid, "rel_url": ref_lookup[rid]["rel_url"]}
            for rid in ref_ids
            if rid in ref_lookup
        ],
    }


# ---------- HTML routes ----------

def _register_routes(app: Flask) -> None:

    @app.route("/")
    def home():
        # The SPA fallback (below) renders the React bundle at /. We keep this
        # handler as a last-resort redirect so users who only have Flask running
        # without web/dist/ still get to /generate.
        if (WEB_DIST / "index.html").exists():
            return send_from_directory(WEB_DIST, "index.html")
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
        spa = serve_spa_or_fallback()
        if spa is not None:
            return spa
        if wants_json():
            return ok({
                "keys": list_keys(),
                "refs": refs_mod.list_refs(),
                "tags": refs_mod.all_tags(),
                "drafts": drafts.list_drafts(limit=50),
                "categories": drafts.categories(),
                "brands": brand_mod.list_brands(),
                "active_brand": brand_mod.get_active_brand(),
                "recent_jobs": [_job_to_json(j) for j in jobs.list_jobs(limit=10)],
                "valid_models": jobs.VALID_MODELS,
                "valid_resolutions": jobs.VALID_RESOLUTIONS,
            })
        return render_template(
            "generate.html",
            keys=list_keys(),
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
        """Shared dispatch for /generate (HTML/HTMX) and /api/generate (JSON).

        Both call sites funnel into _dispatch_generate(); the caller
        decides whether to render HTML or return JSON.
        """
        # Validation + dispatch is shared below.
        payload, status_code = _dispatch_generate()
        if not isinstance(payload, dict):
            # Should never happen — dispatch always returns a dict or a Flask response.
            return payload  # type: ignore[return-value]
        if status_code != 200:
            return err(payload.get("error", "Failed"), code=status_code, **{
                k: v for k, v in payload.items() if k != "error"
            })
        if wants_json():
            return ok(payload)
        # Legacy HTML path.
        if payload.get("kind") == "batch":
            return _render_batch_block(payload["batch_id"])
        job = jobs.get_job(payload["job"]["id"]) if payload.get("job") else None
        if job is None:
            abort(500)
        return _render_job_block(job)

    @app.route("/generate/<job_id>/status")
    def generate_status(job_id: str):
        job = jobs.get_job(job_id)
        if job is None:
            abort(404)
        if wants_json():
            return ok({"job": _job_to_json(job)})
        return render_template("job_status.html", job=job.to_dict())

    @app.route("/generate/batch/<batch_id>/status")
    def batch_status(batch_id: str):
        summary = jobs.get_batch_summary(batch_id)
        if summary is None:
            abort(404)
        children = [j.to_dict() for j in jobs.list_jobs_for_batch(batch_id)]
        if wants_json():
            return ok({
                "batch_id": batch_id,
                "summary": summary,
                "children": [_job_to_json(jobs.get_job(c["job_id"])) for c in children],
            })
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
        spa = serve_spa_or_fallback()
        if spa is not None:
            return spa
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
        if wants_json():
            json_items = []
            for item in decorated:
                link = _job_link_payload(item["id"])
                json_items.append({
                    "id": item["id"],
                    "rel_url": item["rel_url"],
                    "size_mb": item["size_mb"],
                    "created": item["created"],
                    "prompt": link["prompt"] if link else None,
                    "brand_name": link["brand_name"] if link else None,
                    "draft_name": link["draft_name"] if link else None,
                    "refs": link["refs"] if link else [],
                })
            return ok({"outputs": json_items})
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
        link = _job_link_payload(job_id)
        if link is None:
            abort(404)
        if wants_json():
            return ok(link)
        return render_template(
            "_partials/prompt_disclosure.html",
            job_id=link["job_id"],
            prompt=link["prompt"],
            brand_name=link["brand_name"],
            draft_name=link["draft_name"],
            refs=link["refs"],
        )

    # ---------- references ----------

    @app.route("/references")
    def references_page():
        spa = serve_spa_or_fallback()
        if spa is not None:
            return spa
        tag_filter = (request.args.get("tag") or "").strip() or None
        if wants_json():
            return ok({
                "refs": refs_mod.list_refs(tag=tag_filter),
                "tags": refs_mod.all_tags(),
                "active_tag": tag_filter,
            })
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
        from app import db as app_db
        conn = app_db.get_conn()
        conn.execute("DELETE FROM reference_tags WHERE reference_id = ?", (id,))
        flash(f"Deleted {id}", "success")
        return redirect(url_for("references_page"))

    @app.route("/references/<id>/tags", methods=["POST"])
    def references_set_tags(id: str):
        if not (REFERENCES_UPLOAD_DIR / id).exists():
            abort(404)
        raw = (request.form.get("tags") or "").strip()
        names = [refs_mod.normalise_tag(t) for t in raw.split(",") if t.strip()]
        names = [n for n in names if n]
        refs_mod.set_tags(id, names)
        if wants_json():
            return ok({"id": id, "tags": sorted(refs_mod.get_tags(id))})
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
        spa = serve_spa_or_fallback()
        if spa is not None:
            return spa
        if wants_json():
            return ok({
                "brands": brand_mod.list_brands(),
                "active_brand": brand_mod.get_active_brand(),
            })
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
            if wants_json():
                return err(str(exc), code=400)
            flash(str(exc), "error")
            return redirect(url_for("brand_page"))
        if request.form.get("set_active"):
            brand_mod.set_active_brand(saved["id"])
        if wants_json():
            return ok({"brand": saved, "active": bool(request.form.get("set_active"))})
        if request.form.get("set_active"):
            flash(f"Saved '{saved['name']}' and set as active brand.", "success")
        else:
            flash(f"Saved '{saved['name']}'.", "success")
        return redirect(url_for("brand_page"))

    @app.route("/brand/<int:brand_id>/delete", methods=["POST"])
    def brand_delete(brand_id: int):
        brand_mod.delete_brand(brand_id)
        if wants_json():
            return ok({"deleted": brand_id})
        flash("Brand deleted.", "success")
        return redirect(url_for("brand_page"))

    @app.route("/brand/<int:brand_id>/activate", methods=["POST"])
    def brand_activate(brand_id: int):
        try:
            brand_mod.set_active_brand(brand_id)
        except ValueError as exc:
            if wants_json():
                return err(str(exc), code=400)
            flash(str(exc), "error")
        else:
            if wants_json():
                return ok({"active_brand_id": brand_id})
            flash("Active brand updated.", "success")
        return redirect(url_for("brand_page"))

    @app.route("/brand/clear", methods=["POST"])
    def brand_clear():
        brand_mod.clear_active_brand()
        if wants_json():
            return ok({"active_brand_id": None})
        flash("Active brand cleared.", "success")
        return redirect(url_for("brand_page"))

    # ---------- drafts ----------

    @app.route("/drafts/save", methods=["POST"])
    def draft_save():
        draft_id_raw = (request.form.get("draft_id") or "").strip()
        draft_id = int(draft_id_raw) if draft_id_raw else None
        try:
            saved = drafts.save_draft(
                name=request.form.get("name") or "",
                body=request.form.get("body") or "",
                category=request.form.get("category") or "",
                draft_id=draft_id,
                is_favorite=str(request.form.get("is_favorite") or "").lower() in ("1", "true"),
            )
        except ValueError as exc:
            if wants_json():
                return err(str(exc), code=400)
            flash(str(exc), "error")
        else:
            if wants_json():
                return ok({"draft": saved})
            flash("Draft saved.", "success")
        return redirect(request.referrer or url_for("generate_page"))

    @app.route("/drafts/<int:draft_id>/delete", methods=["POST"])
    def draft_delete(draft_id: int):
        drafts.delete_draft(draft_id)
        if wants_json():
            return ok({"deleted": draft_id})
        flash("Draft deleted.", "success")
        return redirect(request.referrer or url_for("generate_page"))

    @app.route("/drafts/<int:draft_id>/favorite", methods=["POST"])
    def draft_favorite(draft_id: int):
        drafts.toggle_favorite(draft_id)
        if request.headers.get("HX-Request"):
            return ("", 204)
        if wants_json():
            return ok({"draft_id": draft_id, "is_favorite": True})
        return redirect(request.referrer or url_for("generate_page"))

    @app.route("/drafts/api")
    def drafts_api():
        query = (request.args.get("draft_query") or "").strip() or None
        category = (request.args.get("draft_category") or "").strip() or None
        favorites_only = request.args.get("favorites_only") == "on"
        items = drafts.list_drafts(
            query=query,
            category=category,
            favorites_only=favorites_only,
            limit=50,
        )
        if wants_json():
            return ok({"drafts": items, "categories": drafts.categories()})
        return render_template("_partials/draft_results.html", drafts=items)

    # ---------- settings ----------

    @app.route("/settings")
    def settings_page():
        spa = serve_spa_or_fallback()
        if spa is not None:
            return spa
        if wants_json():
            return ok({
                "keys": list_keys(),
                "project_root": str(PROJECT_ROOT),
            })
        return render_template(
            "settings.html",
            keys=list_keys(),
            project_root=str(PROJECT_ROOT),
        )

    @app.route("/settings/<env_var>", methods=["POST"])
    def settings_save(env_var: str):
        env_var = _known_env_var_or_404(env_var)
        value = (request.form.get("value") or "").strip()
        if not value:
            if wants_json():
                return err("Value cannot be empty.", code=400)
            flash("Value cannot be empty. Use Delete to remove a key.", "error")
            return redirect(url_for("settings_page"))
        try:
            save_key(env_var, value)
        except ValueError as exc:
            if wants_json():
                return err(str(exc), code=400)
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        if wants_json():
            return ok({"env_var": env_var})
        flash(f"Saved {env_var}", "success")
        return redirect(url_for("settings_page"))

    @app.route("/settings/<env_var>/delete", methods=["POST"])
    def settings_delete(env_var: str):
        env_var = _known_env_var_or_404(env_var)
        try:
            delete_key(env_var)
        except ValueError as exc:
            if wants_json():
                return err(str(exc), code=400)
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        if wants_json():
            return ok({"deleted": env_var})
        flash(f"Deleted {env_var}", "success")
        return redirect(url_for("settings_page"))

    # ---------- error handlers ----------

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404


def _dispatch_generate() -> tuple[dict, int]:
    """Validate the form, kick off the job, and return a payload dict.

    Same logic for the HTML route and the /api/generate route; the caller
    is responsible for rendering.
    """
    prompt = (request.form.get("prompt") or "").strip()
    model = (request.form.get("model") or "auto").strip()
    try:
        duration = int(request.form.get("duration") or 8)
    except ValueError:
        duration = 8
    resolution = (request.form.get("resolution") or "768p").strip()

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

    if not prompt:
        return {"error": "Prompt is required"}, 400
    if model not in jobs.VALID_MODELS:
        return {"error": f"Unknown model: {model}"}, 400
    if resolution not in jobs.VALID_RESOLUTIONS:
        return {"error": f"Unknown resolution: {resolution}"}, 400
    if duration < 1 or duration > 60:
        return {"error": "Duration must be 1-60 seconds"}, 400

    has_fal = bool(get_raw("FAL_API_KEY"))
    has_h3 = bool(get_raw("MINIMAX_API_KEY"))
    if not (has_fal or has_h3):
        return {
            "error": "No API keys configured. Open Settings and add at least one key.",
            "redirect": "/settings",
        }, 400

    ref_pairs = _gather_ref_paths(ref_ids)
    effective_prompt = brand_mod.compose_prompt(prompt, brand_id=brand_id)

    if len(ref_pairs) > 1:
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
        return {
            "kind": "batch",
            "batch_id": batch_id,
            "jobs": [_job_to_json(j) for j in created_jobs],
        }, 200

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
    payload = _job_to_json(job)
    return {"kind": "job", "job": payload, "payload": payload}, 200


# ---------- JSON API (for the React frontend) ----------

def _register_api_routes(app: Flask) -> None:

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "service": "calypso", "version": "0.1.0"})

    @app.route("/api/generate", methods=["POST"])
    def api_generate():
        payload, status_code = _dispatch_generate()
        if status_code != 200:
            return err(payload.get("error", "Failed"), code=status_code)
        return ok(payload)

    @app.route("/api/keys")
    def api_keys():
        keys = [
            {
                "env_var": k.env_var,
                "service": k.service,
                "placeholder": k.placeholder,
                "is_set": k.is_set,
                "masked": k.masked,
            }
            for k in list_keys()
        ]
        return ok({"keys": keys})

    @app.route("/api/keys/<env_var>", methods=["POST"])
    def api_keys_set(env_var: str):
        env_var = _known_env_var_or_404(env_var)
        body = request.get_json(silent=True) or {}
        value = (body.get("value") or request.form.get("value") or "").strip()
        if not value:
            return err("Value cannot be empty.", code=400)
        try:
            save_key(env_var, value)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"env_var": env_var})

    @app.route("/api/keys/<env_var>", methods=["DELETE"])
    def api_keys_delete(env_var: str):
        env_var = _known_env_var_or_404(env_var)
        try:
            delete_key(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"deleted": env_var})

    @app.route("/api/refs")
    def api_refs():
        return ok({
            "refs": refs_mod.list_refs(),
            "tags": refs_mod.all_tags(),
        })

    @app.route("/api/refs", methods=["POST"])
    def api_refs_create():
        file = request.files.get("file")
        if file is None or file.filename == "":
            return err("No file provided.", code=400)
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_REFERENCE_EXTENSIONS:
            return err(f"Unsupported file type: {ext}", code=400)
        REFERENCES_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename).name.replace("/", "_").replace("\\", "_")
        dest = REFERENCES_UPLOAD_DIR / f"{Path(safe_name).stem}_{int(time.time())}{ext}"
        file.save(dest)
        raw_tags = (request.form.get("tags") or "").strip()
        if raw_tags:
            tag_names = [refs_mod.normalise_tag(t) for t in raw_tags.split(",")]
            tag_names = [t for t in tag_names if t]
            if tag_names:
                refs_mod.set_tags(dest.name, tag_names)
        # Re-fetch so we return the canonical row.
        refreshed = next((r for r in refs_mod.list_refs() if r["id"] == dest.name), None)
        return ok({"ref": refreshed})

    @app.route("/api/refs/<id>/tags", methods=["PATCH"])
    def api_refs_set_tags(id: str):
        if not (REFERENCES_UPLOAD_DIR / id).exists():
            abort(404)
        body = request.get_json(silent=True) or {}
        raw = body.get("tags")
        if raw is None:
            raw = request.form.get("tags") or ""
        names = [refs_mod.normalise_tag(t) for t in str(raw).split(",") if t.strip()]
        names = [n for n in names if n]
        refs_mod.set_tags(id, names)
        return ok({"id": id, "tags": sorted(refs_mod.get_tags(id))})

    @app.route("/api/refs/<id>", methods=["DELETE"])
    def api_refs_delete(id: str):
        target = REFERENCES_UPLOAD_DIR / id
        if not target.exists() or not target.is_file():
            abort(404)
        if REFERENCES_UPLOAD_DIR not in target.resolve().parents:
            abort(404)
        target.unlink()
        from app import db as app_db
        conn = app_db.get_conn()
        conn.execute("DELETE FROM reference_tags WHERE reference_id = ?", (id,))
        return ok({"deleted": id})

    @app.route("/api/brands")
    def api_brands():
        return ok({
            "brands": brand_mod.list_brands(),
            "active": brand_mod.get_active_brand(),
        })

    @app.route("/api/brands", methods=["POST"])
    def api_brands_create():
        body = request.get_json(silent=True) or {}
        try:
            saved = brand_mod.save_brand(
                name=body.get("name") or "",
                tagline=body.get("tagline") or "",
                audience=body.get("audience") or "",
                palette=body.get("palette") or "",
                typography=body.get("typography") or "",
                voice=body.get("voice") or "",
                do_examples=body.get("do_examples") or "",
                dont_examples=body.get("dont_examples") or "",
                style_guide=body.get("style_guide") or "",
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        if body.get("set_active") or body.get("make_active"):
            brand_mod.set_active_brand(saved["id"])
        return ok({"brand": saved})

    @app.route("/api/brands/<int:brand_id>", methods=["PATCH"])
    def api_brands_update(brand_id: int):
        body = request.get_json(silent=True) or {}
        try:
            saved = brand_mod.save_brand(
                name=body.get("name") or "",
                tagline=body.get("tagline") or "",
                audience=body.get("audience") or "",
                palette=body.get("palette") or "",
                typography=body.get("typography") or "",
                voice=body.get("voice") or "",
                do_examples=body.get("do_examples") or "",
                dont_examples=body.get("dont_examples") or "",
                style_guide=body.get("style_guide") or "",
                brand_id=brand_id,
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        if body.get("set_active") or body.get("make_active"):
            brand_mod.set_active_brand(saved["id"])
        return ok({"brand": saved})

    @app.route("/api/brands/<int:brand_id>", methods=["DELETE"])
    def api_brands_delete(brand_id: int):
        brand_mod.delete_brand(brand_id)
        return ok({"deleted": brand_id})

    @app.route("/api/brands/<int:brand_id>/activate", methods=["POST"])
    def api_brands_activate(brand_id: int):
        try:
            brand_mod.set_active_brand(brand_id)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"active_brand_id": brand_id})

    @app.route("/api/brands/active", methods=["DELETE"])
    def api_brands_clear_active():
        brand_mod.clear_active_brand()
        return ok({"active_brand_id": None})

    @app.route("/api/drafts")
    def api_drafts_list():
        query = (request.args.get("query") or "").strip() or None
        category = (request.args.get("category") or "").strip() or None
        favorites_only = request.args.get("favorites_only") in ("1", "true", "on")
        items = drafts.list_drafts(
            query=query, category=category,
            favorites_only=favorites_only, limit=100,
        )
        return ok({
            "drafts": items,
            "categories": drafts.categories(),
        })

    @app.route("/api/drafts", methods=["POST"])
    def api_drafts_create():
        body = request.get_json(silent=True) or {}
        try:
            saved = drafts.save_draft(
                name=body.get("name") or "",
                body=body.get("body") or "",
                category=body.get("category") or "",
                is_favorite=bool(body.get("is_favorite")),
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"draft": saved})

    @app.route("/api/drafts/<int:draft_id>", methods=["DELETE"])
    def api_drafts_delete(draft_id: int):
        drafts.delete_draft(draft_id)
        return ok({"deleted": draft_id})

    @app.route("/api/drafts/<int:draft_id>/favorite", methods=["POST"])
    def api_drafts_favorite(draft_id: int):
        drafts.toggle_favorite(draft_id)
        return ok({"draft_id": draft_id})

    @app.route("/api/jobs")
    def api_jobs():
        items = [_job_to_json(j) for j in jobs.list_jobs(limit=100)]
        return ok({"jobs": items})

    @app.route("/api/jobs/<id>")
    def api_jobs_get(id: str):
        job = jobs.get_job(id)
        if job is None:
            abort(404)
        return ok({"job": _job_to_json(job)})

    @app.route("/api/outputs")
    def api_outputs():
        items = _generate_outputs_for_gallery()
        decorated = []
        for item in items:
            link = _job_link_payload(item["id"])
            decorated.append({
                "id": item["id"],
                "rel_url": item["rel_url"],
                "size_mb": item["size_mb"],
                "created": item["created"],
                "prompt": link["prompt"] if link else None,
                "brand_name": link["brand_name"] if link else None,
                "draft_name": link["draft_name"] if link else None,
                "refs": link["refs"] if link else [],
            })
        return ok({"outputs": decorated})


# ---------- SPA static fallback ----------

def _register_spa_fallback(app: Flask) -> None:
    """When web/dist/ exists, serve the SPA bundle at / and any unmatched GET."""

    index_html = WEB_DIST / "index.html"
    assets_dir = WEB_DIST / "assets"

    if not index_html.exists():
        return  # SPA not built yet — fall through to Jinja.

    @app.route("/assets/<path:filename>")
    def spa_assets(filename: str):
        if not assets_dir.exists():
            abort(404)
        return send_from_directory(assets_dir, filename)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa_index(path: str):
        # Never hijack API/static/upload/outputs/HTMX routes.
        blocked_prefixes = (
            "api/", "static/", "outputs/", "references/file/",
            "generate/", "drafts/", "brand/", "settings/", "health",
        )
        first_segment = path.split("/", 1)[0] if path else ""
        if first_segment in blocked_prefixes:
            abort(404)
        return send_from_directory(WEB_DIST, "index.html")


def main() -> None:
    """Entrypoint for `python -m app.server` and `bash run.sh`."""
    import os

    host = os.environ.get("CALYPSO_HOST", "127.0.0.1")
    port = int(os.environ.get("CALYPSO_PORT", "8765"))
    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()