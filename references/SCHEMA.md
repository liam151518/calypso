# Folder A — Reference metadata schema

Every file in `references/ready/`, `references/inbox/`, and `references/archived/` is a JSON document that matches this schema. The reference picker (`scripts/reference_picker.py`) reads these files.

## Schema

```json
{
  "source": "twitter",
  "source_url": "https://twitter.com/GenshinImpact/status/1234567890",
  "scraped_at": 1725120000,
  "scraped_by": "agent-reach",

  "platform": "x",
  "format": "video",
  "theme": "pull_reaction",
  "engagement_tier": "A",
  "style_tags": ["dark_moody", "cinematic", "neon_accents"],
  "composition": "phone_in_hand",
  "audio_trend": "trending_sound_v3",

  "metrics": {
    "likes": 12500,
    "shares": 842,
    "comments": 234,
    "follower_count_at_scrape": 2500000,
    "engagement_rate": 0.0054,
    "vs_account_avg_multiplier": 3.2
  },

  "asset_path": "x_video_001.mp4",
  "thumbnail_path": "x_video_001_thumb.jpg",
  "file_size_bytes": 4521984,
  "duration_seconds": 8,

  "curation": {
    "curated_by": "operator_name",
    "curated_at": 1725300000,
    "tier_set_by": "operator_name",
    "why_a_tier": "top 5% engagement rate in pull_reaction theme"
  },

  "notes": "Reference for the dark-moody cinematic style. Captures the gacha-pull anticipation moment with neon accents."
}
```

## Field reference

### Required

| Field | Type | What |
|-------|------|------|
| `source` | string | Where it was scraped from (twitter, instagram, tiktok, reddit, manual) |
| `source_url` | string (URL) | Original post URL |
| `platform` | enum: `x` \| `instagram` \| `tiktok` \| `reddit` \| `youtube` | Target platform (what it would be posted as) |
| `format` | enum: `image` \| `video` \| `carousel` \| `text` | Asset type |
| `engagement_tier` | enum: `A` \| `B` \| `C` \| `""` | A = top 20%, B = top 50%, C = bottom 50%, "" = unrated |

### Recommended

| Field | Type | What |
|-------|------|------|
| `scraped_at` | int (unix seconds) | When Agent-Reach pulled it |
| `theme` | string | One of: `pull_reaction`, `cabinet_hype`, `tier_list`, `set_completion`, `irl_cabinet`, `restock_alert`, `rare_drop`, `mascot`, `event_hype` |
| `style_tags` | array of strings | Visual style (dark_moody, bright_anime, retro_pixel, cinematic, ugc_handheld, neon, pastel) |
| `composition` | string | close_up, split_screen, text_heavy, gameplay_focused, phone_in_hand, flat_lay |
| `audio_trend` | string | (video only) trending sound name or `""` |

### Optional but useful

| Field | Type | What |
|-------|------|------|
| `metrics.likes`, `.shares`, `.comments` | int | Raw counts at scrape time |
| `metrics.engagement_rate` | float | (likes+shares+comments) / follower_count |
| `metrics.vs_account_avg_multiplier` | float | 1.0 = typical for the source account; 3.0 = 3x better than typical |
| `curation.why_a_tier` | string | Operator note for why this got its tier |
| `notes` | string | Anything else (e.g., "use this for cinematic hero posts") |

## How tier assignment works

When a reference enters `references/inbox/`, `engagement_tier` is `""` (unrated).

After the **4-hour curation session**, the operator assigns `A`, `B`, or `C`:

- **A-tier:** top 20% by engagement_rate vs account average. **These enter `references/ready/`.**
- **B-tier:** top 50%. Parked in `references/ready/` (still usable, just weighted lower).
- **C-tier:** bottom 50%. Moved to `references/archived/` with `curation.why_not_a_tier` filled in.

The picker weights are: A = 3.0, B = 1.0, C = 0.33. So an A-tier reference gets picked ~9x more often than a C-tier.

## How Adam ingests these

When you ask Adam to scrape references, Agent-Reach writes the JSON files. Adam then:

1. Runs `triage` to bin inbox → ready/archived
2. Sorts by engagement_rate
3. Asks you to do the 4-hour curation review
4. Updates `engagement_tier` on each based on your decision
5. Moves A/B to `references/ready/`, C to `references/archived/`

## What's not here yet

- Per-reference weighted LoRA trigger words (Phase 4)
- Folder B asset cross-references (which brand asset to use with this ref) (Phase 4)
- Post-generation engagement backfill (Phase 4 `re-weight Folder A` task)
