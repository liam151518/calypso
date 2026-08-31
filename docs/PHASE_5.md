# Phase 5 — Scale

**Goal:** Increase output, add platforms, automate replies, prep for handoff.

**Time:** ~4 weeks (rolling)

**Outcome:** Pipeline runs mostly unattended. New hires can pick it up by reading `adam/context/*.md`.

---

## 5.1 — Add TikTok

**Say to Adam:**

```
Wire up TikTok publishing. Use the existing Social Stats integration. TikTok Content Posting API needs a separate OAuth flow — walk me through it.
```

Adam writes the TikTok credential config + tests a single upload. If TikTok's beta access is granted, this is ~1 day of work.

---

## 5.2 — Auto-reply bot

The Social Stats unified inbox collects DMs and comments across platforms. Add an LLM-backed auto-responder.

**Say to Adam:**

```
Build the auto-reply bot. It runs on Social Stats' unified inbox. For each new message:
1. Classify intent (gacha-pull question, support request, spam)
2. If gacha-pull question: answer with a reference to the relevant gachakingdoms.com feature (pull simulator, tier list)
3. If support: forward to me on Telegram
4. If spam: archive

Use the brand voice from brand/voice.md. Never auto-reply to anything with a bill, payment, or refund keyword.
```

Builder adds:
- LLM chain (local Ollama or OpenAI API)
- Intent classifier
- Brand-voice-conditioned response generator
- Forward-to-Telegram for sensitive threads

---

## 5.3 — RSS triggers

When gachakingdoms.com publishes a new tier list, auto-generate a promo post.

**Say to Adam:**

```
Set up the RSS trigger. When the site publishes a new tier list (you'll need to add an RSS feed or webhook to the site — that's a Gacha Luka repo change, so coordinate with the site owner), automatically generate a promo post using that tier list's metadata. The post is a 1-image card with the top character + a CTA linking to the tier list.
```

Note: the Gacha Luka site is in a separate repo. If the user owns both repos, Adam can draft the RSS feed change there too. If not, hand the change off.

---

## 5.4 — Evergreen bank

Generate 100 posts in one batch, schedule them across 2 months.

**Say to Adam:**

```
Generate 100 evergreen posts over the next 2 weeks. Each picks a random A-tier reference + a brand caption + generates the image. Review them in batches of 10 in Telegram. The approved 100 get scheduled across 60 days at 12:00 and 18:00 SAST.
```

This decouples generation from publishing. Useful when:
- You want to take a week off
- You want to test scheduling optimization
- You want to maintain cadence during a busy month

---

## 5.5 — Handoff prep

The whole point of Adam is handoff-ready. Phase 5 is where you prove it.

**Say to Adam:**

```
Pretend a new operator is joining tomorrow. They've never seen this pipeline. Write the onboarding document that lets them:
1. Understand the architecture in 10 minutes
2. Resume operations in 30 minutes (run verify.sh, approve any pending Telegram approvals)
3. Modify the pipeline without breaking things (where to find rules, where to find decisions, who to ask)

Write it to docs/HANDOFF.md.
```

Adam writes the doc. Then you do a **dry-run handoff**:

1. Delete your local Cursor memory (close Cursor)
2. Open the repo fresh
3. Open Cursor with Adam
4. Ask Adam: *"A new operator is here. Walk me through this pipeline."*

If Adam can onboard you from scratch in <30 minutes using just the repo, the handoff works.

---

## 5.6 — Quarterly council

**Say to Adam:**

```
Schedule a quarterly council review. Every 3 months, run council on the full pipeline + the last quarter's engagement data + any new platform/model changes. Output: a list of optimization candidates for the next quarter. Write the schedule to agent-control/quarterly-reviews.md.
```

This is the meta-loop. Adam keeps itself honest.

---

## Done with all phases

The pipeline is now:

- **Cheap** (~$20/mo steady state, ~$5/mo if local H3 benchmark succeeds)
- **Local-first** (RTX 5070 doing most of the work)
- **Handoff-ready** (anyone can run it after 30 min of onboarding)
- **Data-driven** (Folder A re-weights from real engagement)
- **License-clean** (H3 posture documented in ADR)

Total time from Phase 0 start: ~12 weeks. Total upfront cost: $0.

---

## What's NOT in scope

These are things Adam will flag as future work but doesn't build unless you ask:

- **Multi-account** (posting from multiple brand accounts) — useful for A/B at scale
- **Influencer outreach** (sending DMs to gacha creators) — requires separate tool
- **Paid ads** (Meta Ads, X Ads) — requires ad account + budget, separate from organic posting
- **Email capture** (collecting emails from engaged users) — separate funnel
- **Localization** (auto-translating posts to Japanese, Korean, Chinese) — useful if expanding beyond SA

Each of these is a separate slice Adam can run when you're ready.

---

## If something breaks

Anywhere along the way:

**Say to Adam:**

```
Something's broken. Use dev-launch-debug to walk me through what's wrong.
```

Adam checks the verify script output, the n8n error logs, the ComfyUI console, the Telegram webhook delivery, and tells you what's stuck. If it's a code bug, `dispatch-builder` fixes it. If it's a config issue, Adam tells you which `.env` var to change.

---

## Next phase

There isn't one. This is the destination. The pipeline keeps running, Adam keeps optimizing, the team keeps curating Folder A, and the brand grows.
