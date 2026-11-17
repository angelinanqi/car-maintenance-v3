# Fine-tuned model

The app requires **`roadie-gemma3-ft`**: the Ollama `gemma3:4b` Q4_K_M base with the corrective LoRA adapter. It is already selected in [app.config.json](../app.config.json). You do not need to train again to run or move the app.

The current adapter came from the **30-step corrective run**. Earlier 50-step pilot records describe a different experiment. Training records and historical reports are evidence of those runs, not current setup instructions.

## Import on a new Mac

Install Ollama and keep these files together:

- [deployment/Modelfile](deployment/Modelfile)
- `deployment/roadie-corrective-lora-f32.gguf`

If the app is stopped, start a temporary model server in one terminal:

```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

In another terminal, run from the project root:

```bash
OLLAMA_HOST=127.0.0.1:11435 ollama pull gemma3:4b
OLLAMA_HOST=127.0.0.1:11435 ollama create roadie-gemma3-ft -f fine-tuning/deployment/Modelfile
OLLAMA_HOST=127.0.0.1:11435 ollama show --modelfile roadie-gemma3-ft
```

The last command should show an **ADAPTER** entry. Stop the temporary server with **Ctrl+C**, then run `./start-app.command`. If the app's managed server is already running, use it for the import commands instead of starting a second server.

Check `http://127.0.0.1:8001/health` after startup: the model must be `roadie-gemma3-ft` and `adapter_verified` must be `true`. Ollama's load log records 476 adapter tensors. The app rejects a base-model override and does not silently fall back to it.

## What to keep

| Location | Contents |
| --- | --- |
| [corrective/dataset.json](corrective/dataset.json), [manifest.json](corrective/manifest.json) | Prepared examples and their source split |
| [corrective/run_corrective.py](corrective/run_corrective.py) | Original Colab training script |
| [Saved corrective run](../dumpster/corrective-20261106-111215-UTC/) | Safetensors adapter, tokenizer, configuration, logs, and base/tuned answers |
| [deployment/deployment.json](deployment/deployment.json) | Original conversion revision, hashes, and import checks |
| [review.json](review.json) | Historical pilot review |
| [Historical fine-tuning documents](../dumpster/fine-tuning-documentation/) | Previous reports and superseded instructions, preserved unchanged |

Ollama caches the imported model itself. Keep the exported GGUF and original training artifacts so you can reproduce the import. Large weights are ignored by Git and must be backed up separately. Original document filenames in historical JSON records now refer to the archived documents above.

## Understand or repeat the training

The corrective dataset contains **176 training examples** and **16 prepared comparison examples** from separate manual document families. It uses source quotations, warning-only gaps, and missing-specification cases. These are automatically prepared targets, not expert-labelled automotive answers.

The recorded run used LoRA rank **8**, learning rate **0.00008**, gradient accumulation **4**, a **1,024-token** training limit, seed **3407**, and up to **30 optimizer steps**. The exact configuration and actual answers are in the saved corrective run above.

To repeat the original procedure in Colab:

1. Use the original prepared notebook environment with a GPU and its `RUN` and `CONFIG` variables. The script depends on this state.
2. Wait for any existing training to finish.
3. Run [corrective/COLAB-CELL.txt](corrective/COLAB-CELL.txt) and select `run_corrective.py` in its upload dialog.
4. Let the job finish once, then save its adapter and results from `MyDrive/Roadie-finetuning/corrective-<timestamp>/`.

If the original runtime state is gone, use the preserved [recovery notebook](../dumpster/roadie-finetuning-20261106/Roadie_Recovery.ipynb) to inspect and recover the saved run first. The optional `EXPORT-CELL.txt` is a separate full-model export; it is not needed to import the existing GGUF adapter.

For another trained adapter, use official llama.cpp LoRA conversion with the code revision recorded in `deployment.json`, verify compatibility with the serving base, and validate actual Roadie answers before replacing the deployed adapter. Preserve previous results. Lower training loss alone does not establish factual accuracy, and reserved final evaluation questions must stay out of training and tuning.
