# Accounts — Required for the Pipeline

You need to create these accounts. The agent cannot do this for you — they require your credentials, sometimes payment info, and sometimes platform approval.

Work the list in order. Items 1-4 are instant. Items 5-7 need 1-7 days of platform review. Start them ASAP.

---

## Tier 1 — Instant (set up first, needed for end-to-end tests)

### 1. MiniMax platform
- **URL:** https://platform.minimax.io (global) / https://platform.minimaxi.com (CN)
- **What for:** MiniMax H3 video generation + H3-Context-IR + H3-Regenerate-2K
- **Cost:** Pay-per-use (~$10-15/mo steady state)
- **What to capture:** API token (Settings → API Keys), account email
- **Store in `.env`:** `MINIMAX_API_TOKEN=<token>`

### 2. fal.ai
- **URL:** https://fal.ai
- **What for:** MiniMax H3 Max (speed tier) + Kling 2.6 Pro (hero tier)
- **Cost:** Pay-per-use, load $20 credit to start
- **What to capture:** API key (Dashboard → Keys)
- **Store in `.env`:** `FAL_API_KEY=<key>`

### 3. Telegram bot
- **URL:** https://t.me/BotFather
- **What for:** Approval gate — every generated post sends here for Approve/Regenerate/Skip
- **Setup:**
  1. Message @BotFather, send `/newbot`
  2. Name it `GatchaKingdom Approvals` (or whatever)
  3. Save the **bot token** he gives you
  4. Create a channel or group, add the bot
  5. Send a message in the channel, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find the **chat_id**
- **What to capture:** Bot token, chat_id
- **Store in `.env`:** `TELEGRAM_BOT_TOKEN=<token>`, `TELEGRAM_CHAT_ID=<chat_id>`

### 4. Cloudflare
- **URL:** https://dash.cloudflare.com/sign-up
- **What for:** DNS for any custom domains + R2 backup bucket for Folder A
- **Cost:** Free tier (DNS is always free, R2 has 10 GB free + 10M free ops/mo)
- **What to capture:** Account ID, R2 access key + secret key, R2 endpoint URL
- **Store in `.env`:** `CLOUDFLARE_ACCOUNT_ID=<id>`, `CLOUDFLARE_R2_ACCESS_KEY=<key>`, `CLOUDFLARE_R2_SECRET_KEY=<secret>`, `CLOUDFLARE_R2_ENDPOINT=<url>`

### 5. ElevenLabs (only needed for UGC voiceover tracks)
- **URL:** https://elevenlabs.io
- **What for:** UGC-style voiceover when NOT using H3 native audio
- **Cost:** Free 10,000 characters/month (about 5-7 minutes of audio)
- **What to capture:** API key
- **Store in `.env`:** `ELEVENLABS_API_KEY=<key>`

Most clips will use H3's native audio and skip ElevenLabs entirely. Only enable this if you plan to do UGC-style "person reacting to pull" content with voice.

---

## Tier 2 — Platform approval (start today, takes days)

### 6. X (Twitter) developer account
- **URL:** https://developer.twitter.com
- **What for:** Publishing tweets via Social Stats (X API v2)
- **Approval time:** 1-3 days
- **What to capture:** API key, API secret, bearer token, access token, access secret
- **Store in `.env`:** `X_API_KEY=`, `X_API_SECRET=`, `X_BEARER_TOKEN=`, `X_ACCESS_TOKEN=`, `X_ACCESS_SECRET=`
- **Application form:** You'll need to write a 200-word description of what the app does. Adam drafts this for you if you ask: *"Adam, draft my X developer app description for a social media scheduler."*

### 7. Meta Graph API (for Instagram publishing)
- **URL:** https://developers.facebook.com/apps
- **What for:** Instagram Business account publishing
- **Approval time:** 1-7 days
- **Prerequisite:** Your Instagram account must be a Business or Creator account (Settings → Account → Switch to Professional Account in the IG app)
- **What to capture:** App ID, app secret, long-lived user access token, Instagram Business account ID
- **Store in `.env`:** `META_APP_ID=`, `META_APP_SECRET=`, `META_ACCESS_TOKEN=`, `META_IG_BUSINESS_ID=`
- **Scopes needed:** `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`

### 8. TikTok for Developers
- **URL:** https://developers.tiktok.com
- **What for:** TikTok Content Posting API
- **Approval time:** 1-3 days, sometimes longer if you're not in their beta
- **What to capture:** Client key, client secret, access token, open ID
- **Store in `.env`:** `TIKTOK_CLIENT_KEY=`, `TIKTOK_CLIENT_SECRET=`, `TIKTOK_ACCESS_TOKEN=`, `TIKTOK_OPEN_ID=`
- **Note:** TikTok's Content Posting API is in limited release as of mid-2026. You may need to waitlist.

---

## How to hand them off to Adam

After creating accounts 1-5 (you can wait on 6-8 for the platform reviews), send Adam a single message:

```
All accounts are set up. Here are the tokens:
- MiniMax: <token>
- fal.ai: <key>
- Telegram bot: <token>, chat_id <id>
- Cloudflare R2: <access>, <secret>, <endpoint>
- ElevenLabs: <key>

Validate them with dry-run API calls.
```

Adam validates each by making a single cheap API call. If anything fails, Adam tells you which one and what to fix.

For accounts 6-8 (platform approval), tell Adam when each gets approved and it integrates the credentials.

---

## Burner accounts for scraping

For any **login-gated scraping** (Twitter, Instagram, Reddit, Facebook), **use a dedicated burner account**. The platform can detect scripted access and lock the account. Don't tie your main to the pipeline.

Adam walks you through creating burner accounts and exporting cookies via Cookie-Editor when you set up Agent-Reach in Phase 0.

---

## Security notes

- **Never commit `.env` to git.** It's gitignored. Verify with `git status` before any commit.
- **Treat the X bearer token as production-grade.** It can post to your account.
- **Rotate Telegram bot token** if it leaks. Easy to do via @BotFather → `/revoke`.
- **Cloudflare R2 keys** can read/write to your bucket. Treat like AWS keys.

---

## What's NOT needed

You don't need accounts on these (the plan doesn't use them):

- OpenAI (we use local Ollama for caption generation, falling back to MiniMax API)
- Anthropic Claude (Adam runs inside Cursor, which already authenticates you)
- Midjourney / Leonardo.ai (we use ComfyUI + H3, not hosted image services)
- Zapier / Make.com (we use n8n, which is self-hosted)
