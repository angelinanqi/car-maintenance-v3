# Fine-tuned model deployment

**Current configuration:** Roadie selects `roadie-gemma3-ft`, the corrective LoRA adapter on the `gemma3:4b` base. The deployment records below describe the original import; current application validation is separate from those historical smoke checks.

At the time of this deployment, Roadie selected `roadie-gemma3-ft` at `http://127.0.0.1:11435`. The backend, RAG and dashboard services were restarted and checked.

This is the actual corrective adapter (30 training steps), not a renamed base model. Official llama.cpp converted the saved F32 LoRA matrices to a small GGUF adapter. Ollama loads it with the existing `gemma3:4b` Q4_K_M base. Its log records 476 adapter tensors loaded. No large full-model merge or Colab GGUF export was necessary.

## Ready for testing

- Existing mobile app: use the same backend connection; no Flutter rebuild is required for this model change.
- Dashboard: http://127.0.0.1:3000/login
- Backend: http://127.0.0.1:8000/health
- Normal later startup: run `./start-app.command` from the project root. Do not start a second launcher while the current one is running.
- Service logs: `output/logs/ollama.log`, `rag.log`, `backend.log`; launcher console: `fine-tuned-launcher-console.log`.

Try the no-pin washer-nozzle question, an engine-oil check, an ordinary explanation and your own follow-ups. Complete the signed-in phone/manual test cases. The performed HTTP checks do not replace device UAT.

## Deployment files

`Modelfile` creates a separate tag from the installed base and `roadie-corrective-lora-f32.gguf`. Once imported, Ollama uses its own cached model/adapter blobs; the app does not load a training folder on each request. Keep the exported adapter for reproducing the import on another machine. Large weights are ignored by Git.

Recreate on this Mac if needed:

```sh
OLLAMA_HOST=127.0.0.1:11435 ollama create roadie-gemma3-ft -f fine-tuning/deployment/Modelfile
```

The minimal base-config copy retains architecture fields but omits bitsandbytes quantization metadata because the converted tensors are F32 LoRA matrices, not quantized base weights. The original pinned training configuration and safetensors are unchanged. Official conversion code revision, artifact hashes and checks are saved in `deployment.json`.

`ollama-model-info.json` records the inherited Gemma template and `<end_of_turn>` stop setting, plus the actual ADAPTER layer. The application still supplies runtime context/output/temperature options. No custom giant SYSTEM prompt or unbounded correction loop was added.

## Checks

- Direct fine-tuned Ollama answer: HTTP 200, supported no-pin response with S1.
- Full private RAG HTTP: three cases passed (washer, complete manufacturer oil sequence + original image descriptor, missing brake-procedure boundary).
- Backend/RAG/web: HTTP 200.
- 25 overhaul tests and 26 local-provider/safety tests passed. The latter's old hard-coded model expectation was updated to the configured setting.

The current inference base is the installed Ollama quantization, not a byte-identical copy of Colab's NF4 checkpoint. Adapter dimensions/load and actual runtime answers were checked; identical Colab outputs or broader quality gains are not assumed. Keep the application safeguards in place.

## Model selection

The fine-tuned model is required for the application. Keep `OLLAMA_MODEL` set to `roadie-gemma3-ft`; inference failures must not silently switch to the base model. The base tag and training artifacts remain available for explicitly isolated diagnostics. Do not overwrite historical evaluation scores with deployment smoke checks.
