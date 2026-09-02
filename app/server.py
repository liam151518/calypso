"""app/server.py. Flask app for Calypso's local web UI + JSON API.

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
import uuid
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
import app.settings as settings
from app.settings import (
    KNOWN_KEYS,
    delete_key,
    get_raw,
    known_keys_grouped,
    list_custom_keys,
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

    # Phase D: discover + auto-enable built-in extensions. Community
    # extensions live in $CALYPSO_EXTENSIONS_DIR (default ~/.calypso/extensions).
    try:
        from app.extensions import loader as ext_loader

        ext_loader.discover()
        ext_loader.load_builtin_extensions()
        ext_loader.restore_state()
    except Exception:  # noqa: BLE001
        pass

    # Phase F.7: boot the in-process scheduler (single instance per process).
    try:
        from app.marketing import scheduler as m_scheduler
        m_scheduler.start()
    except Exception:  # noqa: BLE001
        pass

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
    """True when the built SPA bundle is present. If it is, page routes
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


def ok(payload: Any | None = None, *, status_code: int | None = None) -> Any:
    """Standard success JSON.

    Returns a bare response for the common 200 case. When `status_code`
    is given (e.g. 201 Created), returns the `(response, code)` tuple
    Flask expects for non-default statuses.
    """
    body: dict[str, Any] = {"ok": True}
    if payload:
        body.update(payload)
    resp = jsonify(body)
    if status_code is None or status_code == 200:
        return resp
    return resp, status_code


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


