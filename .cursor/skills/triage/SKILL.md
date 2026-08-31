---
name: triage
description: Bin scraped references into inbox → ready → archived.
---

# Triage

**When to use:** After Agent-Reach scrapes a batch of references into `references/inbox/`.

**Inputs:** `references/inbox/*.json` (metadata sidecars)
**Outputs:** references moved to `references/ready/` (top 20% by engagement) or `references/archived/`

**Behaviour:**
1. Read each metadata file's `engagement_tier`.
2. Tier A → `references/ready/`. Tier B → `references/ready/` only if operator approves.
3. Tier C and below → `references/archived/`.
4. Update the run ledger in `agent-control/`.
