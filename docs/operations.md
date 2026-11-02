# Roadie operations guide

For everyday use, start with the [README](../README.md). This guide covers setup and maintenance tasks. Run commands from the project root unless a command changes folders explicitly.

## Configuration reference

`app.config.json` holds non-secret settings as JSON strings. The Python and web loaders read it relative to the repository, so supported launchers work regardless of where they are opened from.

Python reads only these credential names from the root `.env`:

| Setting | Purpose |
| --- | --- |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend access to Supabase. Never include it in the browser or APK. |
| `RAG_SERVICE_TOKEN` | Private authentication between the backend and AI service; at least 32 bytes. |
| `GEMINI_API_KEY` | Gemini API-key authentication, when used instead of Cloud credentials. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the Google service-account file on the current machine. |
| `GOOGLE_PLACES_API_KEY` | Nearby workshop/place search. |
| `YOUTUBE_API_KEY` | YouTube discovery and ingestion. |

Explicit process environment values take precedence over loaded settings. Old non-secret `.env` entries are ignored. The web loader does not read the root `.env`. A `.env` file is optional if required credentials are already in the process environment.

`SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` belong in JSON and are safe to pass to public clients. The admin uses its same-origin `/api/backend` proxy; `BACKEND_API_URL` selects the server-side upstream. The obsolete `NEXT_PUBLIC_API_URL` setting is no longer read.

`MINERU_API_URL` must point to Windows for the split-device deployment. Leaving it empty selects local MinerU execution, which requires MinerU on the backend machine. The Windows-specific `MINERU_EXECUTABLE` path is unused when remote OCR is selected.

Copying the project to a Mac does not make Windows virtual environments or credential paths valid there. Create native environments and adjust credential paths. Preserve existing credential values; do not put private keys in JSON or pass the whole configuration file to Flutter.

## Tailscale forwarding

Current device addresses:

| Device | Address |
| --- | --- |
| Windows OCR PC | `iphone15promax.tailcb3ca9.ts.net` |
| Mac backend and dashboard | `anqis-macbook-pro.tailcb3ca9.ts.net` |

All devices must belong to the same Tailscale network, with MagicDNS and HTTPS enabled. Device discovery alone does not verify that application services are running.

### Windows

`start-ocr.cmd` applies this mapping after OCR passes its health check when `MINERU_TAILSCALE_SERVE` is `"true"`:

```powershell
tailscale serve --bg --yes --https=443 http://127.0.0.1:8010
```

The launcher reads both ports from JSON. This updates the root route on that HTTPS port and replaces its previous target, including a previous backend target on port 8000. It leaves other routes alone.

Setting `MINERU_TAILSCALE_SERVE` to `"false"` skips future updates; it does not delete a saved mapping. To remove that mapping manually:

```powershell
tailscale serve --https=443 off
```

### Mac

Configure these manually once:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8000
tailscale serve --bg --https=8443 http://127.0.0.1:3000
tailscale serve status
```

`--bg` preserves forwarding across reboots; application launchers still need to be started. Use Serve for private access within Tailscale. The OCR API has no application token, so restrict access through Tailscale permissions. RAG port 8001 stays local and has no Serve target.

To check connectivity from the Mac after starting services:

```bash
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8001/openapi.json
curl -f https://iphone15promax.tailcb3ca9.ts.net/health
```

Health checks confirm that services respond, but do not prove Supabase sign-in, Gemini access, document extraction quality, or answer quality. Try a representative PDF and a real phone query before a demonstration.

## Database and administrator accounts

For a fresh database, follow [Supabase setup](../supabase/README.md) and use [supabase/init.sql](../supabase/init.sql). Do not rerun fresh-install SQL against an existing installation.

Supabase handles user authentication. Keep email confirmation and admin MFA enabled. Configure the mobile redirect `myroadie://auth/callback` and the dashboard redirect `https://anqis-macbook-pro.tailcb3ca9.ts.net:8443/auth/callback` in Supabase, plus local callbacks when used.

To create an administrator:

1. Register through the interface, confirm the email, and sign in once to create the application profile.
2. In Supabase's Table Editor, open `public.app_users` and find that account by email.
3. Change its `role` from `user` to `admin`.
4. Refresh the admin page and complete MFA setup.

If an existing administrator needs their confirmed Supabase identity linked to their original profile, use the trusted helper. It preserves the application ID and historical records:

```bash
.venv/bin/python -m scripts.link_supabase_admin AUTH_USER_UUID
```

