# Omni motion backend (Phase E)

Calypso ships with an OpenCV motion backend (default) and an optional
Omni motion backend. Omni provides high-fidelity camera + scene
motions (track, parallax, scale-tween) without re-rendering the
layer's image.

## When to enable Omni

Enable Omni when:

- You have video assets where simple motion isn't enough
- You have a paid Omni API key in your environment
- The build target is desktop or self-hosted (not the free cloud tier)

Do **not** enable Omni when:

- You want headless renders that run on CPU only
- You want every render to be deterministic and reproducible

## Enabling

1. `pip install omni-ml` (adds the SDK to your venv)
2. Set `OMNI_API_KEY` in `.env`
3. Edit `app/motion/omni.py` if you need to point at a different
   endpoint (the default uses the published `https://api.omni-ai.dev`)

If either step is missing, `app.motion.get_backend` returns the
OpenCV backend. The fallback is silent — no exception, no log spam.

## Usage

The motion backend is invoked by `app.video_compositor.render_scene`
when the UGC template's `transitions` block lists `kind: "omni"`.
Transitions of `kind: "opencv"` always go through OpenCV. Mixed
templates are supported.

## Cost

Omni charges per second of generated video. The generation router's
cost-cap applies the same way as image generation: see
`docs/video_pipeline.md#cost-cap`.

## Comparison

| Feature | OpenCV | Omni |
|---------|--------|------|
| Build dependency | `opencv-python-headless` | `omni-ml` + API key |
| Determinism | full | approximate (seedable) |
| Motion styles | bounce, slide, pop, pulse, wipe, fade | 60+ cinematic styles |
| Cost | $0 (local) | per-second billing |
| CPU-only | yes | no |