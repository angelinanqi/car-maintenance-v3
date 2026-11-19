# AI pipeline

Roadie searches published references before answering. Gemma writes the answer using selected evidence. The app checks citations and values and can return labelled source excerpts when it cannot verify a complete answer.

## How it works

1. **Prepare:** Windows MinerU extracts PDF text, tables, and images. The admin reviews the source and its vehicle coverage.
2. **Index:** The worker chunks prepared content, embeds it with `nomic-ai/nomic-embed-text-v1.5`, and stores it in local Chroma. Published learning guides and emergency content also enter search.
3. **Retrieve:** A question uses its permitted vehicle/topic scope and recent conversation context. Vector and keyword search find candidates.
4. **Rank:** `cross-encoder/ms-marco-MiniLM-L6-v2` selects relevant passages.
5. **Answer:** Ollama runs **`gemma3:4b`** by default with the selected text and extracted table evidence. Citations, numeric relationships, and application safety rules are checked before delivery. Original images and videos are attached separately.

Gemini is used for ingestion-time image descriptions. It does not generate interactive chat answers. Generic references are distinguished from verified manufacturer documents. Videos come from the available catalogue.

## Windows OCR setup

Install Python **3.12** and Tailscale on Windows. From the project root:

```powershell
py -3.12 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt
.\start-ocr.cmd
```

The launcher expects **MinerU 3.4.5**, starts its task API on port **8010**, and configures Tailscale HTTPS forwarding when `MINERU_TAILSCALE_SERVE` is `"true"`. Enable Tailscale HTTPS and make the `tailscale` command available on `PATH`.

Wait for **OCR ready** before processing a PDF. The first document may also require model downloads. On the Mac, `MINERU_API_URL` in [app.config.json](../app.config.json) must point to this Windows machine's Tailscale HTTPS address.

## Mac setup and checks

Use the root `.venv` from the [main setup](../README.md#first-time-mac-setup). If `gemma3:4b` is missing, use the Ollama desktop app or start a temporary Ollama server with `ollama serve`, then run `ollama pull gemma3:4b`. Stop any temporary server when the download finishes. The normal `./start-app.command` launcher starts RAG, its own Ollama server, and the embedded indexing worker together.

The configured model server is `http://127.0.0.1:11435`. The private RAG service is `http://127.0.0.1:8001`. The backend and RAG share `RAG_SERVICE_TOKEN` from `.env`.

After startup:

```bash
curl -f http://127.0.0.1:8001/health
```

With the default model, the response should report `status: "ok"`, `model: "gemma3:4b"`, and `adapter_verified: false`.

Model downloads can make the first startup slow. On the 8 GB Mac, avoid large indexing or video-sync jobs during interactive use. Keep the existing embedding and Chroma settings together; changing the embedding model or dimension requires rebuilding its index.

## Restore search on a new Mac

Supabase publication records alone do not contain the local search index. Preserve `output/` when moving an existing installation. If local indexes are missing on a fresh Mac, rebuild from the extraction bundles stored in Supabase. Use the default output paths in `app.config.json`, starting with empty local data folders:

```bash
# Terminal 1, project root: backend only
.venv/bin/python -m backend
```

```bash
# Terminal 2, project root: one restoration pass
.venv/bin/python scripts/run.py index --once --restore-processed
```

Check the logs and exit status, stop the standalone backend, then start `./start-app.command`. Do not run the full launcher alongside these recovery commands. Retry video-channel syncs through the dashboard if their local collection needs rebuilding.

## Processing problems

| Symptom | Check |
| --- | --- |
| OCR unreachable | Windows launcher, Tailscale, and `MINERU_API_URL/health` |
| Document stays at `awaiting_index` | `output/logs/rag.log`, shared token, and extraction compatibility |
| Model does not load | `output/logs/ollama.log` and the [Mac model setup](#mac-setup-and-checks) |
| Answer says evidence is missing | Review source coverage, publication, index status, and the actual extracted passage |

Keep `output/`, including worker state and OCR task checkpoints. Fix failed work through the admin workflow; do not delete checkpoints or resubmit an uncertain OCR task blindly. Full request and processing logs are in `output/logs/`.
