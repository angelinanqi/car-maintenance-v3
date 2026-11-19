# Run the corrective adapter in the EXISTING connected Colab notebook

This package targets the observed grounding failures using actual local automotive-manual excerpts. It preserves the first run in Drive. It reloads the original base and creates a separate adapter, rather than continuing the first fine-tune.

1. Download/open the local `run_corrective.py` file from this directory.
2. In your ORIGINAL connected Colab notebook, wait for any running cell to finish, then click **+ Code** at the bottom.
3. Paste the contents of `COLAB-CELL.txt` into that new cell and run it.
4. In the upload dialog, select `run_corrective.py`. The script contains the prepared examples; do not upload the whole repository, credentials or other files.
5. Let it run once. It uses the installed libraries, downloads/loads the original base from cache, generates base answers, trains up to 30 optimizer steps with a 15-minute training limit checked at step boundaries, saves the adapter, and generates tuned answers. Setup, loading, comparison and export take additional time.
6. Download the offered ZIP. Results also live in `MyDrive/Roadie-finetuning/corrective-<timestamp>/`. Return the NEW `comparison.md` and `status.json` for review.
7. Do NOT run the original notebook export cell afterward: its RUN/CONFIG variables still refer to the first run. If export is appropriate, use `EXPORT-CELL.txt`, which saves to RUN2, the corrective run.

If the script says RUN/CONFIG are missing, do not Run all or restart training. Your original runtime state was lost; adapter recovery needs different loading instructions.

## What changed

- 176 automatically prepared automotive examples from five manual documents: 112 verbatim-source answers, 32 warning-only procedure-gap answers, and 32 missing-torque-specification answers.
- Source-first citation placement reduces dependence on a trailing citation surviving generation caps.
- Whole excerpts and targets fit within 1,024 tokens; no procedural excerpt is cut to fit.
- Exact positive and warning quotations are programmatically checked against source. These are conservative template targets, not human-verified automotive labels.
- Sixteen prepared comparison cases use two different manual document families. The actual bounded run uses 12 of them, plus the three EXPOSED prior development probes as regression checks. No reserved Roadie final evaluation questions are read or trained on.
- Exact normalized source hashes and source document names are disjoint across train/comparison sets. Similar concepts across car manuals can still overlap; this is not an independent expert benchmark.
- No Gemini/paid inference calls, no installation loops, no keepalive or serving. This is one bounded interactive training job; Colab resources remain subject to availability.

## Pass/fail interpretation

The goal is improved source fidelity, preserved conditions, missing-evidence boundaries, concise answers and citations. Compare the saved base/tuned outputs before claiming improvement. In particular, inspect whether the exposed brake warning still leads to fabricated repair stages and whether the oil answer is duplicated. These probes are already exposed and cannot be described as independent held-out automotive performance.

This package is a corrective attempt motivated by measured failures. It does not guarantee that training will improve the model. If the tuned outputs remain worse, preserve the experiment and use the best-performing validated model rather than claiming success from training loss alone.
