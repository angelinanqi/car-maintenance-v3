# Car Maintenance and Assistance

FastAPI backend, Flutter Android app, Next.js admin dashboard, Supabase database
and storage, and a private RAG service with a document-indexing worker.

## Install and configure

Use Python 3.14 for the shared backend/RAG `venv`, Python 3.12 for MinerU in
`.venv-ocr`, Node.js 22/npm, Flutter with Dart compatible with `^3.11.5`, and the
Android SDK. Keep existing environments and credentials on each computer.
Commands below run from the repository root in PowerShell.

```powershell
py -3.14 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
py -3.12 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt
npm.cmd --prefix web-app/frontend ci
```

Configure the root `.env` with server-only `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET` and `RAG_SERVICE_TOKEN`. Both secrets
must contain at least 32 bytes. Set `MINERU_EXECUTABLE` to the absolute path of
`.venv-ocr/Scripts/mineru.exe` and `MINERU_BACKEND=pipeline`.

Set `LLM_PROVIDER=gemini`, `GEMINI_API_KEY` and an accessible `GEMINI_MODEL`, or
use `LLM_PROVIDER=ollama` with a running Ollama server and its `OLLAMA_MODEL`
installed. `LLM_FALLBACK_ENABLED=true` also requires Ollama. Optional nearby
workshop search uses `GOOGLE_PLACES_API_KEY`; YouTube ingestion uses
`YOUTUBE_API_KEY` and `YOUTUBE_CHANNEL_URL`.

Set browser-reachable `NEXT_PUBLIC_API_URL` and matching `CORS_ORIGINS`. Default
ports are backend `8000`, private RAG `8001`, dashboard `3000`; override with
`BACKEND_PORT`, `RAG_HTTP_PORT` and `FRONTEND_PORT`. For separate hosts, configure
`RAG_SERVICE_URL` for backend-to-RAG calls and `RAG_BACKEND_URL` for the worker's
backend connection. Keep the RAG service private and its token consistent.

Follow [Supabase setup](supabase/README.md) before starting services. Register an
account, then promote its normalized email in the Supabase SQL Editor:

```sql
update public.app_users set role = 'admin' where email = 'your-email@example.com';
```

## Build and run

Build the dashboard after installing dependencies or changing source/public
configuration, then use the launcher for your operating system:

```powershell
npm.cmd --prefix web-app/frontend run build
.\start-app.cmd
```

On macOS, create `venv` with `python3.14` and `.venv-ocr` with `python3.12`, use
`venv/bin/python`, `.venv-ocr/bin/mineru` and `npm`, then run
`chmod +x start-app.command run-youtube.command` and `./start-app.command`.
Recreate environments on each computer; absolute OCR paths are machine-specific.

The launcher starts one backend, the RAG API, the document-indexing worker and the
production dashboard, then opens `/login`. Keep its terminal open; Ctrl+C stops
its child services. `--no-browser` skips opening the browser; `--without-rag`
starts only the backend and dashboard. The launcher reuses a local Ollama server
or starts one when configured and available. Supabase and remote Ollama servers
are managed separately. Listening checks establish startup only.

To run services independently, use separate terminals:

```powershell
.\venv\Scripts\python.exe -m backend
.\venv\Scripts\python.exe -m rag.service
.\venv\Scripts\python.exe -m rag.index_worker
npm.cmd --prefix web-app/frontend start
```

The API's `/health` checks liveness; `/docs` exposes its API contract. Run one
backend process because processing and content-mutation locks are process-local.
MinerU starts on demand for PDF extraction; Markdown skips OCR. Model weights may
download on first use.

For a backend-only installation, use `backend/requirements.txt`; keep OCR in its
separate environment. The dashboard build requires TypeScript and its type
packages. Emotion and TipTap ProseMirror packages satisfy runtime peer
dependencies; Transformers and einops support the embedding model loaded at
runtime. Test fixtures and test runners are not included.

After deployment, check `/health`, sign in to the dashboard, and verify document
processing, a scoped chat answer and the enabled external integrations. A passing
build or liveness check alone does not verify Supabase, OCR or model access.

## Documents and persistent data

Upload documents through the admin dashboard to Supabase, assign vehicle/category
scopes, process, wait for indexing, review, and publish documents and their scopes.
The worker consumes backend extraction bundles; local sample folders are not an
ingestion source. Published learning guides and reviewed emergency protocols are
read from Supabase per request without a separate persisted content index.

Keep `output/` writable and persistent. Preserve document processing files,
`output/sources` manifests, `output/embeddings/chroma`, the
`output/index-worker/managed_indexes.json` ledger and `output/youtube` ingestion
state. Custom `OUTPUT_DIR`, `DOCUMENT_WORK_DIR`, `CHROMA_PATH`,
`RAG_INDEX_WORK_DIR` and `YOUTUBE_OUTPUT_DIR` must point to consistent persistent
locations for the corresponding services. Changing the embedding model or its
dimension requires reindexing through the upload/extraction flow.

Optional YouTube ingestion runs separately with `run-youtube.cmd` or
`run-youtube.command` (or `python -m rag.app.youtube.pipeline`). Assign indexed
videos to scopes in the dashboard. It does not run during normal startup.

Chat also loads a read-only maintenance summary for the signed-in user's active
vehicle. It shares task/schedule views and due-status calculations with the mobile
app. Answers can cite the latest recorded service per task, custom reminders and
calculated due status as `[P2]`, alongside manual or published-content citations.
Unlinked service records stay separate; missing history remains unknown. Admin
chats do not receive personal maintenance context.

Mobile chat includes maintenance question shortcuts and a vehicle-scoped "View
maintenance" action beneath cited maintenance answers. Both clients display
saved records and vehicle profiles in the supporting-source list; the web admin
preview explains that personal records are available in signed-in mobile chat.

The summary includes up to 50 tasks and the latest standalone service per saved
title (up to 50), with total counts retained. Generation selects whole relevant
entries within a 3000-character budget, also limited to half the remaining source
budget. It is not a full-history or spending-analysis feature. No new database
tables, dependencies, model tools or SQL generation are required. Restart both
the backend and private RAG service after updating them together.

## Android build

```powershell
Set-Location car_app
flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=https://your-api-host
```

APK output: `car_app/build/app/outputs/flutter-apk/app-release.apk`. Configure
release signing in `car_app/android/app/build.gradle.kts` for distribution; the
current configuration uses the local debug signing key. `API_BASE_URL` is a build
define; Flutter does not load `.env`. Account access in release builds requires
HTTPS. Preserve native Android resources, Gradle wrapper/local SDK configuration
and bundled emergency guides, which support offline guest access.
