# Brand LoRA Training — Runbook (Phase 4.2)

**Goal:** Train a LoRA on the 30+ best approved posts so every generation carries the Gatcha Kingdom visual DNA.

**When:** After Phase 2 has run for 2-3 weeks and you have 30+ approved posts.
**Where:** Windows PC with the RTX 5070.
**Time:** ~6-12 hours (mostly unattended training).

---

## Prerequisites

Before you start, you need:

- [ ] 30+ approved images/videos in `agent-control/approved-assets/` (or the equivalent output dir)
- [ ] ComfyUI 0.30+ installed on the Windows PC (per Phase 1.3)
- [ ] The brand LoRA training set assembled: brand/screenshots/ + brand/logo/ + approved posts
- [ ] kohya-ss/sd-scripts installed with Blackwell support
- [ ] 50 GB free disk space on the NVMe (training outputs are large)

## Step 1 — Assemble the training set

On the Windows PC, in `C:\ComfyUI\training\gachakingdom-v1\`:

```
gachakingdom-v1/
├── images/
│   ├── 001_approved_pink_cabinet.jpg    # from approved posts
│   ├── 002_approved_damascus.jpg
│   ├── ...
│   ├── brand_pink_logo.png               # from brand/logo/
│   ├── brand_cabinet_screenshots/*.png   # from brand/screenshots/
│   └── ...
├── captions/
│   ├── 001.txt                          # one caption per image
│   ├── 002.txt
│   └── ...
└── trigger_words.txt                    # "gachakingdom" — the word that activates the LoRA
```

For each image, the matching `.txt` file in `captions/` should contain:

```
gachakingdom, gacha capsule toy, Japanese arcade aesthetic, warm pink and cyan lighting
```

Always start with the trigger word `gachakingdom`. Describe what's in the image using brand-aligned terms (from `brand/guidelines.md`).

## Step 2 — Install kohya-ss

```powershell
# In a fresh venv (don't reuse ComfyUI's venv — kohya-ss has different deps)
python -m venv C:\kohya-venv
C:\kohya-venv\Scripts\activate
pip install torch==2.5.1+cu118 --index-url https://download.pytorch.org/whl/cu118
# For Blackwell (RTX 5070), you need PyTorch 2.7+ with CUDA 12.8 — see the official kohya-ss install docs
pip install -U kohya-ss-sd-scripts
```

Verify Blackwell support:
```powershell
python -c "import torch; print(torch.cuda.get_device_capability())"
# Expected: (12, 0)  for RTX 5070
```

If you get a different capability number or an error, check kohya-ss's latest GitHub release — they support new GPUs quickly.

## Step 3 — Configure training

Create `C:\ComfyUI\training\gachakingdom-v1\config.toml`:

```toml
[model]
pretrained_model_name_or_path = "C:/ComfyUI/models/checkpoints/sd_xl_base_1.0.safetensors"
output_dir = "C:/ComfyUI/models/loras/"
output_name = "gachakingdom-v1"

[dataset]
train_data_dir = "C:/ComfyUI/training/gachakingdom-v1/images"
caption_extension = ".txt"

[training]
resolution = 1024
train_batch_size = 2
num_epochs = 10
save_every_n_epochs = 2
learning_rate = 1e-4
lr_scheduler = "cosine"
optimizer = "AdamW8bit"
mixed_precision = "bf16"
network_rank = 8           # low rank prevents memorization
network_alpha = 16
network_module = "networks.lora"

[logging]
log_dir = "C:/ComfyUI/training/gachakingdom-v1/logs"
logging_dir = "C:/ComfyUI/training/gachakingdom-v1/tensorboard"
```

## Step 4 — Train

```powershell
cd C:\ComfyUI\training\gachakingdom-v1
accelerate launch --num_processes=1 --mixed_precision=bf16 `
  -m kohya_ss.sd_scripts.sdxl_train `
  --config_file config.toml
```

Training takes ~4-8 hours on the RTX 5070 with the above config. Watch the TensorBoard:
```powershell
tensorboard --logdir=C:\ComfyUI\training\gachakingdom-v1\tensorboard
```

Look for:
- Loss should drop smoothly from ~0.15 to ~0.05 by end of epoch 5
- No loss spikes (means an unstable learning rate or bad data)
- Generated samples (saved every 2 epochs) should show clear brand DNA

## Step 5 — Validate

After training, run the validation workflow:

1. Open ComfyUI at http://127.0.0.1:8188
2. Load `comfyui/01-image-with-style-reference.json` (the workflow with the LoRA loader)
3. Set the LoRA path to `C:\ComfyUI\models\loras\gachakingdom-v1.safetensors`
4. Generate 10 test images with different references
5. Check: does the brand DNA come through? Cabinet colors, neon palette, mascot style, watermark positioning

If the LoRA is too strong (overfit — every image looks the same), reduce `network_rank` to 4 and retrain.
If too weak (no brand DNA), increase `network_alpha` to 24 and retrain.

## Step 6 — Deploy

Once the LoRA passes validation:

1. Copy `gachakingdom-v1.safetensors` to this repo at `comfyui/models/loras/gachakingdom-v1.safetensors`
2. Commit (it's gitignored but you can use `git add -f`)
3. Update the n8n workflow to reference the new LoRA path
4. Re-test the full pipeline end-to-end

## Cost / time

- **Setup:** ~30 min (assembling training data + installing kohya-ss)
- **Training:** ~4-8 hours (unattended)
- **Validation:** ~30 min
- **Total:** ~6 hours over 1-2 days

## What to do if training fails

| Symptom | Likely cause | Fix |
|---|---|---|
| Loss doesn't drop | Learning rate too low or bad data | Increase lr to 2e-4, or remove low-quality images |
| Loss spikes mid-training | Bad image (corrupted, mislabeled) | Find the spike epoch in TensorBoard, identify the image, remove it |
| Generated images look identical (overfit) | Rank too high or training too long | Lower rank to 4, reduce epochs to 6 |
| No brand DNA visible (underfit) | Rank too low or training too short | Raise rank to 16, increase epochs to 15 |
| CUDA out of memory | Batch size too high | Reduce `train_batch_size` to 1 |
| Validation: brand DNA present but artifacts (grain, color shift) | Mixed precision issue | Try `mixed_precision = "fp16"` or train longer |

## After training

Update `plan/adr/0002-brand-lora-v1.md` (create this ADR if it doesn't exist) with:
- Final rank/alpha
- Final loss
- Sample validation images
- Notes on what to tune next time

## When to retrain

Retrain when:
- 30+ new approved posts accumulated (significant style drift from new content)
- Brand palette changes (new accent color, new cabinet design)
- The pipeline starts generating off-brand images (catches it during council review)

Typical cadence: every 2-3 months, or whenever the brand evolves.
