"""app/marketing. Phase F Marketing surface.

Submodules:
    contacts    : Phase F.1. Contact store with consent and unsubscribe.
    campaigns   : Phase F.2. Campaign drafts and scheduling.
    pages       : Phase F.3. Landing pages and submissions.
    social      : Phase F.5. Multi-platform social post queue.
    analytics   : Phase F.6. Event store.
    scheduler   : Phase F.7. In-process scheduler (cron-style).
    compliance  : Phase F.8. GDPR/CCPA helpers.

The marketing surface is intentionally API-only. The SPA pages live
under `web/src/pages/Marketing.tsx` (and friends). See `app/server.py`
for the routes that wire these to JSON endpoints.
"""

from __future__ import annotations

from . import analytics, campaigns, compliance, contacts, pages, scheduler, social

__all__ = [
    "analytics",
    "campaigns",
    "compliance",
    "contacts",
    "pages",
    "scheduler",
    "social",
]
