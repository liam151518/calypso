# Studio Pro

Studio Pro is the brand-poster multi-agent surface. It complements the
existing 7-agent film Studio (which lives in `app/agents/`) without
replacing it.

## Agent chain

```
Director → TemplateSelector → Copywriter → VisualStrategist → CampaignBuilder
```

Each agent extends `app/agents.base.Agent` and lives in
`app/studio_pro/`:

- `director.py` — picks tone, style, palette shift, recommended platforms,
  duration, and audience from the brief.
- `template_selector.py` — scores templates by category match + name match
  + text-layer presence.
- `copywriter.py` — generates tone-flavored headline variants for every
  text layer of each candidate template.
- `visual_strategist.py` — picks a background prompt + filter + small
  layout nudges by tone.
- `campaign_builder.py` — composes the final 3 suggestions, computes
  confidence, persists to `studio_suggestions`.

## Confidence scoring

Per plan §F.2:

```
score = 0.4 * brand_compat
      + 0.3 * template_score
      + 0.2 * novelty
      + 0.1 * cost_feasibility
```

`brand_compat` is 1.0 when the brand's voice tone matches the
Director's tone, else 0.6. `novelty` is 1.0 when the template hasn't
been seen in the recent run history, else 0.3. `cost_feasibility` is
1.0 when the estimated cost fits the brand's budget, else 0.3.

## What Studio Pro does *not* do

Studio Pro agents never write to the `outputs` table. They emit
`template_id` + `layer_overrides` JSON only. The Compositor renders
previews on demand when the user accepts a suggestion. This keeps the
agents cheap and idempotent — re-running a Studio Pro run with the
same inputs always produces the same suggestions.

## Running manually

```python
from app.studio_pro import StudioProBrief, run_studio_pro
from app import brand as brand_mod
from app import templates as tpl_mod

brand = brand_mod.get_active_brand()
templates = tpl_mod.list_templates(brand_id=brand["id"], include_builtin=True)
run = run_studio_pro(
    StudioProBrief(
        brief="Make a 30s unboxing for these new sneakers, hype energy, 18-25 streetwear",
        brand_id=brand["id"],
        platforms=["instagram"],
        budget_usd=5.0,
        duration_s=30,
    ),
    brand=brand,
    product={"id": 1, "name": "Sneaker"},
    templates=templates,
)
print(run.run_id, run.suggestions)
```

## API

| Endpoint | Notes |
|----------|-------|
| `POST /api/studio-pro/generate` | Run the chain; returns `run_id` + suggestions + agent log |
| `GET /api/studio-pro/<run_id>/log` | Fetch persisted suggestion rows for a run |
| `POST /api/studio-pro/<id>/accept` | Renders the chosen suggestion via the Compositor and redirects to `/editor/<template_id>` |
| `POST /api/studio-pro/<id>/schedule` | Enqueues a `publish_output` job via the scheduler |