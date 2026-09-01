# Video pipeline (Phase D)

The video pipeline turns a UGC-template JSON + product data into an MP4.
It composes each frame through `app.video_compositor`, which itself
reuses `app.compositor` for image composition and shells out to FFmpeg
for stitching.

## UGC template shape

```json
{
  "name": "Unboxing",
  "aspect_ratio": "9:16",
  "duration_s": 30,
  "fps": 30,
  "scenes": [
    {
      "id": "intro",
      "start_s": 0,
      "end_s": 5,
      "template_id": 12,
      "layers": { "headline": "{{director.headline}}" }
    },
    ...
  ],
  "transitions": [
    {"type": "fade", "duration_s": 0.5, "between": ["intro", "demo"]}
  ],
  "audio_track": {
    "src": "ambient.caf", "loop": true, "gain": 0.6
  }
}
```

Built-in UGC templates live in `templates/builtin/ugc/`:

- `unboxing.json`
- `review.json`
- `tutorial.json`
- `lifestyle.json`
- `launch_hype.json`
- `ugc_raw.json`

## CLI: `one_shot`

`app/one_shot.py` accepts a natural language brief and produces an MP4
in one go:

```bash
python -m app.one_shot "Make a 30s unboxing for these new sneakers, hype energy, 18-25 streetwear"
```

Internally it:

1. Runs Studio Pro against the brief.
2. Picks the highest-confidence suggestion.
3. Looks up its UGC template.
4. Expands `{{...}}` placeholders with Director + Copywriter values.
5. Renders each scene's PNG through `app.compositor.render`.
6. Applies motion (`app.motion.get_backend`) per layer.
7. Encodes via `ffmpeg -y -f image2 -i frame_%04d.png -r 30 out.mp4`.

## Motion backends

By default Calypso uses `app.motion.opencv.OpenCVMotionBackend` which
implements bounce, slide, pop, pulse, wipe, and fade without any
external API call. To opt into the Omni backend set
`OMNI_API_KEY=<token>` and the factory returns `OmniMotionBackend` if
the model exists in the key's allowlist.

Both backends produce the same `MotionClip` dataclass — the compositor
treats them interchangeably.

## Cost cap

Every render goes through `app.generation_router`, which enforces:

- Per-job $ cap (default $5)
- Per-day $ cap (default $50)
- Brand-level $ cap (custom field)

Hitting a cap aborts the render before the next image is generated and
returns a 402 with the cap that was crossed.