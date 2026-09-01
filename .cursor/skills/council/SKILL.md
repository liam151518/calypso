---
name: council
description: Seven-perspective review for high-stakes decisions (license, model choice, etc.).
---

# Council

**When to use:** Phase 4 (optimization), or any time a decision has multi-stakeholder consequences
(license review, model selection, cost-vs-quality tradeoffs).

**Inputs:** decision to review
**Outputs:** `plan/adr/NNNN-<topic>.md` with 7 perspectives and a recommendation

**Perspectives:**
1. **Cost**. Monthly spend delta, one-off cost, hidden costs (engineer-time)
2. **Quality**. Output quality, latency, reliability
3. **License / Legal**. Commercial-use terms, attribution, model restrictions
4. **Ops**. Failure modes, recovery, on-call burden
5. **Brand fit**. Does this match Gachakingdoms voice and visual DNA?
6. **Speed / DX**. Does this make iteration faster or slower?
7. **Reversibility**. Can we swap this out later? What would migration cost?

Each perspective gets a 2-4 sentence verdict. Final recommendation synthesizes the verdicts.
