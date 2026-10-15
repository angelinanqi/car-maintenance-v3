# AI retrieval and indexing

The RAG service answers scoped questions using indexed documents and optional
YouTube transcripts. The indexing worker downloads backend extractions, chunks
the Markdown, creates embeddings, and stores them in Chroma.

## Setup

From the repository root, using Python 3.12:

```powershell
py -3.12 -m venv .venv-rag
.\.venv-rag\Scripts\python.exe -m pip install -r requirements.txt
```

Configure the root `.env`:

- Set the same `RAG_SERVICE_TOKEN` (at least 32 bytes) for the backend and RAG.
- Set `RAG_SERVICE_URL` for backend-to-RAG calls and `RAG_BACKEND_URL` for
  worker-to-backend calls. Defaults are `http://127.0.0.1:8001` and
  `http://127.0.0.1:8000` respectively.
- Choose `LLM_PROVIDER=gemini` with `GEMINI_API_KEY` and an accessible
  `GEMINI_MODEL`, or `LLM_PROVIDER=ollama` with a running Ollama server and
  the configured `OLLAMA_MODEL` installed.
- Enable `LLM_FALLBACK_ENABLED` only if Ollama is also configured.

Start each process in its own terminal:

```powershell
.\.venv-rag\Scripts\python.exe -m rag.service
```

```powershell
.\.venv-rag\Scripts\python.exe -m rag.index_worker
```

Keep the RAG API private. The service and worker must share persistent Chroma and
source artifact locations under `output/`. The embedding model may download on
first use; changing its model or dimension requires reindexing.

## Optional YouTube ingestion

Set `YOUTUBE_API_KEY` and `YOUTUBE_CHANNEL_URL`, then run:

```powershell
.\.venv-rag\Scripts\python.exe -m rag.app.youtube.pipeline
```

Assign relevant videos to their vehicle or category scope in the admin dashboard.
See the [root README](../README.md) for document upload and publication.
