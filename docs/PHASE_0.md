# Phase 0 — Install the brains

**Goal:** Get Adam (the orchestrator) and Agent-Reach (the internet-scraping tool) loaded into Cursor. Once this is done, every other phase is driven by talking to Adam.

**Time:** ~30 minutes
**Outcome:** You can say things like *"Adam, build me the Folder B brand pack"* and Adam does it.

---

## Why this happens outside the project folder

Adam lives in **Cursor**, not in this repo. This repo is the project Adam manages. Two distinct things:

| Thing | Where it lives | Who installs it |
|---|---|---|
| **Adam** (orchestrator brain) | `~/.cursor/skills/` and `~/.cursor/rules/` | Cursor, after you paste the install prompt |
| **Agent-Reach** (internet tools) | `~/.agent-reach/` | Cursor, after you paste the install prompt |
| **This repo** (project state) | `/Volumes/Content SSD/Content Pipeline/` | Git, by you |

You don't clone Adam. You don't symlink it. You just paste one URL into Cursor and Adam runs the install.

---

## Step 1 — Install Adam into Cursor (10 min)

1. **Open Cursor**
2. Open any chat (Cmd+L on Mac, Ctrl+L on Windows)
3. Paste this exact message:

```
Install Adam from https://github.com/Justinmendezai/The-Adam-Repo and help me get started.
```

4. **Approve the permission prompts** Cursor shows you. Adam will:
   - Clone the Adam repo to a working directory
   - Copy skill folders into `~/.cursor/skills/` (the folder name is the skill — never flatten `SKILL.md`)
   - Set up `~/.cursor/rules/adam.md` so every Cursor chat in this project loads Adam's rules
   - Trigger the **`calibrate` skill** ([Adam skills/calibrate/SKILL.md](https://github.com/Justinmendezai/The-Adam-Repo/blob/main/skills/calibrate/SKILL.md)) which interviews you

5. **Answer the calibrate interview.** Adam asks:
   - Your technical level (be honest — it adjusts its explanations)
   - Your preferences (terse vs verbose, what to skip)
   - Who you are (operator profile — affects the language Adam uses)
   - What the project is (the pipeline — affects the skill chain it pulls in)

   These answers get written to `adam/context/*.md` in this project (so they survive across Cursor restarts).

6. **At the end of calibrate, Adam offers to run `setup-adam`.** Say yes.

`setup-adam` creates the project skeleton:

```
packet/         # your product brief (you + Adam fill it in)
plan/           # Adam's plans + ADRs
slices/         # vertical-slice task breakdowns
agent-control/  # durable orchestrator state
adam/context/   # the calibration files
adam/memory/    # decisions, handoffs, research
```

The skeleton was already created when this repo was bootstrapped. `setup-adam` will **adopt** the existing structure rather than clobbering it.

---

## Step 2 — Install Agent-Reach (10 min)

Adam gives Adam the ability to scrape Twitter, Instagram, Reddit, YouTube, Bilibili, GitHub. Without this, Folder A doesn't get built.

Once Adam is calibrated, send this message in Cursor:

```
Install Agent Reach from https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md
```

Adam reads the install instructions and runs them. You'll get prompted for:
- **System install?** Default is `--env=auto` (safe, no system changes). Use `--system` only if you want Agent-Reach to write to your shell config and install missing tools.
- **Which login-gated channels?** Twitter, Reddit, Facebook, Instagram, XiaohongShu need cookies/browsers. Pick what you actually want to scrape. For gacha references, you mostly want: **Twitter (X), Reddit, Instagram, YouTube**.
- **Cookie export?** For platforms that need it (Twitter, IG), Agent-Reach walks you through Cookie-Editor.

**Use a dedicated burner account for any login-gated channel** — platform ToS risk if you scrape from your main.

After install, run this in your terminal to verify everything works:

```bash
agent-reach doctor
```

You should see all 6 zero-config channels (web, YouTube, RSS, full-web search, GitHub, V2EX) green, plus any login-gated ones you enabled.

---

## Step 3 — Hand off to Adam (the rest of this is just talking)

From here on, **every phase is a conversation**. The runbooks `docs/PHASE_1.md`, `docs/PHASE_2.md`, etc. tell you what to say to Adam at each step.

A few conventions:

- **Don't type slash commands.** `/calibrate`, `/go`, `/setup-adam` are Cursor-only shortcuts. Adam drives via plain speech. Just say "Adam, do X."
- **Never tell Adam to "run the next command."** Adam runs commands itself when needed.
- **If you're stuck**, say *"Adam, what should we do next?"* — Adam checks `agent-control/` and the run ledger and tells you.
- **Long session?** When Cursor feels slow, say *"Adam, run session-steward."* It compacts state and writes a handoff so the next chat picks up clean.

---

## What "done" looks like

After Phase 0 you should be able to open Cursor, say *"Adam, what's next?"* and get a sensible answer that points at Phase 1.

If you can't, re-run `agent-reach doctor` and check `adam/context/*.md` was actually written. If the calibration interview never ran, send this to Adam:

```
Run the calibrate interview again. I don't think we finished it.
```

---

## Common issues

| Symptom | Fix |
|---|---|
| Cursor says "command not allowed" during install | Approve the permission prompt. If it's persistent, check Cursor → Settings → Features → Bash that `git` and `pip` aren't blocked. |
| Adam's skill folders are missing | The skill name is the **folder**, not `SKILL.md`. If you see `SKILL.md` files instead of folders, the install flattened them — delete `~/.cursor/skills/SKILL.md` (the file) and re-run install. |
| Agent-Reach `doctor` shows red for Twitter/IG | Expected — those need cookies. Run `agent-reach configure x` and follow the cookie-export walkthrough. |
| `agent-reach doctor` shows red for everything | Python 3.10+ missing. Install via `brew install python@3.11` (Mac) or `winget install Python.Python.3.11` (Windows). |
| Adam keeps telling me to type `/something` | Wrong mode. Tell Adam: "Don't tell me to type slash commands. Run them yourself or drive via plain speech." |
| Cursor ran `npx convex deploy` instead of `npx convex dev` | Edit `~/.cursor/rules/adam.md` and add: "Never use `npx convex deploy` — only `npx convex dev`." |

---

## Next phase

When Adam is calibrated and Agent-Reach is installed:

**→ `docs/PHASE_1.md`** (build Folder B brand pack, Folder A reference vault, set up local infra, create accounts)
