# Backend monitoring

From the repository root on the MacBook, use the same Python environment as the application:

```sh
.venv/bin/python -m shared.monitor
```

Start the application normally in another terminal (`./start-app.command` or `python scripts/run.py app` with the project's Python environment). Restart already running services after updating this code. The monitor refreshes every two seconds; Ctrl+C closes only the monitor. It adds no HTTP endpoints, frontend features, cloud services, databases, or Python dependencies.

For a single snapshot or machine-readable output:

```sh
.venv/bin/python -m shared.monitor --once
.venv/bin/python -m shared.monitor --once --json
```

On Windows, the equivalent interpreter is `.venv\Scripts\python.exe`. Continue starting MinerU with `start-ocr.cmd` in its separate `.venv-ocr` environment.

## Architecture reviewed and reused

The backend is not the only Mac process: the launcher starts the FastAPI application, a private RAG HTTP service, an external index worker by default, and the website capture worker when enabled. Indexing can instead run embedded in the RAG process. YouTube syncs run as RAG background tasks.

Supabase document rows already form the persistent document queue. The backend has separate OCR and preparation loops, durable source/revision checkpoints, retryable extraction handoffs, mutation locks, and persisted errors. The index worker downloads completed extractions through the existing authenticated internal API, indexes them in Chroma, and acknowledges the exact source revision. This monitoring adds no second queue and never changes queue ownership or retry decisions.

MinerU 3.4.5 runs its native task API on Windows. The Mac submits a PDF, checkpoints the acknowledged task ID, polls pending/processing/completed, then downloads and safely unpacks the ZIP. Ambiguous submissions remain checkpointed and are never automatically resubmitted. Existing backend request IDs are returned as `X-Request-ID`; the private RAG client now forwards that ID. Document IDs correlate OCR, preparation and indexing across their separate processes. Each stage also has a unique span ID and parent ID, so concurrent retrieval stages do not overwrite each other.

Previously, the launcher rotated plain stdout/stderr logs (5 MiB, three backups), OCR CLI runs had per-document diagnostics, and RAG logged aggregate timings after a query completed. These were useful after failures but did not provide consistent live stage state, cross-service correlation, or freshness evidence. Existing logs and persisted job state remain available.

The new mechanism writes small JSON events to one rotating file per instrumented process. A daemon thread writes a heartbeat with active stages every five seconds. The terminal reader follows those files and reconstructs current operations even if opened during a long stage. No model inference, database querying, or document reading is performed by the monitor.

## What the display means

- `starting`: the process is initializing. RAG warmup can take minutes.
- `running`: a recent heartbeat confirms process liveness, with no active instrumented stage.
- `busy`: a recent heartbeat and active stage(s).
- `stopped`: an orderly shutdown was recorded.
- `disconnected`: a local heartbeat is more than 16 seconds old, or the independent Windows health probe failed. For a local service this can mean a crash, suspension, severe CPU starvation, or a different checkout/log directory.
- `unknown`: insufficient or expired evidence. Database/vector observations expire after 60 seconds. A successful database operation is labeled **last operation succeeded**, not an unconditional health guarantee.
- `failed`: a failed operation or incompatible MinerU health response. Recent stage results show failures, exception types, and durations even when an API returns a fallback answer with HTTP 200.

Stages are actual function boundaries: document upload, OCR, remote health/submission/wait/download/unpack, preparation and extraction packaging, handoff, indexing, normalization, chunking, embedding, vector writes, query preparation, Gemini intent analysis, hybrid/semantic/keyword retrieval, result merging, reranking, evidence filtering, answer generation, Gemini calls, database access and YouTube syncs. Active stages are nested; their durations overlap and should not be added together. A queue attempt finishing does not mean the entire document is indexed. Follow its document ID through `document_preparation: queued`, `document_index: queued`, and `document_index_attempt` completion. Deferred work stays in the existing durable queue.

HTTP timing ends when response headers are ready. Some database operations use direct SDK calls rather than the shared helpers; telemetry is useful evidence, not complete database tracing. Recent results are stage durations, not fabricated progress percentages or estimated completion times.

## Windows visibility and limits

The monitor probes the configured `MINERU_API_URL/health` every five seconds on its own background thread, with a two-second timeout. No probe failures affect application work. Successful health means the compatible task API is reachable; it does not prove that models/GPU are ready. During a document, the backend logs MinerU's reported task state, worker task ID, configured remote hostname, disconnections, and reconnections. Repeated transport failures during polling produce one warning per outage instead of one every two seconds.

`machine` always identifies the host that wrote an event. `worker_host` identifies the Windows endpoint observed from the Mac, and `worker_task_id` links it to native MinerU tasks. Remote state is an observation, not a Windows-origin heartbeat. The native API does not expose separate text/table/image extraction stages or remote log streaming, so those are not invented. Mac-side download/unpack/packaging stages are measured separately.

For internal MinerU failures or a worker processing a task submitted by another client, inspect `output/logs/ocr.log` on Windows. The monitor labels OCR `busy` when this backend has an active remote OCR operation; health alone cannot discover all other clients' work. Keep the existing loopback/Tailscale arrangement; this change opens no additional network ports or unauthenticated monitoring API.

## Log files and privacy

Structured logs default to:

```text
output/logs/monitor/backend-<pid>.jsonl
output/logs/monitor/rag-<pid>.jsonl
output/logs/monitor/index-worker-<pid>.jsonl
output/logs/monitor/website-worker-<pid>.jsonl
```

Embedded indexing shares the RAG file. Each file rotates at 5 MiB with three backups (about 20 MiB per process). When an instrumented process starts, monitoring files older than seven days are removed. Retention cleanup runs on service startup, not as a separate scheduled service.

Events contain UTC timestamps, originating machine, service/PID, module, stage, severity, IDs and durations as applicable. Request query strings, bodies, user messages, prompts, documents, filenames, credentials, exception values and SDK response bodies are excluded. Exceptions retain their class and stack locations without source lines. Legacy application logging is mirrored as a safe diagnostic with module, source location, severity and exception stack locations; its original free-form message and formatting arguments are deliberately omitted. Look at the surrounding named stages for meaning.

Existing launcher logs under `output/logs/` and local OCR diagnostics under the document work directory are unchanged and have their existing content/retention behavior. Keep all runtime logs private; they are already excluded by `.gitignore`.

To watch structured logs directly on macOS:

```sh
tail -F output/logs/monitor/backend-*.jsonl
rg '"state": "failed"|"level": "WARNING"|"level": "ERROR"' output/logs/monitor
rg 'YOUR-DOCUMENT-ID-OR-REQUEST-ID' output/logs/monitor
```

The terminal keeps a bounded recent history; rotated files retain older evidence. Old PID entries can remain visible as stopped/disconnected until the monitor restarts. Its initial scan reads only the last 256 KiB of each recently modified current file; a fresh heartbeat restores active operations within five seconds.

## Configuration

Set these string values in `app.config.json`, or override them with environment variables **before starting services**. This repository loads only credentials from `.env`; nonsecret monitoring settings placed there will not take effect.

| Setting | Default | Effect |
| --- | --- | --- |
| `MONITOR_ENABLED` | `1` | `0`, `false`, or `off` disables telemetry, heartbeat threads, files, and the monitor's worker probes. Existing launcher logs continue. |
| `MONITOR_LOG_LEVEL` | `INFO` | Minimum event severity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Service heartbeats remain enabled so liveness stays observable. `WARNING` reduces file traffic but omits successful stage results. |
| `MONITOR_LOG_DIR` | `output/logs/monitor` | Shared local directory for all Mac processes and monitor. Relative paths resolve from the repository root. |

`--interval 5` changes the terminal refresh rate. It does not change worker polling or service heartbeats. If telemetry files cannot be written, processing continues; missing/stale telemetry is never treated as proof of health.

## Troubleshooting workflow

1. Open the monitor and start the app. Local processes should transition from starting to running/busy. Database/vector state remains unknown until actual instrumented operations supply evidence.
2. Start Windows OCR and verify the health line changes from disconnected to available. If it does not, check `MINERU_API_URL`, Tailscale connectivity, Windows firewall, the native API port and `output/logs/ocr.log`. An incompatible health response requires MinerU 3.4.5/task protocol 2. A CLI OCR setup without `MINERU_API_URL` remains a local `ocr_extraction` operation, with no remote health evidence.
3. Upload a test PDF and queue processing using the existing application. Follow the document ID through OCR, preparation, extraction handoff and indexing. For a long `mineru_wait`, use the reported task ID in the Windows logs. For an uncertain submission, inspect the existing `.mineru-job.json` checkpoint and Windows tasks before any manual retry; do not delete it blindly.
4. Send a normal manual-based chatbot query. Follow `X-Request-ID` from the backend to RAG. Compare embedding, retrieval, reranking, evidence filtering and Gemini durations. Warnings plus failed child stages reveal fallback behavior even if the overall reply succeeds.
5. Temporarily disconnect the OCR network while a task is polling. The independent health line should disconnect, and polling should record the outage once, then record reconnection and resume the saved task when available. Existing deadlines still apply. This is best tested with a disposable document.
6. If an operation looks stuck, check whether its enclosing process heartbeat is still fresh. A fresh heartbeat shows the process can report telemetry; it does not prove the stage will make progress. Read exception types/stack locations, document status/error in the existing application, and legacy logs for the underlying dependency failure. A disappeared process will become disconnected, never automatically completed.

For a viva, keep the terminal beside the existing document/chat interface. No monitoring UI needs to be built into the admin web or Flutter app.
