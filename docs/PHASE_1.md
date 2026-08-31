# Phase 1 — Foundation

**Goal:** Reference library + brand DNA + local infrastructure + accounts all set up. After Phase 1 you can run a single end-to-end "pick a reference, generate an image, post it" loop manually.

**Time:** ~1 week (mostly waiting on account approvals)
**Outcome:** First end-to-end test post (manually triggered) reaches your Telegram for approval.

---

## 1.1 — Folder B (Brand DNA)

**Say to Adam:**

```
Run the intake skill. I want to build the brand pack for Gatcha Kingdom. Start with the existing brand assets — there's a style guide at /Volumes/Content SSD/Gacha Luka/docs/STYLE_GUIDE.md and a Tailwind config at /Volumes/Content SSD/Gacha Luka/tailwind.config.ts. Pull the palette and fonts from there. Then grill me on anything that isn't already documented.
```

**What Adam does:**
1. Reads `../Gacha Luka/docs/STYLE_GUIDE.md` and `../Gacha Luka/tailwind.config.ts` (read-only — never edits them)
2. Pre-populates `brand/guidelines.md` with the real hex codes, font names, mascot, voice
3. Pre-populates `brand/voice.md` with tone examples pulled from the live site's copy
4. **Interviews you** via the `grill-me` skill until the decision tree closes — covering:
   - Do/don't list for ad copy
   - Banned words (you already have legal guidance on gambling framing)
   - Reference caption examples (you need 20-50, tagged by theme)
   - Watermark placement and opacity
5. Copies `../Gacha Luka/Logo/*` into `brand/logo/` (so the originals stay safe in `Gacha Luka/`)
6. Copies `../Gacha Luka/public/*.png` (the lower-res versions) into `brand/screenshots/` as read-only snapshots
7. Write-locks `brand/screenshots/` after seeding

**Your job in this step:** spend ~2 hours answering Adam's questions and reviewing the pre-populated brand pack. The pack gets written once. Subsequent edits only when the brand evolves.

**Folder B is now done when:**
- [ ] `brand/guidelines.md` reflects the real Gatcha Kingdom palette (already pre-filled)
- [ ] `brand/voice.md` has 10+ tone examples
- [ ] `brand/logo/` has `GK_Logo.png` + `GK_Logo.jpg` + a watermark variant (you create the watermark variant by overlaying the logo at 12% opacity on a transparent PNG — Adam will do this via Pillow if you ask)
- [ ] `brand/screenshots/` has at least 10 snapshots from the live site (the gk-cabinet-* PNGs are good picks)
- [ ] `brand/captions/reference_captions.json` has 20-50 examples tagged by theme
- [ ] `brand/fonts/` has M PLUS Rounded 1c + Noto Sans JP + Inter (download from Google Fonts)

---

## 1.2 — Folder A (Reference Vault)

**Say to Adam:**

```
Run the brainstorm skill to figure out which competitor accounts we should scrape for Folder A, then dispatch Agent Reach to pull 100-300 references. After scraping, run triage so I can review them.
```

