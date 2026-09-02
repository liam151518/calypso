# Calypso — Refinement Studio

The Refinement Studio is the editing surface for every generated output.
Open any output and click **Refine** (or navigate to `/refine/:outputId`).
You'll see three columns:

```
┌──────────────┬────────────────────┬──────────────┐
│ Layers       │ Preview            │ Refine       │
│ (left)       │ (center)           │ (right tabs) │
└──────────────┴────────────────────┴──────────────┘
```

## Layer Panel — left column

Lists every layer in `outputs.layers_json`. Click a layer to reveal
type-specific controls:

| Layer type       | Controls                                                          |
|------------------|-------------------------------------------------------------------|
| `ai_background`  | Prompt textarea, seed input, model input, **Regenerate** button   |
| `ai_image`       | Same as above                                                      |
| `text`           | Inline text editor, **Regenerate** to apply                        |
| `image`          | Replace cutout (coming soon)                                      |
| `motion_*`       | Timing + easing (coming soon)                                      |

Regenerating a single layer does **not** regenerate the whole image. The
compositor patches only that layer and saves a new version. Your product
placement, text, and other layers stay exactly where they were.

## Preview — center column

The current canonical render. Toggle **Compare** on any version in the
**Variants** tab to see them side-by-side with synchronized sizing.

## Refine Panel — right column

Three tabs:

### Quality

- **Upscale** — 2x or 4x. Backend picker:
  - `realesrgan` — local Real-ESRGAN NCNN Vulkan binary. Free, fast, but
    requires the binary to be installed (see `scripts/install-realesrgan.sh`).
  - `fal` — cloud ESRGAN endpoint. Costs ~$0.04 per MP.
- **Face enhancement** — toggle. Improves faces at the cost of slightly
  softer backgrounds.

The upscaled output is saved as a new version (no overwriting), so you
can A/B the original vs. the upscale.

### Variants

Every saved version. For each:

- **Compare** — toggles the side-by-side preview.
- **Promote** — flips `outputs.file_path` to this version, making it the
  canonical render.
- **Delete** — drops the version. The file on disk is left intact.
- **Open** — opens the file in a new tab (uses the `/outputs/...` URL).

### VFX

Placeholder for video outputs. Once the per-layer VFX backend lands,
this tab will host the timeline editor, easing picker, and motion-graphic
markers.

## Versioning model

Every refine action (regenerate, upscale, manual save) writes a row to
the `output_versions` table:

```
output_versions
├── id
├── output_id (FK -> outputs.id)
├── layers_json     (the patched layer stack)
├── filter_settings (filter name + intensity)
├── file_path       (the rendered file on disk)
├── thumbnail_path  (optional)
├── notes           (e.g., "moody + 4x upscale")
├── cost_usd        (generation cost, 0 for local-only ops)
└── created_at
```

Promoting a version flips `outputs.file_path` to point at the version's
file. The previous canonical file stays on disk — nothing is ever
overwritten, only redirected.

## Endpoints

| Endpoint                                                    | Purpose                                  |
|-------------------------------------------------------------|------------------------------------------|
| `GET    /api/outputs/<id>`                                  | Single output, including layers + filter |
| `GET    /api/outputs/<id>/versions`                         | List all versions                        |
| `POST   /api/outputs/<id>/versions`                         | Create a new version                     |
| `POST   /api/outputs/<id>/versions/<vid>/promote`            | Promote a version to canonical           |
| `DELETE /api/outputs/<id>/versions/<vid>`                   | Delete a version                         |
| `POST   /api/outputs/<id>/layers/<idx>/regenerate`          | Re-render one layer, save as version     |
| `POST   /api/outputs/<id>/upscale`                          | Upscale and save as version              |

All endpoints accept `notes` to label the resulting version — useful for
"v1-rough", "v2-moody", "v3-final".

## Tips

- **Start with the layer that bugs you most.** Background wrong?
  Click it, change one word in the prompt, hit **Regenerate**. The
  compositor re-renders just that layer.
- **Save versions liberally.** Each one costs zero storage (the file
  already exists) and gives you an undo path.
- **Upscale last.** Once you're happy with the composition, upscale to
  your target export resolution. Upscaling is destructive if you redo
  it — but since it's a separate version, you can A/B.
- **Promote intentionally.** Once you have a version you love, promote
  it. From then on every "current" reference in the scheduler points at
  that file.

## What it doesn't do (yet)

- Multi-layer edits in one save — today each action creates its own
  version. Stack them by promoting in sequence.
- VFX timeline for video — schema is in place; UI ships next milestone.
- Curve / HSL color grading — the right side currently exposes
  quality/upscale; advanced grading is on the roadmap.
- Batch operations across multiple outputs — version compare only goes
  one deep today.
