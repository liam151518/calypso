# Calypso — Design Direction

Calypso is an operator console for a single-actor AI video pipeline.
Mode: **Operate**. Decisions lead with scanability, consistency, and native expectations; brand lives in precise details.

## Why dark

The use scene is a producer at a desk, often with video playback in the same window. Dark surfaces keep reference imagery and generated video frames from being washed out by adjacent glow, which is the actual ambient condition. Picking light or dark by category is the failure mode; here it is picked from the scene.

## Surface hierarchy

Four layers, stacked top-down:

1. `--bg` — app background. Receives no chrome.
2. `--surface` — the sidebar rail and per-page content areas.
3. `--panel` — group containers (form sections, list blocks).
4. `--elevated` — controls at rest (inputs, dropdowns, selectors).
5. `--elevated-2` — controls on hover / focus.

Lines are a single 1px hairline (`--line`). No decorative borders of any other weight; status is conveyed by the surface tint and the status pill, never a colored `border-left`.

## Type

One family throughout the chrome: **Inter** at 400 / 500 / 600. Headings, body, labels, buttons — all Inter. The temptation to add a display face for a "magazine" feel was refused; this is an interface, not a read surface.

**JetBrains Mono** appears only in places that are genuinely code or data: ref ids, job ids, environment variable names, palette hex codes, prompt bodies in the disclosure panel, error-message text.

Type scale: fixed rem steps at 1.2 ratio (`--t-12` … `--t-28`). No clamp() headings. Display body is 16px; the page-head title is 28px, 600 weight, `-0.025em` tracking. The font-feature settings `cv11, ss01` are enabled for tabular figures and the Inter alternate-one.

## Color

Restrained. Single accent:

- **signal-orange** `#ff6a1f` — the only chromatic note. Reserved for primary actions, current selection, focus rings, status-running dots, and the active-brand marker. It does not decorate.

Status:
- `ok` green for succeeded
- `err` red for failed
- `warn` amber for queued / not configured

State vocabulary: hover, focus, active, disabled. Every interactive surface ships all four. The focus ring is 2px solid signal-orange with 1px offset.

## Layout

Sidebar rail on the left (232px, sticky, full-height). Content column has a max width of 1280px and 48px gutters that collapse to 20px below 900px.

Sectioning uses panels: one panel per page-section, title in `panel-head`, body in `panel-body`. No kicker or eyebrow above panel titles — the title carries the section's weight.

Two-column form on Generate: prompt composer (left) + side column (right). The breakpoint at 900px collapses to a single column.

References and Brand pages use a sidebar-list + main-content grid; both collapse below 900px.

## Components

- **Buttons**: 32px height, 14px horizontal padding, `--r-2` (6px) radius. Three styles: primary (signal), ghost (transparent on hover-elevate), danger (transparent with red border). A smaller `--sm` variant at 26px.
- **Inputs / selects / textareas**: `--elevated` background, `--line` border. Focus state lifts to `--elevated-2`, border color to signal, 3px halo in `--signal-bg`.
- **Tag pills**: rounded (`border-radius: 999px`), mono, lowercase. Three states: static (read-only), filter (toggleable group), and dismissable-with-X (on reference cards).
- **Job card**: surface panel + a single status pill in its top-left corner. No colored sidebar/border-left decorations.
- **Brand banner on Generate**: a single horizontal row, never a card with a vertical signal stripe.
- **Empty state**: a 36px circular icon in `--elevated`, a title, a 1-sentence subhead, and an action. Not italic helper text. Empty states teach the interface.

## Motion

150–200ms transitions on color, background, border. State changes use ease (`cubic-bezier(0.4, 0, 0.2, 1)`). One authored moment: the indeterminate progress bar on running jobs (an orange bar sliding left-to-right in a 3px track). No choreographed load sequences. `prefers-reduced-motion` halts motion entirely.

## Browser surfaces

Selection, scrollbar, focus ring, and numerals are themed from the palette. Without this, the page reads as assembled; with it, as built.

## Banned

These are the category defaults the design refuses; the brief would have to specifically call for any of them to earn them back.

- Kicker/eyebrow labels above section titles or headings. The heading carries the weight.
- A giant hero button on Generate. Primary actions are 32px tall, not 56px.
- Colored `border-left` or `border-right` decorative stripes on cards or alerts.
- Display fonts in UI labels, buttons, or data.
- Gradient text, glass-as-decoration, hard offset box-shadows.
- Emoji or unicode glyphs standing in for icons. All icons are SVG, single weight (1.5px), `currentColor`, sized to the control they live in.

## Acceptance

Each shipped surface must:

- Render against a populated database without orphan or empty blocks.
- Show all states of every interactive control: default, hover, focus, active, disabled.
- Pass 347 pytest tests with zero flakes.
- Render at 1440px desktop and 360px mobile without overflow.
