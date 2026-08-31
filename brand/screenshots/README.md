# Folder B — Site Screenshots (seeded, then locked)

**Status:** Seeded 2026-08-31 from `/Volumes/Content SSD/Gacha Luka/public/`. **Do not modify files in this folder after this date.**

The pipeline references these images but does not edit them. If the live site updates its cabinet artwork, you (the operator) update the snapshots here manually — by copying fresh PNGs from `../Gacha Luka/public/` over the existing files. The pipeline picks up the new images on the next generation cycle.

## What's here

10 cabinet snapshots (one per cabinet color, 480px wide) + 1 hero cabinet shot:

- `gk-cabinet-black-480.png`
- `gk-cabinet-blue-480.png`
- `gk-cabinet-damascus-480.png`
- `gk-cabinet-orange-480.png`
- `gk-cabinet-pink-480.png`
- `gk-cabinet-purple-480.png`
- `gk-cabinet-red-480.png`
- `gk-cabinet-white-480.png`
- `gk-cabinet-yellow-480.png`
- `gk-hero-cabinet-pink-480.png`

## How the pipeline uses these

1. **Folder B injection.** The IP-Adapter Plus node picks one of these at random when generating an image post that needs to feature an actual Gatcha Kingdom cabinet (instead of an abstract gacha reference).
2. **Brand grounding.** The post-process script overlays the watermark logo (`../logo/GK_Logo_128.png` at 12% opacity, bottom-right) on top of generated images that include one of these cabinets.
3. **Reference for the Brand LoRA** (Phase 4 training). These are part of the LoRA training set, so the model learns the cabinet shapes and color treatments.

## Update procedure

When the live site changes:

```bash
# On the Mac (this machine), not the Windows PC
cd "/Volumes/Content SSD"
cp -p "Gacha Luka/public/gk-cabinet-<color>-480.png" "Content Pipeline /brand/screenshots/"
```

Don't rename files. The reference picker expects the exact filenames listed above.
