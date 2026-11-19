# Roadie Colab fine-tuning pilot

1. Open https://colab.research.google.com/ and sign in.
2. File → Open notebook → Upload → select `Roadie_Gemma3_QLoRA.ipynb` from this directory.
3. Runtime → Change runtime type → T4 GPU. A new uploaded notebook may not inherit the GPU setting from your blank notebook. Release the blank notebook's runtime if it holds the GPU allocation.
4. Run the installation cell, then the remaining cells in order. Approve Google Drive access when asked. If installation asks for a restart, restart once and continue at the Drive/model cells. Never paste `.env`, `gemini-api-key.json`, or account tokens into notebook cells.
5. Keep the session open. Training is capped at 50 optimizer steps and 45 minutes checked after each optimizer step. Setup/downloads/evaluation/export are additional time. Do not rerun the training cell.
6. The required run finishes at “DONE: adapter + logs + comparisons saved”. Outputs live under `MyDrive/Roadie-finetuning/<timestamp>/`. Download the automatically offered ZIP and save this notebook WITH outputs using File → Download → Download .ipynb.
7. Return `status.json`, `comparison-metrics.json`, and `comparison.md` for review. If a cell fails, send its last error lines and cell heading. The adapter or latest checkpoint may already be saved.
8. GGUF export is optional and disabled by default. It is a separate deployment step; the app is not switched automatically. After downloads/export, Runtime → Disconnect and delete runtime.

## What the notebook does

- Loads Unsloth Gemma 3 4B in 4-bit; trains rank-8 LoRA on language attention/MLP modules, freezing vision.
- Downloads pinned Finetune-RAG (1,653 synthetic, mixed-domain examples), checking the exact SHA256.
- Keeps the original target plus a single `[S1]` attribution; includes full original/preceding/following chunks. No fictitious distractors in this pilot. This is a simplified positive-context SFT recipe, not reproduction of the authors' experiment.
- Groups identical filenames or identical normalized source chunks before splitting; selects up to 320 training, 24 validation and 12 test examples after rejecting oversized examples intact.
- Masks prompt tokens, checks response labels and lengths, saves checkpoints every 10 steps, and saves the final adapter before post-training evaluation.
- Compares the SAME loaded base model with adapters disabled versus enabled using identical greedy generation settings. The base is a different quantization from the Mac Ollama installation; comparisons are internal to Colab.
- Reports validation loss, word overlap, citation presence and generation caps. These are diagnostics, not factual accuracy or proof of improvement.
- Includes 3 exposed Roadie development probes separate from public held-out examples. They test generation only, not retrieval, attachment delivery or deterministic procedure display.

## What you can honestly report

After actual training: parameter-efficient supervised fine-tuning of Gemma 3 4B for evidence-conditioned QA, using an automatically prepared subset of public synthetic Finetune-RAG, with recorded split, hyperparameters, optimizer steps, adapter artifacts and base/tuned comparisons. Report actual selected counts and completed steps from saved files.

Do not describe this as automotive-expertise training, a human-verified automotive dataset, reproduction of the paper's results, certified safety, or demonstrated improvement without reviewing actual answers. The model can regress. Keep Roadie's manufacturer-procedure preservation and all existing safeguards. The reserved Roadie final evaluation dataset is not read or used by this notebook.

An adapter file is a real fine-tuning artifact but is not an Ollama model. If your rubric requires integration, reserve time to merge/export, quantize appropriately and test importing the resulting model before changing `OLLAMA_MODEL`. The official Gemma notebook currently documents Q8_0/BF16/F16 export; this notebook's optional Q8 export may be too large for the 8 GB Mac alongside Roadie. Do not delete the original working model.

## Resource use

One interactive notebook, one bounded training job, cached model/dataset downloads, no Gemini or paid inference APIs, no tunnels, no model server, no keepalive, no automatic session retries. These are practical limits, not a guarantee against Colab termination. Colab availability and usage limits fluctuate.

## Validation and reproducibility

`local-validation.json` records checks run locally. Actual CUDA training is not tested on the Mac. Runtime package resolution and GPU availability can still cause errors; the notebook saves `pip-freeze.txt`, exact model/dataset revisions, data splits and run configuration to diagnose them. Pinning Transformers/TRL/datasets follows the official notebook fetched during preparation; other package versions are recorded at runtime.

`data_prep.py` is the standalone preparation implementation embedded in the notebook. Only the `.ipynb` needs uploading; no repository files are needed. The notebook and supporting files are in the ignored `dumpster/` development directory, so back them up with your submission; they are not production runtime dependencies.

Sources and attribution:
- https://github.com/unslothai/notebooks/blob/main/nb/Gemma3_(4B).ipynb — model/trainer/install/export examples adapted under LGPL-3.0; upstream license: https://github.com/unslothai/notebooks/blob/main/LICENSE
- https://huggingface.co/datasets/pints-ai/Finetune-RAG — Apache-2.0 synthetic dataset, revision 3374821d5e10262bc523828de8a9fefa88055ddf
- https://huggingface.co/unsloth/gemma-3-4b-it-unsloth-bnb-4bit — Gemma model terms
- https://research.google.com/colaboratory/faq.html — Colab resource policies
