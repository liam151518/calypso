# Folder B. Logo Pack

**Source:** `/Volumes/Content SSD/Gacha Luka/Logo/` and `/Volumes/Content SSD/Gacha Luka/public/`
**Status:** Seeded 2026-08-31. **Do not modify files in this folder after this date.**

## What's here

| File | Purpose | Resolution |
|------|---------|------------|
| `GK_Logo.png` | Full-resolution source logo | 1.3 MB |
| `GK_Logo.jpg` | JPEG alternative | 882 KB |
| `GK_Logo_512.jpg` | Mid-res for watermarks | 480×480 |
| `GK_Logo_256.png` | Small watermark | 256×256 |
| `GK_Logo_128.png` | Tiny watermark for image posts | 128×128 |
| `GK_favicon_32.png` | 32×32 favicon | 32×32 |
| `GK_favicon_16.png` | 16×16 favicon | 16×16 |

## How the pipeline uses these

- **`GK_Logo_128.png`** is the default watermark applied by `scripts/post_process.py` at 12% opacity, bottom-right corner.
- **`GK_Logo_512.jpg`** is the watermark for high-resolution Instagram posts (4% opacity, more visible).
- **`GK_Logo.png`** is the full-quality version, used only for the website hero. **Never** referenced by the pipeline.
- **Favicons** are not used by the pipeline. They live here for completeness.

## Watermark variants

You (or Adam during `intake`) need to create a true **watermark variant**. A transparent PNG version of the logo with white outline suitable for placement on dark backgrounds. To generate one:

```bash
# On the Windows PC, inside the ComfyUI Python venv
python -c "
from PIL import Image
logo = Image.open('C:/path/to/brand/logo/GK_Logo_512.jpg').convert('RGBA')
# Force white tint for visibility on dark backgrounds
pixels = logo.load()
for y in range(logo.height):
    for x in range(logo.width):
        r, g, b, a = pixels[x, y]
        # Average the colors and push toward white, keep alpha
        avg = (r + g + b) // 3
        pixels[x, y] = (255, 255, 255, int(a * 0.85))
logo.save('C:/path/to/brand/logo/GK_Logo_watermark.png')
"
```

Then update `scripts/post_process.py` to use `GK_Logo_watermark.png` when generating dark-themed posts.

## Update procedure

If the logo changes on the live site:

```bash
cd "/Volumes/Content SSD"
cp -p "Gacha Luka/Logo/GK_Logo.png" "Content Pipeline /brand/logo/"
```

Regenerate the watermark variant after copying.
