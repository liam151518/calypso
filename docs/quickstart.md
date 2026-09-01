# Calypso — Quickstart

This walks a new operator through their first brand-poster render.

## 1. Set the active brand

Open the web SPA, go to **Brand**, fill in:

- Name
- Voice tone (bold / minimal / playful / luxury / casual / cinematic)
- Palette (list of hex colors)
- Banned words (comma-separated)
- Default filter + aspect ratio

Click **Save**. The active brand is now used by every downstream module.

## 2. Add a product

Open **Products**, click **Add product**. Either:

- Fill in the form manually
- Paste a CSV with columns `name,price,category,collection,description,tags`

Upload a hero image. The Compositor will automatically generate a
cutout (via `rembg` + `onnxruntime`) on the first render.

## 3. Boot built-in templates

Open **Templates** and click **Boot built-ins** if the list is empty.
This loads:

- `minimal_launch.json` — clean studio launch poster
- `bold_drop.json` — high-contrast streetwear drop
- `lifestyle_flatlay.json` — lifestyle overhead shot
- `announcement.json` — neutral announcement poster
- `sale_blast.json` — sale promo poster
- `ugc/*.json` — UGC video templates (unboxing, review, tutorial, lifestyle, launch hype, ugc_raw)

## 4. Render

Open **Studio Pro**, type:

> "Make a 30s unboxing for these new sneakers, hype energy, 18-25 streetwear"

Click **Generate**. You'll see three suggestion cards with previews,
rationale, cost, and confidence score. Click **Edit** on your favorite
to drop into the editor with the layers pre-populated, or **Schedule**
to queue it for later.

## 5. Connect a Telegram approval bot (optional)

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then schedule a job.
The bot will send a message with **Approve** / **Reject** inline
buttons; Calypso waits for the click before publishing.

## 6. Run an automation rule

Open **Automation**, click **New rule**. Example:

- Trigger: `product_added`
- Conditions: `{"field": "category", "op": "eq", "value": "shoes"}`
- Action: `apply_preset` → preset ID 1

Now when you add a new product with category "shoes", the preset is
automatically applied and an output is created.

## Where to go next

- `docs/templates.md` — Template JSON schema and authoring tips
- `docs/studio.md` — Studio Pro agent architecture
- `docs/video_pipeline.md` — UGC templates + ffmpeg stitching
- `docs/omni_integration.md` — Enabling the Omni motion backend
- `docs/api.md` — Full HTTP API reference
- `docs/RELEASE.md` — Pre-release checklist