**What Adam does:**
1. Brainstorms target accounts (Genshin Impact, Honkai Star Rail, Fate/GO, Nikke, Punishing Gray Raven, plus non-gaming references like Bandai Namco's capsule toy accounts, Pop Mart blind boxes — pick 5-10 accounts)
2. Runs Agent-Reach to scrape: pulls the asset + a metadata JSON sidecar with `platform`, `format`, `theme`, `style_tags`, `composition`, `engagement_tier` (initially unrated), `scraped_at`
3. Drops everything into `references/inbox/`
4. Runs `triage` to bin into inbox / ready / archived
5. Asks you to spend **one focused 4-hour session** reviewing the top 100 and only A-tier (top 20% by engagement relative to follower count) enters `references/ready/`. Everything else goes to `references/archived/` with a reason.

**Your job in this step:** spend the 4-hour curation session. This is the **single highest-ROI task** in the whole pipeline — a great reference library beats a great prompt every time.

**Reference picker logic lives at `scripts/reference_picker.py`.** It reads `references/ready/*.json`, applies the weighting (A-tier 3x, B-tier 1x, C-tier 0.3x), and returns one random pick. Adam will write this script as part of `dispatch-builder` once you've curated ~20+ references.

**Folder A is now done when:**
- [ ] `references/ready/` has at least 20 A-tier references (target: 50 by end of Phase 2)
- [ ] `references/archived/` has the rest with reasons
- [ ] `scripts/reference_picker.py` exists and is tested (see Phase 2)

---

## 1.3 — Local Infrastructure (Windows PC)

**Where:** Your Windows PC with the RTX 5070. Not on this Mac. All commands below are **Windows commands** — run them in PowerShell or Windows Terminal.

**Say to Adam:**

```
Set up the local infrastructure for the ad pipeline. The Windows PC has an RTX 5070 (Blackwell, 12 GB VRAM), 32 GB DDR5, 1 TB NVMe, Windows 11. Write me a runbook for the steps I need to run.
```

**What Adam does:** runs `research-and-plan` and produces a Windows-specific runbook (similar to the checklist below, but tuned to whatever current versions are appropriate). Confirm the runbook with you, then you execute the commands.

**Hard checklist (run these on the Windows PC):**

### 1.3.1 — System prep

```powershell
# Set the power plan so ComfyUI jobs don't get throttled
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  # High Performance

# Enable Long Path support (some Windows builds cap at 260 chars)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -Type DWord

# Verify the GPU is visible to the OS
nvidia-smi
# Expected: lists "NVIDIA GeForce RTX 5070", driver version 570+, CUDA 12.8+
```

If `nvidia-smi` shows an older driver, install the latest from [nvidia.com/drivers](https://www.nvidia.com/drivers). The 5070 needs **driver 570+** for full Blackwell support.

### 1.3.2 — WSL2 + Docker Desktop

```powershell
# Install WSL2
wsl --install

# Install Docker Desktop from docker.com (download the Windows installer)
# During install, check "Use WSL 2 instead of Hyper-V"
# After install, in Settings → Resources → WSL Integration, enable your distro
```

Verify:

```powershell
docker --version
docker run hello-world
```

### 1.3.3 — ComfyUI (native Windows install — NOT in Docker, for direct GPU)

```powershell
# Clone ComfyUI to a fast path (NVMe, not Documents)
cd C:\
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Create a venv with Python 3.11
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip

# Install PyTorch nightly for Blackwell support (CUDA 12.8)
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Install ComfyUI requirements
pip install -r requirements.txt

# First run (downloads models — start with just SD 1.5 to verify the install)
python main.py
# ComfyUI listens on http://127.0.0.1:8188
```

**Upgrade ComfyUI to ≥0.30.0** so the H3 native nodes are available:

```powershell
cd C:\ComfyUI
git pull
pip install -r requirements.txt
```

**Install the MiniMax H3 native nodes** (already merged in ComfyUI 0.30.0):

```powershell
# H3 nodes come with ComfyUI 0.30+ — verify by opening ComfyUI in a browser:
# http://127.0.0.1:8188
# Right-click → Add Node → search "MiniMax" → you should see:
#   - EmptyMiniMaxH3LatentAV
#   - MiniMaxH3ImageToVideo
#   - MiniMaxH3ReferenceToVideo
#   - MiniMaxH3SigmaShift
```

**Install IP-Adapter Plus + ControlNet Aux:**

```powershell
cd C:\ComfyUI\custom_nodes
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus
git clone https://github.com/Fannovel16/comfyui_controlnet_aux
# Plus the ComfyUI Manager for one-click node installs
git clone https://github.com/ltdrdata/ComfyUI-Manager
# Restart ComfyUI — Manager loads in the menu
```

### 1.3.4 — Python + Node (for n8n and scripts)

```powershell
# Install Python 3.11 if not already (https://www.python.org/downloads/windows/)
# Make sure "Add to PATH" is checked

# Install Node.js 20 LTS from https://nodejs.org

# Verify
python --version   # 3.11.x
node --version     # v20.x
npm --version      # 10.x
```

### 1.3.5 — n8n (in Docker — n8n doesn't need GPU)

```powershell
# Create a working dir for n8n
mkdir C:\n8n-data
cd C:\n8n-data

# Create docker-compose.yml (Adam will write this during Phase 2)
# Initial placeholder:
docker run -it --rm `
  --name n8n `
  -p 5678:5678 `
  -v C:\n8n-data:/home/node/.n8n `
  docker.n8n.io/n8nio/n8n
```

n8n listens on `http://localhost:5678`. Default user: `admin` / a randomly generated password in the logs.

### 1.3.6 — Social Stats (in Docker)

```powershell
# Clone Social Stats
git clone https://github.com/cbsshekhawat18-lab/social-stats-social-media-manager.git C:\social-stats
cd C:\social-stats

# Adam writes the docker-compose.yml during Phase 2. Initial placeholder:
docker compose up -d
```

### 1.3.7 — Wake-on-LAN (so cron fires even when PC sleeps)

In BIOS: enable Wake-on-LAN. In Windows Device Manager → Network adapter → Power Management → check "Allow this device to wake the computer" and "Only allow a magic packet to wake the computer."

n8n will use a `wakeonlan` node to send the magic packet 5 minutes before each cron tick.

### 1.3.8 — Verify

```powershell
# All four services should respond
curl http://127.0.0.1:8188  # ComfyUI — should return HTML
curl http://127.0.0.1:5678  # n8n — login page
# Social Stats port varies; check its docker-compose.yml
```

Tell Adam "Local infra is up" and it will run `verify.sh` (which tests all four services respond and that `nvidia-smi` still sees the 5070).

---

## 1.4 — Accounts (you do these, Adam waits)

**Say to Adam:**

```
List the accounts I need to create and the URLs for each.
```

**What Adam does:** lists the following. None of these can be done by the agent — they require your credentials and sometimes payment info.

### Checklist

| # | Service | URL | What for | Approve time |
|---|---|---|---|---|
| 1 | **MiniMax platform** | https://platform.minimax.io | Cloud H3 video gen + H3-Context-IR + H3-Regenerate-2K | Instant |
| 2 | **fal.ai** | https://fal.ai | H3 Max speed tier + Kling 2.6 Pro hero tier | Instant (load $20 credit) |
| 3 | **Telegram bot** | https://t.me/BotFather | Approval gate | 5 min |
| 4 | **Cloudflare** | https://dash.cloudflare.com/sign-up | DNS + R2 backup | Instant (free tier) |
| 5 | **X developer** | https://developer.twitter.com | Publishing via Social Stats | 1-3 days |
| 6 | **Meta Graph API** | https://developers.facebook.com/apps | Instagram publishing (need Business account) | 1-7 days |
| 7 | **TikTok for Developers** | https://developers.tiktok.com | TikTok Content Posting API | 1-3 days |
| 8 | **ElevenLabs** | https://elevenlabs.io | UGC voiceover (only needed if not using H3 native audio) | Instant (free 10k chars/mo) |

### Notes

- **Use a burner/disposable account for any login-gated scraping channel** (X, IG, Reddit, FB). The platform can detect scripted access and lock the account. Don't tie your main to the pipeline.
- **X developer access** is the slow one — apply early. You'll need to write a 200-word description of what the app does. Adam drafts this for you if you ask.
- **Meta Graph API** requires an Instagram Business or Creator account. Switch your IG account type in the IG app: Settings → Account → Switch to Professional Account → Business.
- **TikTok Content Posting API** is in closed beta-ish territory; you might need to wait for an approval email.
- **H3 Community License** — read it before Phase 3 ships H3-generated clips publicly. Adam reviews it during Phase 4 `council`.

### When you're done

Send Adam a single message:

```
All accounts are set up. Here are the API tokens (paste them):
- MiniMax: <token>
- fal.ai: <token>
- Telegram bot: <token> (chat_id is <id>)
- Cloudflare R2: <access_key> <secret_key>
- X: <bearer_token>
- Meta: <access_token>
- TikTok: <access_token>
- ElevenLabs: <api_key>
```

Adam writes these into `.env` (gitignored) and validates each one with a dry-run API call. If anything's broken, Adam tells you which one.

---

## Done with Phase 1?

Send Adam:

```
Phase 1 is done. Run verify.sh and tell me what's missing.
```

Adam runs the verify script and tells you which checklist items are still open. When everything's green, you move to Phase 2.

---

## Next phase

**→ `docs/PHASE_2.md`** — image pipeline (ComfyUI on the 5070, n8n workflow, Telegram approval)
