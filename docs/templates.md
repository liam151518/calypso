# Templates

A template is a JSON document describing a canvas, an ordered list of
layers, and an optional brand-locks list. The Compositor (`app/compositor.py`)
turns a template + product + brand into a final image.

## Top-level shape

```json
{
  "name": "Bold Drop",
  "aspect_ratio": "1:1",
  "canvas": {"width": 1080, "height": 1080},
  "category": "ugc",
  "default_filter": "neon",
  "ai_prompt_template": "high-contrast editorial scene with {{product.name}}",
  "layers": [ ... ],
  "brand_locks": ["bg", "logo"]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Required, used as the display label |
| `aspect_ratio` | enum | `1:1`, `4:5`, `9:16`, `16:9`, `2:3` |
| `canvas.width` / `canvas.height` | int | Pixel dimensions |
| `category` | enum | One of `ugc`, `lifestyle`, `minimal`, `bold`, `cinematic`, `tutorial`, `review`, `launch`, `announcement`, `sale` |
| `default_filter` | string | One of the built-in filters (`bright`, `moody`, `vintage`, `minimal`, `neon`) |
| `ai_prompt_template` | string | Background prompt template; `{{product.name}}` etc. is substituted |
| `layers` | array | Ordered bottom-to-top |
| `brand_locks` | array | Layer ids that brand DNA v2 should not modify |

## Layer shape

Every layer has a `type` and a `config`. The supported types are:

| Type | Config schema |
|------|---------------|
| `ai_background` | `{prompt: string}` |
| `ai_image` | `{prompt: string}` |
| `product_cutout` | `{position: "left"\|"center"\|"right"\|"fill"}` |
| `text` | `{content, font_family, color, font_size?, background_color?, padding?, border_radius?, text_align?, text_transform?, letter_spacing?}` |
| `image` | `{src, radius?, opacity?}` |
| `shape` | `{shape_type, fill_color?, stroke_color?, stroke_width?}` |
| `video_background` | `{prompt, duration_s?, fps?, loop?}` |

Top-level layer properties:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Required, unique within the template |
| `name` | string | Display name in the editor |
| `x`, `y` | float (0..1) | Position as percent of canvas |
| `width`, `height` | float (0..1) | Size as percent of canvas |
| `visible` | bool | Default `true` |
| `locked` | bool | Default `false` |
| `rotation` | float | Degrees |
| `opacity` | float (0..1) | Default `1.0` |

## Built-in template library

`templates/builtin/*.json` ships with six image templates and
`templates/builtin/ugc/*.json` ships with five video templates. They
are loaded into the DB on first request via `GET /api/templates/boot-builtins`.

## Validation

Templates are validated against `app/utils/validators.py` (JSON Schema).
Invalid templates raise `TemplateError` with a list of offending
fields. The SPA displays those errors before saving.

## Layer overrides

Studio Pro agents emit `layer_overrides` (a dict keyed by layer id) that
the Compositor can apply on top of the template without mutating the
stored template. Use this to merge Copywriter copy or VisualStrategist
nudges without touching the DB.