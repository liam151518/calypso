---
name: review-via-graph
description: Structural review of an n8n workflow or ComfyUI graph by reading the JSON.
---

# Review-via-graph

**When to use:** A new workflow JSON is added or modified.

**Inputs:** workflow JSON path
**Outputs:** review notes appended to `slices/NNN-name/review.md`

**Behaviour:**
1. Parse the JSON; enumerate nodes and edges.
2. Check: every node has a clear input, every output is consumed, no orphan nodes.
3. For n8n: verify cron triggers fire at the expected times; verify webhook handlers validate payloads.
4. For ComfyUI: verify the sampler is wired to a VAE decode, model loads are consistent.
5. If issues found, file them as TODOs in the review; do not fix them yourself.