On Windows, use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`.

## Restore document search

Use this when moving to a fresh Mac environment with existing processed documents in Supabase. Existing publication status does not mean the new Mac already has local search indexes.

For that first migration, use new, empty folders and keep the paths consistent. One possible set of JSON values is:

```json
{
  "OUTPUT_DIR": "output/viva-mac",
  "DOCUMENT_WORK_DIR": "output/viva-mac/documents",
  "CHROMA_PATH": "output/viva-mac/embeddings/chroma",
  "RAG_INDEX_WORK_DIR": "output/viva-mac/index-worker",
  "YOUTUBE_OUTPUT_DIR": "output/viva-mac/youtube"
}
```

Do not switch paths on an established installation as a routine restart step. Do not copy old indexes, worker ledgers, or YouTube caches into the new migration folders. Launcher logs stay under `output/logs` regardless of `OUTPUT_DIR`.

Stop any old backend, then run the backend alone on the Mac:

```bash
# Terminal 1
.venv/bin/python -m backend
```

In a second terminal, restore search from the currently stored document extractions:

```bash
# Terminal 2 — do not start the full app launcher at the same time
.venv/bin/python scripts/run.py index --once --restore-processed
```

This rebuilds local search artifacts from saved extraction ZIPs, including corrections and provenance, without resetting publication records. It also handles pending `awaiting_index` work. Review logs and the exit code, stop the standalone backend, then start the full stack.

Missing extractions, older formats, or chunk-count mismatches need review through the admin workflow. Do not reset records with SQL. If fresh OCR is needed, upload a new document or deliberately unpublish and reprocess an existing one. Retry/sync YouTube channels through the admin dashboard when rebuilding their local collection.

## AI service and memory

The normal launcher runs the backend, Next.js dashboard, and one RAG process. With `RAG_INDEX_WORKER_MODE` set to `"embedded"`, indexing shares the RAG process and cached model. `RAG_INDEX_POLL_SECONDS` controls the polling interval; the current JSON value is 15 seconds.

Use `"external"` only when a separate indexing worker is needed; the app launcher starts it in that mode. Do not start a standalone worker alongside the embedded worker. Different worker directories pointing to the same search database are unsupported.

On the 8 GB Mac, build indexes and sync YouTube separately from live demonstrations. A conservative starting point is `MODEL_DEVICE` set to `"cpu"`, `EMBEDDING_BATCH_SIZE` set to `"1"`, and `EMBEDDING_CPU_THREADS` set to `"2"`. These are optional tuning choices, not the current JSON values or measured proof that CPU beats MPS. Check Activity Monitor memory pressure during representative use before choosing settings.

The configured encoder is `nomic-ai/nomic-embed-text-v1.5`, with 768-dimensional output and an 8192-token limit. The reranker is `cross-encoder/ms-marco-MiniLM-L6-v2`. Models use the normal Hugging Face cache. First downloads, long documents, cloud calls, and relayed Tailscale transfers can all add startup or processing time.

## Build the Android app

Build on Windows with the existing Flutter/Android tooling. This command reads only the public settings from JSON and passes them to Flutter:

```powershell
$publicConfig = Get-Content -LiteralPath app.config.json -Raw | ConvertFrom-Json
Push-Location mobile
try {
    flutter pub get
    flutter build apk --release `
        "--dart-define=API_BASE_URL=$($publicConfig.API_BASE_URL)" `
        "--dart-define=SUPABASE_URL=$($publicConfig.SUPABASE_URL)" `
        "--dart-define=SUPABASE_PUBLISHABLE_KEY=$($publicConfig.SUPABASE_PUBLISHABLE_KEY)"
} finally {
    Pop-Location
}
```

The APK is written to `mobile/build/app/outputs/flutter-apk/app-release.apk`. Install it by trusted transfer or `adb install -r` while connected.

Use the same signing certificate as the installed app to update it without clearing data. Release currently uses the local debug signing key. If signatures do not match, locate the correct key rather than uninstalling the app. Rebuild after changing the public API or Supabase settings.

## Recovery and logs

| Log | Contains |
| --- | --- |
| `output/logs/backend.log` | Main backend and document-processing messages. |
| `output/logs/rag.log` | AI search and embedded indexing messages. |
| `output/logs/web.log` | Admin dashboard server messages. |
| `output/logs/ocr.log` | Windows MinerU messages. |
| `output/logs/index-worker.log` | Separate worker messages, when using external mode. |
| `output/logs/app-launcher.log` / `ocr-launcher.log` | Startup and shutdown failures. |

Logs rotate at 5 MiB with three backups. To follow OCR logs on Windows:

```powershell
Get-Content output/logs/ocr.log -Tail 80 -Wait
```

If a document stays at `awaiting_index`, inspect the RAG logs, shared token, backend address, worker lock, and extraction compatibility. Fix the cause before retrying; do not reset records.

For an acknowledged OCR task interrupted by a connection failure, retrying can resume the saved task. If upload status is unknown, the task failed or expired, or Windows OCR restarted, inspect the task and logs before archiving its `*.mineru-job.json` checkpoint and deliberately retrying. Blind resubmission can create duplicate work.

Finish active processing before shutdown. The launcher waits up to 120 seconds per child before forcing it to stop. Keep documents, search databases, credentials, signing keys, and recovery checkpoints even though Git ignores many of those files.

## Website article imports

The Mac extracts supported public HTML articles directly. The saved snapshot includes text, supported images, source metadata, and a content hash. Identical snapshots are rejected; changed content creates a new source instead of overwriting the previous one. Review the old source's publication status when importing an update.

The importer does not run JavaScript or crawl linked pages. Login/paywall pages and inaccessible or blocked sources are rejected. Video, interactive media, and SVG/canvas diagrams are not captured. Review the result against the original before publishing. An authorized PDF can use the normal PDF upload workflow if needed.
