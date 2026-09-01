# HTTP API reference

All endpoints are namespaced under `/api/`. JSON in, JSON out.
Successful responses carry `{ ok: true, ... }`. Failure responses
carry `{ ok: false, error: "<message>" }`.

## Brands

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/brands` | — | `{brands: Brand[]}` |
| `POST` | `/api/brands` | Brand (no `id`) | `{brand_id, brand}` |
| `PATCH` | `/api/brands/<id>` | partial Brand | `{brand}` |
| `DELETE` | `/api/brands/<id>` | — | `{deleted}` |
| `GET` | `/api/brands/<id>/posts` | query: `platform`, `count` | `{outputs}` |

## Products

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/products` | query: `brand_id`, `category`, `tag`, `q` |
| `POST` | `/api/products` | Product (no `id`) |
| `GET` | `/api/products/<id>` | full record |
| `PATCH` | `/api/products/<id>` | partial |
| `DELETE` | `/api/products/<id>` | |
| `POST` | `/api/products/import` | `{csv: <text>}` → import by CSV |

## Templates

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/templates` | query: `category`, `brand_id`, `include_builtin`, `format` |
| `POST` | `/api/templates` | full template JSON; validates against schema |
| `GET` | `/api/templates/<id>` | |
| `DELETE` | `/api/templates/<id>` | only custom templates may be deleted |
| `POST` | `/api/templates/boot-builtins` | idempotent; loads `templates/builtin/*.json` |
| `POST` | `/api/templates/<id>/preview` | `{brand_id?, product_id?}` → render preview PNG |

## Compositor

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/render` | `{template_id, product_id?, layer_overrides?, filter?, aspect_ratio?, intensity?, brand_id?, job_id?}` |
| `POST` | `/api/render/batch` | `{preset_id?, product_ids?}` |
| `GET` | `/api/render/<job_id>/events` | Server-Sent Events stream |
| `GET` | `/api/outputs/<id>/preview.png` | rendered preview |
| `GET` | `/api/outputs/<id>/file.jpg` | the actual JPEG |

## Filters

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/filters` | built-in + custom presets |
| `POST` | `/api/filters/preview` | `{filter, intensity?, ...}` → preview via `text.jpg` |

## Studio Pro

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/studio-pro/generate` | `{brief, brand_id?, product_id?, platforms?, budget_usd?, duration_s?}` |
| `GET` | `/api/studio-pro/<run_id>/log` | persisted suggestion rows |
| `POST` | `/api/studio-pro/<id>/accept` | render + return editor URL |
| `POST` | `/api/studio-pro/<id>/schedule` | enqueue a publish job |

## Video

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/video/render` | `{ugc_template_id, product_id, brand_id, layer_overrides?}` |
| `POST` | `/api/video/one_shot` | `{brief, ...}` → one-shot brief → video |
| `POST` | `/api/motion/render` | `{layer_id, kind: "opencv"\|"omni", ...}` |

## Marketing

Endpoints under `/api/marketing/`: contacts, campaigns, landing,
social, analytics. See `app/marketing/schemas.py` for payload shapes.

## Phase G: presets, automation, config

| Method | Path |
|--------|------|
| `GET/POST/DELETE` | `/api/presets[?brand_id]` |
| `POST` | `/api/presets/<id>/apply` |
| `GET/POST` | `/api/automation/rules[?brand_id]` |
| `PATCH/DELETE` | `/api/automation/rules/<id>` |
| `GET` | `/api/config/export` |
| `POST` | `/api/config/import` |

## Health

`GET /api/health` → `{ok, version, modules}`