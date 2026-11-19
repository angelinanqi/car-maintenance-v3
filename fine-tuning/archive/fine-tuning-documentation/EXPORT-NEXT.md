# Next: export the completed Colab model

The supplied status records 50 training steps and completed comparisons. See review.md for mixed results and observed regressions. This directory does not yet contain model weights.

If the original Colab runtime is connected and still holds `model` and `tokenizer`:

1. Scroll to **9 — OPTIONAL export** in the original notebook.
2. Change only `EXPORT_GGUF = False` to `EXPORT_GGUF = True`.
3. Run only that export cell. Do not rerun training or Run all.
4. Wait for **Export saved:**. This operation takes additional memory/disk/time; preserve your adapter backup first.
5. In Google Drive → Roadie-finetuning → your original timestamped run folder → gguf-export, download the exported `.gguf` file to this local `fine-tuning/` directory. Preserve the original adapter ZIP and the executed notebook as experiment evidence.
6. Keep the exact original adapter/config/tokenizer and config.json available in case export or conversion needs retrying. Do not paste access tokens or private credentials into chat or notebook cells.

The original export cell uses the Gemma-3-specific Q8_0 route in the official notebook. A later Q4_K_M conversion is intended for the 8 GB Mac. The Q8 export is an intermediate; do not switch Roadie's configuration before import and validation.

If the runtime was lost, do not start training again. The saved adapter can be reloaded for export; the recovery notebook is at `dumpster/roadie-finetuning-20261106/Roadie_Recovery.ipynb`. Its first inspection cells locate/back up the original run. Optional GPU cells reload and compare the adapter. Export is off by default.

After the GGUF is present locally, the remaining integration is: prepare an appropriate quantization; import under a separate Ollama tag using the model's correct chat template/stop tokens; test full Roadie paths; then set OLLAMA_MODEL in app.config.json and restart services. Retain the current working model for rollback.

Export references:
- https://github.com/unslothai/notebooks/blob/main/nb/Gemma3_(4B).ipynb
- https://docs.ollama.com/import