def _normalize_env_var(env_var: str) -> str:
    """Validate and return the canonical env-var name, or raise ValueError.

    - Trims whitespace.
    - Matches KNOWN_KEYS case-insensitively (returns the canonical form).
    - Otherwise accepts any valid identifier-shaped name so operators can
      save custom keys (e.g. MY_CUSTOM_TOKEN) directly from the UI.
    """
    name = (env_var or "").strip()
    if not name:
        raise ValueError("env_var is required")
    for entry in KNOWN_KEYS:
        if str(entry["env_var"]).lower() == name.lower():
            return str(entry["env_var"])
    if not settings._is_valid_env_var_name(name):
        raise ValueError(
            f"invalid key name {name!r}: use A-Z, 0-9, underscore, no leading digit"
        )
    return name


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
            # Should never happen. Dispatch always returns a dict or a Flask response.
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

    @app.route("/image/submit", methods=["POST"])
    def image_submit():
        from app import image_jobs

        if wants_json():
            return err("Use POST /api/image-generate instead", code=400)
        env = settings._read_env_file(settings.ENV_PATH)
        if not env.get("FAL_API_KEY", "").strip():
            return err("FAL_API_KEY not set", code=400, redirect="/settings")

        prompt = (request.form.get("prompt") or "").strip()
        if not prompt:
            return err("prompt is required", code=400)
        model = request.form.get("model") or "flux-pro/v1.1"
        aspect_ratio = request.form.get("aspect_ratio") or "1:1"
        try:
            num_images = int(request.form.get("num_images") or 1)
        except (TypeError, ValueError):
            num_images = 1
        ref_id = request.form.get("ref_id") or None
        ref_path: str | None = None
        if ref_id:
            ref_path = str(REFERENCES_UPLOAD_DIR / ref_id)

        active_brand = brand_mod.get_active_brand()
        effective_prompt = prompt
        if active_brand and active_brand.get("name"):
            effective_prompt = f"{active_brand['name']} brand. {prompt}"

        job = image_jobs.create_image_job(
            effective_prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            num_images=num_images,
            reference=ref_path,
            ref_ids=[ref_id] if ref_id else [],
        )
        image_jobs.start_image_job(job)
        return render_template("job_block.html", job=job.to_dict())

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

    @app.route("/outputs/images/<path:filename>")
    def outputs_image(filename: str):
        from app.compositor import IMAGES_DIR as _IMAGES_DIR
        return send_from_directory(_IMAGES_DIR, filename)

    @app.route("/outputs/videos/<path:filename>")
    def outputs_video_file(filename: str):
        from app.video_compositor import VIDEOS_DIR as _VIDEOS_DIR
        return send_from_directory(_VIDEOS_DIR, filename)

    @app.route("/outputs/motion/<path:filename>")
    def outputs_motion(filename: str):
        from app.motion.opencv import OpenCVMotionBackend
        # Always serves from the same outputs/motion dir; we instantiate a
        # backend with no `output_dir` so it falls back to its default.
        backend = OpenCVMotionBackend()
        return send_from_directory(backend.output_dir, filename)

    @app.route("/image")
    def image_page():
        spa = serve_spa_or_fallback()
        if spa is not None:
            return spa
        if wants_json():
            from app import models as models_mod

            env = settings._read_env_file(settings.ENV_PATH)
            fal_key = env.get("FAL_API_KEY", "").strip()
            return ok({
                "keys": list_keys(),
                "refs": refs_mod.list_refs(),
                "tags": refs_mod.all_tags(),
                "brands": brand_mod.list_brands(),
                "active_brand": brand_mod.get_active_brand(),
                "models": models_mod.list_models(api_key=fal_key or None),
                "defaults": {
                    "image": models_mod.default_image_model_id(),
                },
                "recent_jobs": [],
            })
        return render_template(
            "image.html",
            keys=list_keys(),
            references=_references_for_library(),
            all_tags=_all_tags_for_filter(),
            active_brand=brand_mod.get_active_brand(),
            brands=brand_mod.list_brands(),
        )

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
        try:
            env_var = _normalize_env_var(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
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
        try:
            env_var = _normalize_env_var(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
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

    # ---------- Phase A: pipeline routes (Jinja fallback) ----------
    @app.route("/pipelines")
    def pipelines_index():
        from app import node_schema as ns_mod
        from app import pipelines as pl_mod
        return render_template(
            "pipelines.html",
            pipelines=pl_mod.list_pipelines(),
            schemas=ns_mod.all_schemas(),
        )

    @app.route("/pipelines/<int:pid>")
    def pipelines_detail(pid: int):
        from app import node_schema as ns_mod
        from app import pipelines as pl_mod
        p = pl_mod.get_pipeline(pid)
        if not p:
            abort(404)
        runs = pl_mod.list_runs(pid, limit=20)
        return render_template(
            "pipelines.html",
            pipelines=pl_mod.list_pipelines(),
            schemas=ns_mod.all_schemas(),
            active=p,
            runs=runs,
        )


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

    @app.route("/api/models")
    def api_models():
        from app import models as models_mod

        env = settings._read_env_file(settings.ENV_PATH)
        fal_key = env.get("FAL_API_KEY", "").strip()
        return ok({
            "models": models_mod.list_models(api_key=fal_key or None),
            "defaults": {
                "video": models_mod.default_video_model_id(),
                "image": models_mod.default_image_model_id(),
            },
        })

    @app.route("/api/cost-estimate", methods=["POST"])
    def api_cost_estimate():
        from app import models as models_mod

        body = request.get_json(silent=True) or {}
        model_id = str(body.get("model") or "auto")
        est = models_mod.estimate_cost(
            model_id,
            duration=body.get("duration"),
            resolution=body.get("resolution"),
            aspect_ratio=body.get("aspect_ratio"),
            num_images=int(body.get("num_images") or 1),
        )
        return ok({"estimate": est})

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
                "group": k.group,
                "required": k.required,
                "docs_url": k.docs_url,
                "description": k.description,
                "is_set": k.is_set,
                "masked": k.masked,
                "is_custom": False,
            }
            for k in list_keys()
        ]
        custom = [
            {
                "env_var": k.env_var,
                "service": k.service,
                "placeholder": k.placeholder,
                "group": k.group,
                "required": k.required,
                "docs_url": k.docs_url,
                "description": k.description,
                "is_set": k.is_set,
                "masked": k.masked,
                "is_custom": True,
            }
            for k in list_custom_keys()
        ]
        groups = [
            {"name": name, "keys": [k["env_var"] for k in entries]}
            for name, entries in known_keys_grouped()
        ]
        return ok({"keys": keys, "custom": custom, "groups": groups})

    @app.route("/api/keys/<env_var>", methods=["POST"])
    def api_keys_set(env_var: str):
        try:
            env_var = _normalize_env_var(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
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
        try:
            env_var = _normalize_env_var(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
        try:
            delete_key(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"deleted": env_var})

    @app.route("/api/keys/<env_var>/test", methods=["POST"])
    def api_keys_test(env_var: str):
        """Lightweight sanity check: the key must be present, non-empty, and
        structurally valid (not all whitespace, not a placeholder, etc.).

        Returns 200 if the key looks usable, 400 with a reason otherwise.
        We deliberately don't call out to third-party APIs from the test
        endpoint to keep credentials local.
        """
        try:
            env_var = _normalize_env_var(env_var)
        except ValueError as exc:
            return err(str(exc), code=400)
        raw = get_raw(env_var).strip()
        if not raw:
            return err(f"{env_var} is not set.", code=400)
        if len(raw) < 4:
            return err(f"{env_var} looks too short — double-check you pasted the full value.", code=400)
        if raw.lower() in {"changeme", "todo", "your-key-here", "xxx", "xxxx"}:
            return err(f"{env_var} still has the placeholder value.", code=400)
        return ok({"env_var": env_var, "ok": True})

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

    @app.route("/api/image-generate", methods=["POST"])
    def api_image_generate():
        from app import image_jobs

        body = request.get_json(silent=True) or request.form.to_dict()
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return err("prompt is required")
        env = settings._read_env_file(settings.ENV_PATH)
        if not env.get("FAL_API_KEY", "").strip():
            return err("FAL_API_KEY not set", code=400, redirect="/settings")

        # If a brand is active, prepend it like video jobs do.
        active_brand = brand_mod.get_active_brand()
        effective_prompt = prompt
        if active_brand and active_brand.get("name"):
            effective_prompt = f"{active_brand['name']} brand. {prompt}"

        model = body.get("model") or "flux-pro/v1.1"
        aspect_ratio = body.get("aspect_ratio") or "1:1"
        try:
            num_images = int(body.get("num_images") or 1)
        except (TypeError, ValueError):
            num_images = 1

        ref_id = body.get("ref_id")
        ref_path: str | None = None
        ref_ids: list[str] = []
        if ref_id:
            ref_path = str(REFERENCES_UPLOAD_DIR / ref_id)
            ref_ids = [str(ref_id)]
            if not Path(ref_path).exists():
                return err(f"reference {ref_id} not found", code=404)

        job = image_jobs.create_image_job(
            effective_prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            num_images=num_images,
            reference=ref_path,
            ref_ids=ref_ids,
        )
        image_jobs.start_image_job(job)
        return ok({"job": job.to_dict()})

    @app.route("/api/image-jobs")
    def api_image_jobs():
        from app import image_jobs

        return ok({"jobs": [j.to_dict() for j in image_jobs.list_image_jobs(limit=100)]})

    @app.route("/api/image-jobs/<id>")
    def api_image_jobs_get(id: str):
        from app import image_jobs

        job = image_jobs.get_image_job(id)
        if job is None:
            abort(404)
        return ok({"job": job.to_dict()})

    @app.route("/outputs/file/<job_id>/<path:filename>")
    def api_outputs_file(job_id: str, filename: str):
        """Serve a generated image or video file by job_id.

        Used by the SPA's <img> / <video src> tags. Path traversal is guarded
        by resolving the path under OUTPUTS_DIR and refusing anything that
        climbs out.
        """
        target = (jobs.OUTPUTS_DIR / job_id / filename).resolve()
        try:
            target.relative_to(jobs.OUTPUTS_DIR.resolve())
        except ValueError:
            abort(404)
        if not target.exists() or not target.is_file():
            abort(404)
        return send_from_directory(target.parent, target.name)

    @app.route("/api/image-outputs")
    def api_image_outputs():
        from app import image_jobs

        items = []
        for job in image_jobs.list_image_jobs(limit=100):
            if job.status != "succeeded" or not job.output_paths:
                continue
            first = Path(job.output_paths[0])
            size_mb = round(first.stat().st_size / (1024 * 1024), 2) if first.exists() else 0
            rel = f"/outputs/file/{first.parent.name}/{first.name}"
            items.append({
                "id": job.job_id,
                "job_id": job.job_id,
                "rel_url": rel,
                "size_mb": size_mb,
                "created": job.created_at,
                "prompt": job.prompt,
                "model": job.model,
                "aspect_ratio": job.aspect_ratio,
                "num_images": job.num_images,
                "cost_usd": job.cost_usd,
            })
        return ok({"outputs": items})

    # ---------- Phase A: pipelines ----------

    from app import node_schema as node_schema_mod
    from app import pipelines as pipelines_mod

    @app.route("/api/pipelines/node-schemas")
    def api_pipeline_node_schemas():
        return ok({"schemas": node_schema_mod.all_schemas(),
                    "categories": node_schema_mod.node_categories()})

    @app.route("/api/pipelines")
    def api_list_pipelines():
        return ok({"pipelines": pipelines_mod.list_pipelines()})

    @app.route("/api/pipelines", methods=["POST"])
    def api_create_pipeline():
        body = request.get_json(silent=True) or {}
        try:
            p = pipelines_mod.create_pipeline(
                body.get("name", ""),
                description=body.get("description", ""),
                nodes=body.get("nodes", []),
                edges=body.get("edges", []),
                max_workers=int(body.get("max_workers", 2) or 2),
                enabled=bool(body.get("enabled", True)),
            )
        except pipelines_mod.PipelineError as exc:
            return err(str(exc), code=400)
        return ok({"pipeline": p}), 201

    @app.route("/api/pipelines/<int:pid>")
    def api_get_pipeline(pid: int):
        p = pipelines_mod.get_pipeline(pid)
        if not p:
            return err("not found", code=404)
        return ok({"pipeline": p})

    @app.route("/api/pipelines/<int:pid>", methods=["PATCH"])
    def api_update_pipeline(pid: int):
        body = request.get_json(silent=True) or {}
        try:
            p = pipelines_mod.update_pipeline(pid, **body)
        except pipelines_mod.PipelineError as exc:
            return err(str(exc), code=400)
        if not p:
            return err("not found", code=404)
        return ok({"pipeline": p})

    @app.route("/api/pipelines/<int:pid>", methods=["DELETE"])
    def api_delete_pipeline(pid: int):
        ok_flag = pipelines_mod.delete_pipeline(pid)
        if not ok_flag:
            return err("not found", code=404)
        return ok({"deleted": True})

    @app.route("/api/pipelines/<int:pid>/run", methods=["POST"])
    def api_run_pipeline(pid: int):
        body = request.get_json(silent=True) or {}
        try:
            run = pipelines_mod.run_pipeline(
                pid,
                triggered_by=body.get("triggered_by", "api"),
                max_workers=body.get("max_workers"),
            )
        except pipelines_mod.PipelineError as exc:
            return err(str(exc), code=400)
        return ok({"run": run}), 202

    @app.route("/api/pipelines/<int:pid>/runs")
    def api_list_pipeline_runs(pid: int):
        return ok({"runs": pipelines_mod.list_runs(pid)})

    @app.route("/api/pipelines/runs/<int:run_id>")
    def api_get_pipeline_run(run_id: int):
        run = pipelines_mod.get_run(run_id)
        if not run:
            return err("not found", code=404)
        return ok({"run": run})

    # ---------- Phase C: Studio ----------
    from app import agents as agents_mod

    # ---------- Phase D: extensions ----------
    from app.extensions import loader as ext_loader

    @app.route("/api/extensions")
    def api_list_extensions():
        ext_loader.discover()
        return ok({"extensions": ext_loader.list_extensions()})

    @app.route("/api/extensions/<ext_id>/enable", methods=["POST"])
    def api_enable_extension(ext_id: str):
        body = request.get_json(silent=True) or {}
        secret = body.get("secret") or ""
        if not ext_loader.enable(ext_id, secret=secret or None):
            return err("could not enable extension (not found or bad signature)", code=400)
        return ok({"id": ext_id, "enabled": True})

    @app.route("/api/extensions/<ext_id>/disable", methods=["POST"])
    def api_disable_extension(ext_id: str):
        if not ext_loader.disable(ext_id):
            return err("not enabled", code=400)
        return ok({"id": ext_id, "enabled": False})

    @app.route("/api/studio/run", methods=["POST"])
    def api_studio_run():
        body = request.get_json(silent=True) or {}
        brief = (body.get("brief") or "").strip()
        if not brief:
            return err("brief is required", code=400)
        try:
            brand = brand_mod.get_active_brand() or {}
        except Exception:  # noqa: BLE001
            brand = {}
        refs_list: list[dict] = []
        try:
            raw_refs = refs_mod.list_refs() or []
            refs_list = [
                {"id": r.get("filename"), "tags": r.get("tags", []), "path": r.get("path")}
                for r in raw_refs
            ]
        except Exception:  # noqa: BLE001
            pass
        try:
            result = agents_mod.run_studio(brief, brand=brand, references=refs_list)
        except agents_mod.StudioError as exc:
            return err(str(exc), code=400)
        # Auto-persist the resulting pipeline so the user can run it later.
        pipe_art = result["artifacts"].get("pipeline") or {}
        saved_pid = None
        if pipe_art.get("nodes"):
            try:
                p = pipelines_mod.create_pipeline(
                    pipe_art.get("name", "studio"),
                    description=pipe_art.get("description", ""),
                    nodes=pipe_art["nodes"],
                    edges=pipe_art["edges"],
                    max_workers=int(pipe_art.get("max_workers", 2) or 2),
                )
                saved_pid = p["id"]
            except pipelines_mod.PipelineError:
                saved_pid = None
        return ok({
            "log": result["log"],
            "artifacts": result["artifacts"],
            "spent_usd": result["spent_usd"],
            "pipeline_id": saved_pid,
        })

    # ---------- Phase F: Marketing surface ----------
    from app.marketing import (
        analytics as m_analytics,
        campaigns as m_campaigns,
        compliance as m_compliance,
        contacts as m_contacts,
        pages as m_pages,
        scheduler as m_scheduler,
        social as m_social,
    )

    # --- Contacts ---
    @app.route("/api/contacts")
    def api_list_contacts():
        items = m_contacts.list_contacts(
            tag=request.args.get("tag"),
            query=request.args.get("q"),
            subscribed_only=request.args.get("subscribed_only") == "1",
        )
        return ok({"contacts": [c.to_dict() for c in items]})

    @app.route("/api/contacts", methods=["POST"])
    def api_create_contact():
        body = request.get_json(silent=True) or {}
        try:
            cid = m_contacts.upsert_contact(m_contacts.Contact(
                id=None,
                email=body.get("email", ""),
                first_name=body.get("first_name", ""),
                last_name=body.get("last_name", ""),
                phone=body.get("phone", ""),
                tags=body.get("tags") or [],
                source=body.get("source", "api"),
                consent_marketing=bool(body.get("consent_marketing")),
            ))
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"id": cid}, status_code=201)

    @app.route("/api/contacts/<int:cid>", methods=["DELETE"])
    def api_delete_contact(cid: int):
        m_contacts.delete_contact(cid)
        return ok({"id": cid})

    @app.route("/api/contacts/unsubscribe", methods=["POST"])
    def api_unsubscribe_contact():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip().lower()
        token = body.get("token") or ""
        return ok(m_compliance.unsubscribe_via_token(email, token))

    # --- Campaigns ---
    @app.route("/api/campaigns")
    def api_list_campaigns():
        items = m_campaigns.list_campaigns(status=request.args.get("status"))
        return ok({"campaigns": [c.to_dict() for c in items]})

    @app.route("/api/campaigns", methods=["POST"])
    def api_create_campaign():
        body = request.get_json(silent=True) or {}
        try:
            cid = m_campaigns.create_campaign(m_campaigns.Campaign(
                id=None,
                name=body.get("name", ""),
                subject=body.get("subject", ""),
                channel=body.get("channel", "email"),
                status="draft",
                audience_query=body.get("audience_query", ""),
                send_at=body.get("send_at"),
                body_html=body.get("body_html", ""),
                body_text=body.get("body_text", ""),
            ))
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"id": cid}, status_code=201)

    @app.route("/api/campaigns/<int:cid>", methods=["PATCH"])
    def api_update_campaign(cid: int):
        body = request.get_json(silent=True) or {}
        try:
            m_campaigns.update_campaign(cid, **body)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"id": cid})

    @app.route("/api/campaigns/<int:cid>", methods=["DELETE"])
    def api_delete_campaign(cid: int):
        m_campaigns.delete_campaign(cid)
        return ok({"id": cid})

    @app.route("/api/campaigns/<int:cid>/send", methods=["POST"])
    def api_send_campaign(cid: int):
        camp = m_campaigns.get_campaign(cid)
        if not camp:
            return err("not found", code=404)
        if camp.status not in ("draft", "scheduled", "failed"):
            return err(f"cannot send status={camp.status}", code=400)
        m_campaigns.update_campaign(cid, status="sending")
        if camp.send_at:
            m_scheduler.schedule(
                f"campaign:{cid}", "send_campaign", float(camp.send_at),
                payload={"campaign_id": cid},
            )
            return ok({"scheduled": True})
        # Immediate send. Invoke handler directly.
        from app.marketing.scheduler import _HANDLERS
        handler = _HANDLERS.get("send_campaign")
        if handler:
            handler({"campaign_id": cid})
        return ok({"sent": True})

    # --- Landing pages ---
    @app.route("/api/pages")
    def api_list_pages():
        items = m_pages.list_pages(
            published_only=request.args.get("published_only") == "1",
        )
        return ok({"pages": [p.to_dict() for p in items]})

    @app.route("/api/pages", methods=["POST"])
    def api_create_page():
        body = request.get_json(silent=True) or {}
        try:
            pid = m_pages.create_page(m_pages.LandingPage(
                id=None,
                slug=body.get("slug", ""),
                title=body.get("title", ""),
                body_html=body.get("body_html", ""),
                form_schema=body.get("form_schema") or {},
                consent_text=body.get("consent_text", ""),
                published=bool(body.get("published")),
            ))
        except Exception as exc:  # noqa: BLE001
            return err(str(exc), code=400)
        return ok({"id": pid}, status_code=201)

    @app.route("/api/pages/<int:pid>", methods=["PATCH"])
    def api_update_page(pid: int):
        body = request.get_json(silent=True) or {}
        m_pages.update_page(pid, **body)
        return ok({"id": pid})

    @app.route("/api/pages/<int:pid>", methods=["DELETE"])
    def api_delete_page(pid: int):
        m_pages.delete_page(pid)
        return ok({"id": pid})

    # --- Social ---
    @app.route("/api/social")
    def api_list_social():
        items = m_social.list_posts(
            platform=request.args.get("platform"),
            status=request.args.get("status"),
        )
        return ok({"posts": [p.to_dict() for p in items]})

    @app.route("/api/social", methods=["POST"])
    def api_create_social():
        body = request.get_json(silent=True) or {}
        try:
            pid = m_social.create_post(m_social.SocialPost(
                id=None,
                platform=body.get("platform", "x"),
                account=body.get("account", ""),
                body=body.get("body", ""),
                media_url=body.get("media_url", ""),
                scheduled_at=body.get("scheduled_at"),
                status="draft",
            ))
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"id": pid}, status_code=201)

    @app.route("/api/social/<int:pid>", methods=["PATCH"])
    def api_update_social(pid: int):
        body = request.get_json(silent=True) or {}
        try:
            m_social.update_post(pid, **body)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"id": pid})

    @app.route("/api/social/<int:pid>", methods=["DELETE"])
    def api_delete_social(pid: int):
        m_social.delete_post(pid)
        return ok({"id": pid})

    # --- Analytics ---
    @app.route("/api/analytics/aggregate")
    def api_analytics_aggregate():
        try:
            days = int(request.args.get("days", "7"))
        except ValueError:
            days = 7
        since = time.time() - days * 86400
        agg = m_analytics.aggregate(since, kind=request.args.get("kind"))
        return ok({"aggregate": agg, "since": since, "days": days})

    @app.route("/api/analytics/events", methods=["POST"])
    def api_record_event():
        body = request.get_json(silent=True) or {}
        try:
            eid = m_analytics.record(
                kind=body.get("kind", ""),
                ref=body.get("ref", ""),
                value_num=float(body.get("value_num", 0)),
                metadata=body.get("metadata") or {},
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"id": eid}, status_code=201)

    # --- Scheduler ---
    @app.route("/api/scheduler/jobs")
    def api_list_jobs():
        return ok({"jobs": m_scheduler.list_jobs(
            status=request.args.get("status"),
        )})

    @app.route("/api/scheduler/jobs", methods=["POST"])
    def api_schedule_job():
        body = request.get_json(silent=True) or {}
        try:
            jid = m_scheduler.schedule(
                name=body.get("name", "job"),
                kind=body.get("kind", ""),
                run_at=float(body.get("run_at", time.time())),
                payload=body.get("payload") or {},
            )
        except (ValueError, TypeError) as exc:
            return err(str(exc), code=400)
        return ok({"id": jid}, status_code=201)

    @app.route("/api/scheduler/jobs/<int:jid>", methods=["DELETE"])
    def api_cancel_job(jid: int):
        m_scheduler.cancel(jid)
        return ok({"id": jid})

    # --- Compliance ---
    @app.route("/api/compliance/export", methods=["POST"])
    def api_compliance_export():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip().lower()
        return ok(m_compliance.export_user_data(email))

    @app.route("/api/compliance/erase", methods=["POST"])
    def api_compliance_erase():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip().lower()
        return ok(m_compliance.erase_user_data(email))

    # ====================================================================
    # Phase A — Brand Poster surface: templates, products, render, filters
    # ====================================================================
    from app import templates as tpl_mod
    from app import products as prod_mod
    from app import filters as filters_api
    from app import compositor as comp_mod
    from app.utils import (
        TemplateError as _TemplateError,
        ASPECT_RATIOS as _ASPECT_RATIOS,
        LAYER_TYPES as _LAYER_TYPES,
    )

    # ---- templates ----

    @app.route("/api/templates", methods=["GET"])
    def api_templates_list():
        brand_id = request.args.get("brand_id", type=int)
        category = request.args.get("category") or None
        items = tpl_mod.list_templates(brand_id=brand_id, category=category)
        return jsonify({"templates": items, "aspect_ratios": list(_ASPECT_RATIOS), "layer_types": list(_LAYER_TYPES)})

    @app.route("/api/templates/<int:template_id>", methods=["GET"])
    def api_templates_get(template_id: int):
        item = tpl_mod.get_template(template_id)
        if item is None:
            abort(404)
        return jsonify({"template": item})

    @app.route("/api/templates", methods=["POST"])
    def api_templates_create():
        body = request.get_json(silent=True) or {}
        brand_id = body.get("brand_id")
        try:
            tid = tpl_mod.create_template(body, brand_id=int(brand_id) if brand_id else None)
        except _TemplateError as exc:
            return err(str(exc), code=400)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"template_id": tid}, status_code=201)

    @app.route("/api/templates/<int:template_id>", methods=["PUT", "PATCH"])
    def api_templates_update(template_id: int):
        body = request.get_json(silent=True) or {}
        force = bool(body.get("force"))
        try:
            ok_flag = tpl_mod.update_template(template_id, body, force=force)
        except _TemplateError as exc:
            return err(str(exc), code=400)
        return ok({"updated": ok_flag}) if ok_flag else err("not found", code=404)

    @app.route("/api/templates/<int:template_id>", methods=["DELETE"])
    def api_templates_delete(template_id: int):
        force = request.args.get("force") in ("1", "true", "yes")
        try:
            ok_flag = tpl_mod.delete_template(template_id, force=force)
        except _TemplateError as exc:
            return err(str(exc), code=400)
        return ok({"deleted": ok_flag}) if ok_flag else err("not found", code=404)

    @app.route("/api/templates/<int:template_id>/duplicate", methods=["POST"])
    def api_templates_duplicate(template_id: int):
        body = request.get_json(silent=True) or {}
        new_name = (body.get("name") or "").strip() or f"Copy {template_id}"
        try:
            new_id = tpl_mod.duplicate_template(template_id, new_name)
        except _TemplateError as exc:
            return err(str(exc), code=400)
        return ok({"template_id": new_id}, status_code=201)

    # ---- products ----

    @app.route("/api/products", methods=["GET"])
    def api_products_list():
        brand_id = request.args.get("brand_id", type=int)
        category = request.args.get("category") or None
        collection = request.args.get("collection") or None
        tag = request.args.get("tag") or None
        items = prod_mod.list_products(brand_id=brand_id, category=category, collection=collection, tag=tag)
        return jsonify({"products": items})

    @app.route("/api/products/<int:product_id>", methods=["GET"])
    def api_products_get(product_id: int):
        item = prod_mod.get_product(product_id)
        if item is None:
            abort(404)
        return jsonify({"product": item, "variants": prod_mod.list_variants(product_id)})

    @app.route("/api/products", methods=["POST"])
    def api_products_create():
        body = request.get_json(silent=True) or {}
        try:
            pid = prod_mod.create_product(
                body.get("brand_id"),
                name=body.get("name") or "",
                price=body.get("price"),
                category=body.get("category"),
                collection=body.get("collection"),
                description=body.get("description"),
                image_path=body.get("image_path"),
                tags=body.get("tags") or [],
                launch_date=body.get("launch_date"),
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"product_id": pid}, status_code=201)

    @app.route("/api/products/<int:product_id>", methods=["PUT", "PATCH"])
    def api_products_update(product_id: int):
        body = request.get_json(silent=True) or {}
        ok_flag = prod_mod.update_product(product_id, body)
        return ok({"updated": ok_flag}) if ok_flag else err("not found", code=404)

    @app.route("/api/products/<int:product_id>", methods=["DELETE"])
    def api_products_delete(product_id: int):
        ok_flag = prod_mod.delete_product(product_id)
        return ok({"deleted": ok_flag}) if ok_flag else err("not found", code=404)

    @app.route("/api/products/import", methods=["POST"])
    def api_products_import():
        body = request.get_json(silent=True) or {}
        brand_id = body.get("brand_id")
        if "csv" in body:
            res = prod_mod.import_csv(int(brand_id) if brand_id else None, body["csv"] or "")
        else:
            res = prod_mod.bulk_import(int(brand_id) if brand_id else None, body.get("rows") or [])
        return ok(res, status_code=201)

    @app.route("/api/products/<int:product_id>/cutout", methods=["POST"])
    def api_products_cutout(product_id: int):
        regen = request.args.get("regenerate") in ("1", "true", "yes") or bool(
            (request.get_json(silent=True) or {}).get("regenerate")
        )
        try:
            path = prod_mod.get_cutout(product_id, regenerate=regen)
        except (ValueError, FileNotFoundError) as exc:
            return err(str(exc), code=400)
        except RuntimeError as exc:
            return err(str(exc), code=500)
        return ok({"cutout_path": path})

    # ---- filters ----

    @app.route("/api/filters", methods=["GET"])
    def api_filters_list():
        return jsonify({"presets": filters_api.list_presets(), "user": filters_api.list_user_presets()})

    @app.route("/api/filters/preview", methods=["POST"])
    def api_filters_preview():
        body = request.get_json(silent=True) or {}
        img_path = body.get("image_path")
        if not img_path:
            return err("image_path required", code=400)
        from pathlib import Path
        p = Path(img_path)
        if not p.exists():
            p = (Path(__file__).resolve().parent.parent / img_path).resolve()
        if not p.exists():
            return err(f"image not found: {img_path}", code=404)
        settings = body.get("settings") or body.get("preset_settings") or {}
        try:
            out_path = filters_api.preview(p, settings)
        except Exception as exc:  # noqa: BLE001
            return err(str(exc), code=500)
        return ok({"preview_path": str(out_path)})

    # ---- render ----

    @app.route("/api/render", methods=["POST"])
    def api_render():
        body = request.get_json(silent=True) or {}
        template_id = body.get("template_id")
        if template_id is None:
            return err("template_id required", code=400)
        job_id = body.get("job_id") or f"render_{uuid.uuid4().hex[:12]}"
        try:
            res = comp_mod.render(
                int(template_id),
                product_id=body.get("product_id"),
                layer_overrides=body.get("layer_overrides"),
                filter_name=body.get("filter"),
                aspect_ratio=body.get("aspect_ratio"),
                intensity=float(body.get("intensity") or 1.0),
                brand_id=body.get("brand_id"),
                job_id=job_id,
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok(
            {
                "output_id": res.output_id,
                "file_path": res.file_path,
                "cost_usd": res.cost_usd,
                "cached_background": res.cached_background,
                "elapsed_seconds": res.elapsed_seconds,
                "job_id": job_id,
            },
            status_code=201,
        )

    @app.route("/api/render/batch", methods=["POST"])
    def api_render_batch():
        body = request.get_json(silent=True) or {}
        template_id = body.get("template_id")
        product_ids = body.get("product_ids") or []
        if template_id is None or not product_ids:
            return err("template_id and product_ids required", code=400)
        results = comp_mod.render_batch(
            template_id=int(template_id),
            product_ids=[int(p) for p in product_ids],
            layer_overrides=body.get("layer_overrides"),
            filter_name=body.get("filter"),
            intensity=float(body.get("intensity") or 1.0),
        )
        return ok(
            {
                "renders": [
                    {
                        "output_id": r.output_id,
                        "file_path": r.file_path,
                        "cost_usd": r.cost_usd,
                    }
                    for r in results
                ]
            }
        )

    # ---- bootstrap built-ins on first hit ----

    @app.route("/api/templates/boot-builtins", methods=["POST"])
    def api_templates_boot_builtins():
        inserted = tpl_mod.load_builtins()
        return ok({"inserted": inserted})

    # ---- outputs (gallery) ----

    @app.route("/api/outputs/images", methods=["GET"])
    def api_outputs_images():
        from app import db as app_db
        conn = app_db.get_conn()
        rows = conn.execute(
            "SELECT id, brand_id, product_id, template_id, type, file_path, "
            "aspect_ratio, filter_applied, status, cost_usd, created_at "
            "FROM outputs WHERE type = 'image' ORDER BY id DESC LIMIT 200"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                rel = f"/outputs/images/{Path(d['file_path']).name}"
                d["rel_url"] = rel
            except Exception:  # noqa: BLE001
                d["rel_url"] = None
            out.append(d)
        return jsonify({"outputs": out})

    # ====================================================================
    # Phase D — Video pipeline: render_video, one_shot, UGC templates
    # ====================================================================

    @app.route("/api/video/templates", methods=["GET"])
    def api_video_templates():
        from app import video_compositor as vc
        names = vc.list_ugc_templates()
        return ok({"templates": [
            {"name": n, "template": vc.load_ugc_template(n)} for n in names
        ]})

    # ---- Phase E: motion graphics ----
    @app.route("/api/motion/backends", methods=["GET"])
    def api_motion_backends():
        from app import motion as motion_mod
        backend = motion_mod.get_backend()
        return ok({"active": backend.name, "available": backend.available()})

    @app.route("/api/motion/render", methods=["POST"])
    def api_motion_render():
        from app import motion as motion_mod
        body = request.get_json(silent=True) or {}
        try:
            kind = str(body.get("kind") or "")
            duration_s = float(body.get("duration_s") or 1.0)
            fps = int(body.get("fps") or 30)
            canvas_w = int(body.get("canvas_w") or 1080)
            canvas_h = int(body.get("canvas_h") or 1920)
        except (TypeError, ValueError) as exc:
            return err(f"invalid input: {exc}", code=400)
        backend_name = body.get("backend")
        try:
            backend = motion_mod.get_backend(backend_name)
        except (RuntimeError, ValueError) as exc:
            return err(str(exc), code=400)
        try:
            clip = backend.generate(motion_mod.MotionRequest(
                kind=kind,
                params=dict(body.get("params") or {}),
                duration_s=duration_s,
                fps=fps,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
            ))
        except ValueError as exc:
            return err(str(exc), code=400)
        rels = []
        for p in clip.frames:
            try:
                rels.append(f"/outputs/motion/{Path(p).name}")
            except Exception:  # noqa: BLE001
                rels.append(None)
        return ok({
            "backend": clip.backend,
            "kind": clip.kind,
            "frames": rels,
            "duration_s": clip.duration_s,
        })

    # ====================================================================
    # Phase F — Studio Pro: brand-poster multi-agent surface
    # ====================================================================

    @app.route("/api/studio-pro/generate", methods=["POST"])
    def api_studio_pro_generate():
        from app.studio_pro import StudioProBrief, run_studio_pro
        from app import brand as brand_mod
        from app import templates as tpl_mod

        body = request.get_json(silent=True) or {}
        brief_text = str(body.get("brief") or "").strip()
        if not brief_text:
            return err("brief required", code=400)
        try:
            product_id = int(body.get("product_id") or 0) or None
            brand_id = body.get("brand_id")
            brand_id = int(brand_id) if brand_id is not None else None
            budget = float(body.get("budget_usd") or 5.0)
            duration_s = body.get("duration_s")
            duration_s = int(duration_s) if duration_s is not None else None
        except (TypeError, ValueError) as exc:
            return err(f"invalid input: {exc}", code=400)
        platforms = body.get("platforms") or ["instagram"]
        audience = body.get("audience")
        brand = brand_mod.get_brand(brand_id) if brand_id else brand_mod.get_active_brand()
        templates = tpl_mod.list_templates(brand_id=brand_id or None,
                                             include_builtin=True)
        product = None
        if product_id:
            try:
                from app import products as products_mod
                product = products_mod.get_product(product_id)
            except Exception:  # noqa: BLE001
                product = None
        brief_obj = StudioProBrief(
            brief=brief_text,
            product_id=product_id,
            brand_id=brand_id,
            platforms=list(platforms),
            budget_usd=budget,
            audience=audience,
            duration_s=duration_s,
        )
        run = run_studio_pro(
            brief_obj,
            brand=brand or {},
            product=product,
            templates=templates,
        )
        return ok({
            "run_id": run.run_id,
            "suggestions": run.suggestions,
            "agent_log": run.agent_log,
            "spent_usd": run.spent_usd,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        })

    @app.route("/api/studio-pro/<run_id>/log", methods=["GET"])
    def api_studio_pro_log(run_id: str):
        from app import db as app_db
        conn = app_db.get_conn()
        rows = conn.execute(
            "SELECT id, template_id, layer_overrides_json, rationale_json, "
            "confidence_score, cost_usd, status, created_at "
            "FROM studio_suggestions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("layer_overrides_json", "rationale_json"):
                raw = d.get(k)
                if isinstance(raw, str):
                    try:
                        d[k.replace("_json", "")] = json.loads(raw)
                    except json.JSONDecodeError:
                        d[k.replace("_json", "")] = None
                    d.pop(k, None)
            out.append(d)
        return ok({"suggestions": out, "run_id": run_id})

    @app.route("/api/studio-pro/<int:suggestion_id>/accept", methods=["POST"])
    def api_studio_pro_accept(suggestion_id: int):
        from app import db as app_db
        from app import studio_pro as studio_pro_mod
        from app import compositor as compositor_mod
        from app import templates as tpl_mod

        conn = app_db.get_conn()
        row = conn.execute(
            "SELECT id, run_id, template_id, layer_overrides_json, status "
            "FROM studio_suggestions WHERE id = ?",
            (suggestion_id,),
        ).fetchone()
        if not row:
            return err("suggestion not found", code=404)
        if row["status"] not in ("pending", "accepted"):
            return err(f"cannot accept suggestion in status={row['status']!r}", code=409)
        template_id = int(row["template_id"])
        template = tpl_mod.get_template(template_id)
        if template is None:
            return err("template not found", code=404)
        body = request.get_json(silent=True) or {}
        try:
            product_id = body.get("product_id")
            product_id = int(product_id) if product_id is not None else None
            brand_id = body.get("brand_id")
            brand_id = int(brand_id) if brand_id is not None else None
        except (TypeError, ValueError):
            product_id = None
            brand_id = None
        # Render via the existing Compositor. We don't apply layer_overrides
        # here (Phase F.6 says the SPA can pre-populate the editor instead);
        # but we do mark the suggestion accepted and return an editor URL.
        result = compositor_mod.render(
            template_id,
            product_id=product_id,
            brand_id=brand_id,
        )
        conn.execute(
            "UPDATE studio_suggestions SET status = 'accepted' WHERE id = ?",
            (suggestion_id,),
        )
        conn.commit()
        return ok({
            "suggestion_id": suggestion_id,
            "output_id": result.output_id,
            "editor_url": f"/editor/{template_id}",
            "file_path": result.file_path,
        })

    @app.route("/api/studio-pro/<int:suggestion_id>/schedule", methods=["POST"])
    def api_studio_pro_schedule(suggestion_id: int):
        from app import db as app_db
        from app.marketing import scheduler as sched_mod

        conn = app_db.get_conn()
        row = conn.execute(
            "SELECT id, run_id, template_id, status FROM studio_suggestions "
            "WHERE id = ?",
            (suggestion_id,),
        ).fetchone()
        if not row:
            return err("suggestion not found", code=404)
        if row["status"] not in ("pending", "accepted"):
            return err(f"cannot schedule suggestion in status={row['status']!r}",
                       code=409)
        body = request.get_json(silent=True) or {}
        try:
            run_at = float(body.get("run_at") or time.time() + 3600)
        except (TypeError, ValueError):
            return err("run_at must be a unix timestamp", code=400)
        template_id_raw = row["template_id"]
        if template_id_raw is None:
            return err("suggestion has no template_id; cannot schedule", code=400)
        template_id = int(template_id_raw)
        jid = sched_mod.schedule(
            name=f"Studio Pro suggestion {suggestion_id}",
            kind="publish_output",
            run_at=run_at,
            payload={
                "output_id": 0,
                "template_id": template_id,
                "platform": body.get("platform") or "instagram",
                "suggestion_id": suggestion_id,
            },
        )
        conn.execute(
            "UPDATE studio_suggestions SET status = 'scheduled' WHERE id = ?",
            (suggestion_id,),
        )
        conn.commit()
        return ok({"suggestion_id": suggestion_id, "job_id": jid})

    # ====================================================================
    # Phase G — Presets, automation, config import/export, render events
    # ====================================================================

    @app.route("/api/presets", methods=["GET", "POST"])
    def api_presets():
        from app import presets as presets_mod

        if request.method == "GET":
            brand_id = request.args.get("brand_id", type=int)
            return ok({"presets": presets_mod.list_for_brand(brand_id)})
        body = request.get_json(silent=True) or {}
        try:
            brand_id = body.get("brand_id")
            brand_id = int(brand_id) if brand_id is not None else None
            template_id = body.get("template_id")
            template_id = int(template_id) if template_id is not None else None
        except (TypeError, ValueError):
            return err("invalid id", code=400)
        try:
            pid = presets_mod.create(
                brand_id,
                name=str(body.get("name") or ""),
                description=body.get("description"),
                template_id=template_id,
                layers=body.get("layers") or [],
                filter_name=body.get("filter"),
                caption_template=body.get("caption_template"),
                schedule_settings=body.get("schedule_settings") or {},
                product_filter=body.get("product_filter") or {},
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"preset_id": pid})

    @app.route("/api/presets/<int:preset_id>", methods=["GET", "PATCH", "DELETE"])
    def api_preset_item(preset_id: int):
        from app import presets as presets_mod

        if request.method == "GET":
            p = presets_mod.get(preset_id)
            return ok({"preset": p}) if p else err("not found", code=404)
        if request.method == "DELETE":
            deleted = presets_mod.delete(preset_id)
            return ok({"deleted": deleted}) if deleted else err("not found", code=404)
        body = request.get_json(silent=True) or {}
        try:
            updated = presets_mod.update(preset_id, **body)
        except Exception as exc:  # noqa: BLE001
            return err(str(exc), code=400)
        return ok({"preset": updated}) if updated else err("not found", code=404)

    @app.route("/api/presets/<int:preset_id>/apply", methods=["POST"])
    def api_preset_apply(preset_id: int):
        from app import presets as presets_mod

        body = request.get_json(silent=True) or {}
        product_ids = body.get("product_ids") or []
        if not isinstance(product_ids, list) or not all(
            isinstance(p, int) for p in product_ids
        ):
            return err("product_ids must be a list of ints", code=400)
        result = presets_mod.batch_apply(preset_id, product_ids)
        return ok(result)

    @app.route("/api/automation/rules", methods=["GET", "POST"])
    def api_automation_rules():
        from app import automation as automation_mod

        if request.method == "GET":
            brand_id = request.args.get("brand_id", type=int)
            return ok({"rules": automation_mod.list_rules(brand_id)})
        body = request.get_json(silent=True) or {}
        try:
            brand_id = body.get("brand_id")
            brand_id = int(brand_id) if brand_id is not None else None
        except (TypeError, ValueError):
            return err("invalid brand_id", code=400)
        try:
            rid = automation_mod.create_rule(
                brand_id,
                name=str(body.get("name") or ""),
                trigger=str(body.get("trigger") or ""),
                conditions=list(body.get("conditions") or []),
                action=dict(body.get("action") or {}),
                is_active=bool(body.get("is_active", True)),
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"rule_id": rid})

    @app.route(
        "/api/automation/rules/<int:rule_id>",
        methods=["GET", "PATCH", "DELETE"],
    )
    def api_automation_rule_item(rule_id: int):
        from app import automation as automation_mod

        if request.method == "GET":
            r = automation_mod.get_rule(rule_id)
            return ok({"rule": r}) if r else err("not found", code=404)
        if request.method == "DELETE":
            deleted = automation_mod.delete_rule(rule_id)
            return ok({"deleted": deleted}) if deleted else err("not found", code=404)
        body = request.get_json(silent=True) or {}
        if "is_active" in body:
            ok_set = automation_mod.set_active(rule_id, bool(body["is_active"]))
            if not ok_set:
                return err("not found", code=404)
        return ok({"rule": automation_mod.get_rule(rule_id)})

    @app.route("/api/automation/rules/<int:rule_id>/run", methods=["POST"])
    def api_automation_rule_run(rule_id: int):
        from app import automation as automation_mod

        body = request.get_json(silent=True) or {}
        ids = automation_mod.run_rule(rule_id, payload=body)
        return ok({"output_ids": ids})

    @app.route("/api/config/export", methods=["GET"])
    def api_config_export():
        from app import config_io as config_io_mod
        return ok({"config": config_io_mod.export_config()})

    @app.route("/api/config/import", methods=["POST"])
    def api_config_import():
        from app import config_io as config_io_mod

        body = request.get_json(silent=True) or {}
        doc = body.get("config") or {}
        merge = bool(body.get("merge", True))
        try:
            counts = config_io_mod.import_config(doc, merge=merge)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"imported": counts})

    @app.route("/api/render/<job_id>/events", methods=["GET"])
    def api_render_events(job_id: str):
        from app import ws as ws_mod
        return ws_mod.sse_response(job_id)

    def api_motion_render():
        from app import motion as motion_mod
        body = request.get_json(silent=True) or {}
        try:
            kind = str(body.get("kind") or "")
            duration_s = float(body.get("duration_s") or 1.0)
            fps = int(body.get("fps") or 30)
            canvas_w = int(body.get("canvas_w") or 1080)
            canvas_h = int(body.get("canvas_h") or 1920)
        except (TypeError, ValueError) as exc:
            return err(f"invalid input: {exc}", code=400)
        backend_name = body.get("backend")
        try:
            backend = motion_mod.get_backend(backend_name)
        except (RuntimeError, ValueError) as exc:
            return err(str(exc), code=400)
        try:
            clip = backend.generate(motion_mod.MotionRequest(
                kind=kind,
                params=dict(body.get("params") or {}),
                duration_s=duration_s,
                fps=fps,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
            ))
        except ValueError as exc:
            return err(str(exc), code=400)
        rels = []
        for p in clip.frames:
            try:
                rels.append(f"/outputs/motion/{Path(p).name}")
            except Exception:  # noqa: BLE001
                rels.append(None)
        return ok({
            "backend": clip.backend,
            "kind": clip.kind,
            "frames": rels,
            "duration_s": clip.duration_s,
        })

    @app.route("/api/video/render", methods=["POST"])
    def api_video_render():
        from app import video_compositor as vc
        body = request.get_json(silent=True) or {}
        try:
            template_id = int(body.get("template_id") or 0)
            product_id = body.get("product_id")
            product_id = int(product_id) if product_id is not None else None
            brand_id = body.get("brand_id")
            brand_id = int(brand_id) if brand_id is not None else None
        except (TypeError, ValueError) as exc:
            return err(f"invalid input: {exc}", code=400)
        try:
            result = vc.render_video(
                template_id,
                product_id=product_id,
                brand_id=brand_id,
                audio_track=body.get("audio_track"),
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            return err(str(exc), code=400)
        rel = None
        if result.file_path:
            try:
                rel = f"/outputs/videos/{Path(result.file_path).name}"
            except Exception:  # noqa: BLE001
                rel = None
        return ok({
            "output_id": result.output_id,
            "file_path": result.file_path,
            "rel_url": rel,
            "duration_s": result.duration_s,
            "cost_usd": result.cost_usd,
            "elapsed_seconds": result.elapsed_seconds,
        })

    @app.route("/api/video/one-shot", methods=["POST"])
    def api_video_one_shot():
        from app import one_shot as one_shot_mod
        body = request.get_json(silent=True) or {}
        brief = str(body.get("brief") or "")
        try:
            product_id = int(body.get("product_id") or 0)
        except (TypeError, ValueError):
            return err("product_id required", code=400)
        template_id = body.get("template_id")
        template_id = int(template_id) if template_id is not None else None
        duration_s = int(body.get("duration_s") or 30)
        brand = body.get("brand") or {}
        try:
            result = one_shot_mod.one_shot(
                brief,
                template_id=template_id,
                product_id=product_id,
                brand=brand,
                duration_s=duration_s,
            )
        except (RuntimeError, ValueError) as exc:
            return err(str(exc), code=400)
        rel = None
        if result.file_path:
            try:
                rel = f"/outputs/videos/{Path(result.file_path).name}"
            except Exception:  # noqa: BLE001
                rel = None
        return ok({
            "output_id": result.output_id,
            "file_path": result.file_path,
            "rel_url": rel,
            "duration_s": result.duration_s,
            "cost_usd": result.cost_usd,
            "elapsed_seconds": result.elapsed_seconds,
        })

    # ---- Phase C: captions + feed + scheduler + publisher + telegram ----

    @app.route("/api/captions/generate", methods=["POST"])
    def api_captions_generate():
        from app import captions as captions_mod
        body = request.get_json(silent=True) or {}
        try:
            product_id = int(body.get("product_id") or 0)
            template_id = int(body.get("template_id") or 0)
            brand_id = body.get("brand_id")
            if brand_id is not None:
                brand_id = int(brand_id)
            platform = str(body.get("platform") or "instagram")
            model = str(body.get("model") or "heuristic")
            count = int(body.get("count") or 3)
        except (TypeError, ValueError) as exc:
            return err(f"invalid input: {exc}", code=400)
        # Pull product + template from the DB.
        conn = app_db.get_conn()
        product_row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone() if product_id else None
        template_row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone() if template_id else None
        brand = None
        if brand_id:
            brand = brand.get_brand_v2(brand_id) if hasattr(brand, "get_brand_v2") else None
            # local import avoids circulars
            from app import brand as brand_mod
            brand = brand_mod.get_brand_v2(brand_id)
        product = dict(product_row) if product_row else {"id": product_id}
        template = dict(template_row) if template_row else {"id": template_id}
        try:
            variants = captions_mod.generate(
                product=product,
                template=template,
                brand=brand,
                platform=platform,
                model=model,
                count=count,
            )
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"variants": [v.to_dict() for v in variants]})

    @app.route("/api/captions/select", methods=["POST"])
    def api_captions_select():
        from app import captions as captions_mod
        body = request.get_json(silent=True) or {}
        try:
            output_id = int(body.get("output_id") or 0)
        except (TypeError, ValueError):
            return err("output_id required", code=400)
        variant_dict = body.get("variant") or {}
        try:
            variant = captions_mod.CaptionVariant(
                content=str(variant_dict.get("content", "")),
                hashtags=list(variant_dict.get("hashtags") or []),
                first_comment=str(variant_dict.get("first_comment", "")),
                alt_text=str(variant_dict.get("alt_text", "")),
            )
        except Exception as exc:  # noqa: BLE001
            return err(f"invalid variant: {exc}", code=400)
        platform = str(body.get("platform") or "instagram")
        row_id = captions_mod.persist_selection(
            output_id=output_id,
            variant=variant,
            platform=platform,
            brand_id=body.get("brand_id"),
            template_id=body.get("template_id"),
            product_id=body.get("product_id"),
        )
        return ok({"caption_id": row_id})

    @app.route("/api/captions/<int:output_id>", methods=["GET"])
    def api_captions_for_output(output_id: int):
        from app import captions as captions_mod
        return ok({"captions": captions_mod.list_for_output(output_id)})

    @app.route("/api/feed", methods=["GET"])
    def api_feed_grid():
        from app import feed_preview as fp_mod
        brand_id = request.args.get("brand_id", type=int)
        new_id = request.args.get("new_output_id", type=int)
        return ok({"items": fp_mod.grid(brand_id=brand_id, new_output_id=new_id)})

    @app.route("/api/feed/shuffle", methods=["POST"])
    def api_feed_shuffle():
        from app import feed_preview as fp_mod
        body = request.get_json(silent=True) or {}
        brand_id = body.get("brand_id")
        if brand_id is not None:
            brand_id = int(brand_id)
        request_token = body.get("request_token") or ""
        return ok({"items": fp_mod.shuffle(brand_id=brand_id, request_token=request_token)})

    @app.route("/api/scheduler/schedule", methods=["POST"])
    def api_scheduler_schedule():
        from app.marketing import scheduler as sched_mod
        body = request.get_json(silent=True) or {}
        name = str(body.get("name") or "")
        kind = str(body.get("kind") or "publish_output")
        run_at = float(body.get("run_at") or time.time())
        payload = body.get("payload") or {}
        if not name:
            return err("name required", code=400)
        try:
            job_id = sched_mod.schedule(name, kind, run_at, payload)
        except ValueError as exc:
            return err(str(exc), code=400)
        return ok({"job_id": job_id})

    @app.route("/api/scheduler/jobs", methods=["GET"])
    def api_scheduler_jobs():
        from app.marketing import scheduler as sched_mod
        status = request.args.get("status")
        return ok({"jobs": sched_mod.list_jobs(status=status)})

    @app.route("/api/scheduler/jobs/<int:job_id>/run", methods=["POST"])
    def api_scheduler_run_now(job_id: int):
        from app.marketing import scheduler as sched_mod
        return ok(sched_mod.run_now(job_id))

    @app.route("/api/scheduler/jobs/<int:job_id>/approve", methods=["POST"])
    def api_scheduler_approve(job_id: int):
        from app.marketing import scheduler as sched_mod
        return ok(sched_mod.approve(job_id))

    @app.route("/api/scheduler/jobs/<int:job_id>", methods=["DELETE"])
    def api_scheduler_cancel(job_id: int):
        from app.marketing import scheduler as sched_mod
        return ok({"cancelled": sched_mod.cancel(job_id)})

    @app.route("/api/publishers", methods=["GET"])
    def api_publishers_list():
        from app import publisher as publisher_mod
        return ok({"publishers": publisher_mod.list_publishers()})

    @app.route("/api/publishers/dispatch", methods=["POST"])
    def api_publishers_dispatch():
        from app import outputs as outputs_mod
        from app import publisher as publisher_mod
        body = request.get_json(silent=True) or {}
        try:
            output_id = int(body.get("output_id") or 0)
        except (TypeError, ValueError):
            return err("output_id required", code=400)
        out = outputs_mod.get_output(output_id)
        if not out:
            return err("output not found", code=404)
        platform = str(body.get("platform") or "instagram")
        preferred = body.get("preferred")
        result = publisher_mod.dispatch(out, platform, preferred=preferred)
        return ok({"publisher": result})

    @app.route("/api/telegram/webhook", methods=["POST"])
    def api_telegram_webhook():
        from app import telegram_notify as tg
        from app.marketing import scheduler as sched_mod
        body = request.get_json(silent=True) or {}
        callback = body.get("callback_query") or {}
        data = str(callback.get("data") or "")
        message = callback.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        # Map the output_id from the callback back to the queued job.
        try:
            output_id = int(data.split(":", 1)[1])
        except (IndexError, ValueError):
            output_id = None
        decision = tg.handle_callback(data, job_id=output_id)
        job_action = "noop"
        if output_id and decision in ("approved", "rejected"):
            # Find the most recent queued/blocked job for this output.
            conn = app_db.get_conn()
            row = conn.execute(
                "SELECT id FROM scheduled_jobs WHERE payload_json LIKE ? "
                "AND status IN ('queued','blocked') ORDER BY id DESC LIMIT 1",
                (f'%"output_id": {output_id}%',),
            ).fetchone()
            if row:
                if decision == "approved":
                    sched_mod.approve(int(row[0]))
                    sched_mod.run_now(int(row[0]))
                    job_action = "approved_and_dispatched"
                else:
                    sched_mod.cancel(int(row[0]))
                    job_action = "rejected"
        return ok({"decision": decision, "job_action": job_action, "chat_id": chat_id})


# ---------- SPA static fallback ----------

def _register_spa_fallback(app: Flask) -> None:
    """When web/dist/ exists, serve the SPA bundle at / and any unmatched GET."""

    index_html = WEB_DIST / "index.html"
    assets_dir = WEB_DIST / "assets"

    if not index_html.exists():
        return  # SPA not built yet. Fall through to Jinja.

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
            "assets/", "favicon",
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