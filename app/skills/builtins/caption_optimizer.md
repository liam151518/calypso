---
name: Caption Optimizer
enabled: true
description: Tightens social captions for engagement.
post_process_re: "(?i)\b(just|simply|very|really)\b\s*"
tags: ["copy", "caption"]
---

When the operator asks for a social caption, output it with these properties:

1. **Front-load the hook.** The first 6 words determine whether the rest gets read. Lead with the benefit, the surprise, or the question — not "Introducing" or "We're excited to".
2. **One sentence in the body.** Two if absolutely necessary. Three is a wall of text that gets skipped.
3. **No emojis unless the brand voice asks for them.** Calypso defaults to text-only — operators can opt-in via Settings.
4. **Hashtags at the end, separated by a line break.** 3–5 hashtags max. Mix 1 broad + 2 niche + 1 brand.
5. **CTA is a soft next-step**, never "BUY NOW". "Tap to see", "Link in bio", "Drop a 🔥 if you agree" all work.
6. **Total length: under 140 characters** for X and TikTok; under 220 for Instagram; under 300 for LinkedIn.

After the LLM returns, strip filler adverbs (`just`, `simply`, `very`, `really`) — the `post_process_re` regex handles that automatically.
