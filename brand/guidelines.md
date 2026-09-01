# Gatcha Kingdom. Brand Guidelines

> Pre-populated from `/Volumes/Content SSD/Gacha Luka/docs/STYLE_GUIDE.md` and `tailwind.config.ts` (read-only sources).
> Adam will extend this during the `intake` skill.

**Brand spelling:** **Gatcha** Kingdom (not "Gacha").
**Tagline:** *Japan-gacha digital storefront. Spin online, check in IRL, collect everything.*
**Live site:** https://gatcha-kingdom-psi.vercel.app
**Launch market:** South Africa, starting in Johannesburg.

---

## 1. Core feeling

**Nostalgic Tokyo arcade meets modern kawaii digital storefront.** Stepping into a brightly lit gacha-gacha corner in Akihabara. Exciting, slightly chaotic, always friendly.

**Brand attributes:** Playful · Nostalgic (Showa-era arcade) · Energetic (neon, candy colours) · Trustworthy (clean layouts, clear CTAs) · Collectible (designs, badges, completionist streaks)

**Mascot:** Small round cat (maneki-neko as a capsule toy). Use sparingly as decoration and loading indicator.

---

## 2. Color palette

### Primary Neon (buttons, highlights, CTAs)

| Token | Name | Hex | Usage |
|-------|------|-----|-------|
| `gacha-pink` | Gacha Pink | `#FF5E7E` | Primary CTA, active states, sale badges |
| `gacha-cyan` | Capsule Cyan | `#00D4FF` | Links, info badges, machine glass glow |
| `gacha-yellow` | Ticket Yellow | `#FFD166` | Stars, "NEW" tags, spotlight effects |
| `gacha-purple` | Arcade Purple | `#6A0572` | Footer, deep shadows, brand accents |

### Background & Surface

| Token | Hex | Usage |
|-------|-----|-------|
| `gacha-bg` | `#FDF6F0` | Main page background (warm white) |
| `gacha-card` | `#FFFFFF` | Cards, modals |
| `gacha-dark` | `#1E1E2F` | Dark sections, hero overlay |
| `surface-subtle` | `#F3E8FF` | Subtle purple-tinted containers |

### Functional

- **Success:** `#10B981`
- **Error:** `#EF4444`
- **Warning:** `#F59E0B`
- **Text primary:** `#1F2937`
- **Text secondary:** `#6B7280`
- **Text on dark:** `#FFFFFF`

---

## 3. Typography

**Headings / buttons / machine names:** **M PLUS Rounded 1c** (400, 700, 800)
**Body / forms:** **Noto Sans JP** + **Inter** fallback
**Mono:** JetBrains Mono (admin dashboards only)

| Style | Size / LH | Weight | Usage |
|-------|-----------|--------|-------|
| `gacha-hero` | 4rem / 1.1 | 800 | Homepage hero |
| `gacha-h1` | 2.5rem / 1.2 | 800 | Page titles |
| `gacha-h2` | 1.875rem / 1.3 | 700 | Section headings |
| `gacha-h3` | 1.5rem / 1.4 | 700 | Card titles |
| `gacha-body` | 1rem / 1.6 | 400 | Paragraphs, forms |
| `gacha-caption` | 0.875rem / 1.5 | 400 | Labels, badges |
| `gacha-button` | 1.125rem / 1.2 | 700 | Button text |

**Japanese decorative watermark** (e.g. `ガチャ`): M PLUS Rounded 1c 700, `#FF5E7E` at 10% opacity, very large.

---

## 4. Spacing & layout

- **Grid:** 12-column, max-width **1280px**, centered
- **Gutters:** **24px** desktop / **16px** mobile
- **Section padding:** **80px** desktop / **48px** mobile
- **Card gaps:** **24px** / **16px**
- **Radii:** small **8px** · medium **16px** (`gacha`) · large **24px** (`gacha-lg`) · pill **9999px**
- **Page rhythm:** Hero → Machine Grid → How it works → Map preview → Footer. Sections separated by subtle wavy SVG dividers.

---

## 5. Iconography

Capsule-themed / chunky rounded icons (Phosphor or custom).

---

## 6. Effects

| Token | Value | Usage |
|-------|-------|-------|
| `gacha-card` shadow | `0 4px 20px rgba(0,0,0,0.05)` | Card lift |
| `gacha-glow` (pink) | `0 0 15px rgba(255,94,126,0.6)` | Pink CTA glow |
| `gacha-cyan` glow | `0 0 15px rgba(0,212,255,0.5)` | Cyan accents |
| `gacha-pastel-glow` | `0 18px 60px rgba(255,94,126,0.18)` | Hero cards |

---

## 7. Animations

| Name | Duration | Easing | Usage |
|------|----------|--------|-------|
| `gacha-float` | 3s | ease-in-out infinite | Hover lift on cards |
| `gacha-shake` | 0.6s | ease-in-out | "Pull" CTA hover |
| `gacha-drop` | 0.5s | ease-out | Capsule reveal |
| `gacha-pulse-ring` | 2s | ease-out infinite | Live location pings |
| `gacha-wiggle` | 0.6s | ease-in-out infinite | Mascot |

---

## 8. Legal posture (CRITICAL for ad copy)

**Gatcha Kingdom is NOT a casino, lottery, or pay-to-maybe-get-nothing product.** It is the digital interface for the same transaction as a mall capsule machine or blind box:

> You pay a fixed price. You always receive a physical collectible. The pool decides which one.

**Banned words in ad copy:** "bet", "wager", "odds", "winning", "jackpot", "chance to win", "prize", "lucky draw", "spin to win" (without "toy"), "cash", "money payout"

**Allowed framing:** "spin", "pull", "open", "reveal", "collect", "complete the set", "blind box", "capsule", "mystery capsule", "random figure"

**Always true:** every paid spin delivers one physical figure. Randomness decides *which* figure, never *whether* you get one. **Never** imply a chance of "winning nothing."

---

## 9. Do / Don't

### Do

- Lead with the toy. Show the capsule, the reveal, the figure in hand.
- Use bright, saturated lighting (matches the arcade aesthetic).
- Reference specific machine names and cabinet colors (Pink, Blue, Damascus, Orange, Purple, Red, White, Yellow).
- Use the maneki-neko mascot in occasional decorative roles.
- Lean into collection mechanics: completionist, rarity badges, set completion.
- Tag CTAs that link back to gachakingdoms.com: "see the full tier list", "check the cabinet map".

### Don't

- Don't imply gambling, betting, or chance-of-nothing outcomes.
- Don't use "you could win" or "win big" framing.
- Don't lead with the empty wallet / sad face. Lead with the joy of the reveal.
- Don't use stock photo people. When humans appear, use real-feeling, gacha-kid energy (excited, hand-on-chest reaction).
- Don't use Western casino iconography (dice, cards, slot reels).
- Don't use the mascot excessively. It's a decoration, not a co-host.

---

*Last updated: 2026-08-31 (scaffolded from live-site style guide)*
