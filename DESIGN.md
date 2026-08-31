# Calypso — Design system

> Captured from the shipped build, not written before it. This document describes the world Calypso lives in, derived from the actual CSS, templates, and component behavior in `app/static/app.css`, `app/templates/`, and `app/server.py`.

## Product in one sentence

A producer's console for a single-operator video-ad pipeline: type a prompt, hit Generate, the rendered clip lands in `outputs/`.

## Mode

**Operate.** The visitor's success is completing a task — generating a video, reviewing past outputs, managing references, configuring keys. Scannability, clarity, and native affordances outrank expression. Brand lives in the precise details: a single saturated signal-orange that carries action, an editorial serif that gives the dashboard its voice, a broadcast-control-room sidebar.

## Visual world

A 1970s hifi receiver crossed with a broadcast control room, filtered through editorial design. Dark ink ground (operator's studio), warm bone foreground, brass for metadata, a single signal-orange that lights up only for action. Typography carries personality: Playfair Display for page heads and primary actions (a serif with character, earned by the brand being a collector brand), Inter for body, JetBrains Mono for technical metadata (job IDs, model names, durations).

## Palette

| Token         | Hex       | Role                                          |
| ------------- | --------- | --------------------------------------------- |
| `--ink`       | `#0a0a0c` | Page ground                                   |
| `--ink-2`     | `#131316` | Cards, panels                                 |
| `--ink-3`     | `#1c1c20` | Form inputs, hover grounds                    |
| `--ink-4`     | `#2a2a2f` | Stronger hover, button secondary              |
| `--rule`      | `#3a3a42` | Borders, rules                                |
| `--rule-soft` | `#2a2a30` | Subtle borders                                |
| `--bone`      | `#f0ece4` | Primary foreground                            |
| `--bone-2`    | `#d4cfc2` | Secondary foreground, labels                  |
| `--bone-3`    | `#9a948a` | Tertiary foreground, hint text                |
| `--signal`    | `#ff6a1f` | Primary action, active state, focus ring      |
| `--signal-2`  | `#ff8a47` | Hover for `--signal`                          |
| `--brass`     | `#c89d5e` | Metadata, secondary chrome, "queued" status   |
| `--ok`        | `#6ec27b` | Succeeded status, "set" indicator             |
| `--err`       | `#e26b5c` | Failed status, error message                  |

Strategy: **Committed**. A single signal-orange carries ~15–20% of the surface (one primary button per page, one accent rail on the active job card, the focus ring). Everything else is ink + bone.

## Typography

- **Display** — `Playfair Display`, weights 500 and 700. Page titles only. Tracking `-0.025em`.
- **Body** — `Inter`, weights 400, 500, 600. All UI text. Tabular nums enabled globally.
- **Mono** — `JetBrains Mono`, weights 400, 500. Labels (uppercase, tracked 0.1–0.14em), job IDs, durations, technical metadata.

Display and mono fonts are self-hosted from `app/static/fonts/` so the app runs without a network round-trip. System fallbacks: `Times New Roman`, `-apple-system`, `ui-monospace`.

Type scale: H1 44px (30px on mobile), H2 18px, body 14px, hint 11–13px, mono labels 10–11px.

## Layout

- **Sidebar** — fixed-width 240px on desktop, sticky horizontal nav bar on mobile. Contains brand mark, 4 nav links in mono caps, and a liveness indicator.
- **Main** — fluid, max 1180px, padded 40–48px horizontal.
- **Page head** — serif H1 + sub-paragraph, separated from content by a single 1px rule. No kicker/eyebrow label.
- **Card** — `--ink-2` background, 1px `--rule` border, 14px radius, 28px padding.
- **Grid** — 1fr 1fr for paired fields (model+duration, resolution+reference), collapses to single column under 720px.

## Surfaces

- Cards: 1px border, no shadow. The depth comes from layered ink values, not offset shadows.
- Buttons: layered ink for secondary, signal-orange for primary. Hero variant adds a soft orange glow.
- Inputs: `--ink-3` ground, 1px `--rule` border, 3px signal-orange focus ring at 18% opacity.
- Status dots: 6px circles colored by job state. Animated pulse for "loading" and "running".
- Reference previews: 4:3 aspect, dark diagonal-stripe ground visible behind transparent images.

## Motion

One authored moment: the **progress bar** during a running job — a 3px signal-orange bar that slides 40%→60%→280% across the track every 1.6s with a cubic ease-in-out. No hover effects on the dashboard nav (instant state change), no entrance animations on page load, no staggered reveals. Hover transitions: 120ms ease-out on `color`, `background-color`, `border-color`, `box-shadow`. Reduced-motion preference is respected globally.

## Iconography

Hand-authored SVGs in `app/templates/_icons.html`. Single 1.5px stroke, `currentColor` for state. Used in nav (4 icons), form (lightning, upload, download, trash), settings. No icon library dependency.

## Components

- **Job card** — left-rail color by status (orange=running, brass=queued, green=succeeded, red=failed). Mono-caps status text, mono job ID right-aligned. Prompt + meta line. Conditional: video player + cost/elapsed stats (succeeded) or error message (failed) or progress bar (queued/running).
- **Reference cell** — 4:3 preview, name (truncated), file type + size, full-width ghost Remove button.
- **Output cell** — 16:9 video frame, mono ID + size, ghost Download button.
- **Key row** — three-column grid (200px service name, 1fr status, 220px form). Status shows Set/Not configured with masked value when set.
- **Empty state** — centered headline (serif), one-sentence description (body), single primary action button.

## States

Every interactive element covers: hover (color shift), focus (orange ring), active (scale 0.96), disabled (40% opacity). Job statuses: queued → running → succeeded/failed. Form inputs: default, focus, error (via HTMX `hx-on::after-request`). Key rows: set vs not set.

## Browser surfaces (themed, not defaulted)

- Custom scrollbar: 10px wide, ink-2 track, ink-4 thumb.
- Custom focus ring: 2px solid signal, 2px offset, 3px radius.
- Custom selection: signal-orange background, ink foreground.
- `font-variant-numeric: tabular-nums` globally so job IDs and file sizes align.
- `-webkit-font-smoothing: antialiased` for crisp Inter on macOS.
- `prefers-reduced-motion` zeroes all animations and transitions.

## Copy

- Section labels: mono uppercase, tracked (e.g. "API keys", "Recent jobs", "Outputs").
- Buttons name their action: "Generate video", "Upload", "Remove key", "Download".
- Errors name the problem and the recovery: "No API keys configured. Open Settings and add at least one key." (Not "Error: no keys".)
- Empty states invite: "No outputs yet. Generate your first video on the Generate page."
- Brand tag: "Producer's console" (not "ad studio" or generic "dashboard").

## What this design refuses

- Gradient text — emphasis from weight and size.
- Glass / blur — decoration without a function.
- Borders thicker than 1px on cards — structure, not depth.
- Eyebrow / kicker labels above headings — the heading carries its own weight.
- Same-size card+icon+heading+text as the page structure — uses editorial cells and control-panel rows instead.
- Unicode glyphs (▣ ▶ ◆ ⚙) standing in for icons — replaced with hand-drawn SVGs.
- Hard offset shadows (`4px 4px 0`) outside a neobrutalist world.
- Pink/purple gradient accents — replaced with a single committed signal-orange.
- A modal for a task that doesn't need protected focus.

## Provenance

Every shipped raster was generated for this build. The three test images used during visual QA (`/tmp/qa_ref.png`, the synthetic outputs video) are diagnostic fixtures, not shipping assets. The reference previews, output video frames, and SVG icons are the production assets.
