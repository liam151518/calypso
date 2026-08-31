---
name: dev-launch-debug
description: When local infra goes sideways (ComfyUI down, n8n timing out), diagnose and fix.
---

# Dev-launch-debug

**When to use:** Operator reports an infra failure (ComfyUI, n8n, scripts/validate_accounts failing).

**Inputs:** error log
**Outputs:** root cause + fix + a regression check

**Behaviour:**
1. Reproduce the failure on demand.
2. Read the error log; identify the *first* non-cascading error.
3. Diagnose (check the obvious: is the service running? is the .env set? is the network reachable?).
4. Apply the minimum fix.
5. Add a regression check to `verify.sh` so this never goes unnoticed again.
