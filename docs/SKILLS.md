# Calypso — Skills

Skills are markdown files that Calypso injects into every LLM call. They
shape the model's behavior without you writing Python or tweaking
prompts by hand.

## The four built-in skills

| Slug                | What it does                                          |
|---------------------|-------------------------------------------------------|
| `ugc_video`         | UGC scripting patterns for short-form video           |
| `image_ad`          | Direct-response ad patterns for static posts          |
| `prompt_enhancement`| Generic prompt-quality upgrades (sensory detail, camera, lighting) |
| `caption_optimizer` | Tightens captions, strips filler words post-LLM        |

All four are enabled by default. Toggle them on the **Skills** page.

## Frontmatter spec

Every skill is a markdown file with this structure:

```markdown
---
name: My Brand Voice
enabled: true
description: One-line summary shown in the UI.
post_process_re: "(?i)\\b(just|very)\\b"   # optional, applied after LLM
tags: ["brand", "voice"]
---

Markdown body — this is what gets injected as a <skill> block.
```

### Fields

| Field            | Type        | Required | Notes                                          |
|------------------|-------------|----------|------------------------------------------------|
| `name`           | string      | yes      | Display name. Defaults to a slug-derived title.|
| `enabled`        | bool        | no       | Default `true`. Toggled in the UI; DB wins.    |
| `description`    | string      | no       | Short explanation.                              |
| `post_process_re`| string      | no       | Regex applied to LLM output. Invalid → logged + skipped. |
| `tags`           | string[]    | no       | UI grouping.                                   |

## How skills flow into a prompt

When the LLM is called, `app.skills.apply_pre()` prepends every enabled
skill's body as a `<skill>` block in the system prompt:

```
<skill name='Image Ad Composition' slug='image_ad'>
When generating a static image ad, follow these rules:
1. Lead with the offer, not the brand.
2. Use a 3-second test.
...
</skill>

<skill name='Prompt Enhancement' slug='prompt_enhancement'>
When you receive a prompt from the operator, refine it before passing to
the underlying model...
</skill>

[original user prompt]
```

After the model returns, `app.skills.apply_post()` runs every enabled
skill's `post_process_re` against the response, in skill order. The
default `caption_optimizer` strips filler words (`just`, `simply`,
`very`, `really`).

## Writing your own skill

The simplest path is the **Skills** page: click **Add a custom skill**,
fill in the slug, display name, and body, and Save. The DB persists it
and mirrors it to `~/.calypso/skills/<slug>.md`.

The filesystem path matters if you want to edit skills with your normal
text editor or version them in git:

```
~/.calypso/skills/
├── brand_voice.md
├── discount_compliance.md
└── hashtag_strategy.md
```

Drop a file in there and Calypso will pick it up on next startup
(`app.skills.sync_filesystem_to_db()`).

## Examples

### A "no emojis" policy

```markdown
---
name: No Emojis
enabled: true
description: Strip emoji from any LLM output.
post_process_re: "[\\U0001F300-\\U0001FAFF\\U0001F600-\\U0001F64F\\U0001F680-\\U0001F6FF]+"
tags: ["policy", "copy"]
---

Never use emoji in captions, hooks, or any text returned to the operator.
Emoji reduce perceived professionalism and break brand voice.
The `post_process_re` regex above strips any emoji the model slips in.
```

### A "South African pricing" skill

```markdown
---
name: South African Pricing
enabled: true
description: Always show prices in ZAR with the R symbol.
tags: ["pricing", "region"]
---

When showing a price, always prefix with `R` (South African Rand) and use
a space, never a currency code. Example: "R 899" not "R899" and never
"ZAR 899".
```

### A prompt-enhancement skill for streetwear

```markdown
---
name: Streetwear Mood
enabled: true
description: Inject streetwear aesthetics into generated prompts.
tags: ["prompt", "streetwear"]
---

When generating imagery for a streetwear brand, anchor every prompt in:

- **Texture:** raw concrete, exposed brick, scuffed leather, weathered denim
- **Lighting:** hard side-light, sodium-vapor orange, late afternoon sun
- **Wardrobe:** oversized silhouettes, technical fabrics, vintage sportswear
- **Camera:** 35mm film grain, slightly desaturated, 1/125 shutter
```

## Programmatic access

```python
from app import skills

for s in skills.enabled_skills():
    print(s.slug, s.name)

# Inject skills into a prompt:
final_user = skills.apply_pre("my raw prompt", system="be helpful")
# Or build the system prompt on its own:
system_prompt = skills.build_system_prompt(base="be terse")

# Apply post-process transforms:
clean = skills.apply_post(raw_llm_output)
```

## Troubleshooting

- **Skill not firing?** Open **Skills**, confirm the toggle is on. Check
  the body has actual content (empty bodies are skipped).
- **Regex error in logs?** The `post_process_re` regex is invalid;
  Calypso logs the error and skips it so other skills still run. Fix the
  regex on the Skills page.
- **DB vs filesystem drift?** The filesystem wins for `content_md` /
  `post_process_re`; the DB wins for the `enabled` toggle. Edit the DB
  flag in the UI to keep the file in sync.
