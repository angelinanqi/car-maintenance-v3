# Car Maintenance and Assistance

FastAPI backend, Flutter Android app, Next.js admin dashboard, Supabase database
and storage, and a private RAG service with a document-indexing worker.

The learning companion connects
admin-published learning activities, grounded questions, calculated service plans,
saved resources and mechanic preparation. Existing databases require the additive
[`learning_companion.sql`](supabase/migrations/learning_companion.sql) migration
before deploying this version.

## Project layout

- `backend/`: FastAPI application. HTTP endpoints live in `routes/`, application
  logic in `services/`, public request/response models in `models.py`, and session
  access checks in `auth.py`.
- `rag/`: Private RAG API, indexing worker, and ingestion/retrieval/generation
  pipeline under `app/`.
- `shared/`: Python contracts, document element formats, maintenance extraction,
  mechanic-question helpers, and HTTP error responses used by both services.
  This package does not import either application.
- `web/`: Next.js administrator dashboard. Routes live in `src/app/admin/`,
  schedule-specific code in `src/features/schedules/`, reusable components in
  `src/components/`, and backend requests in `src/api/`. Existing `/user/...`
  links redirect to `/admin/...` and retain query parameters.
- `car_app/`: Flutter Android app, with repositories in `lib/data/`, models in
  `lib/models/`, screens in `lib/screens/`, and reusable widgets in `lib/widgets/`.
- `supabase/`: Consolidated fresh-install schema, original schema and additive migrations.
- `scripts/`: Production service launcher and PDF page renderer.
- `output/`: Ignored persistent processing data and local indexes.

## Install and configure

Use Python 3.14 for the shared backend/RAG `.venv`, Python 3.12 for MinerU in
`.venv-ocr`, Node.js 22/npm, Flutter with Dart compatible with `^3.11.5`, and the
Android SDK. Keep existing environments and credentials on each computer.
Commands below run from the repository root in PowerShell.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
py -3.12 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt
npm.cmd --prefix web ci
```

Configure the root `.env` with server-only `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET` and `RAG_SERVICE_TOKEN`. Both secrets
must contain at least 32 bytes. Set `MINERU_EXECUTABLE` to the absolute path of
`.venv-ocr/Scripts/mineru.exe` and `MINERU_BACKEND=pipeline`.
`MINERU_TIMEOUT=7200` allows up to two hours per OCR attempt; this is also the default.
OCR attempts save MinerU output to
`output/documents/<document-id>/ocr/<document-id>.mineru.log` (under
`DOCUMENT_WORK_DIR` if overridden). Failed attempts include the end of this log
in the document's error message. The log is overwritten on the next OCR attempt.

Set `LLM_PROVIDER=gemini`, an accessible `GEMINI_MODEL`, and either
`GEMINI_API_KEY` or Google Cloud credentials as described below. Alternatively,
use `LLM_PROVIDER=ollama` with a running Ollama server and its `OLLAMA_MODEL`
installed. `LLM_FALLBACK_ENABLED=true` also requires Ollama. Optional nearby
workshop search uses `GOOGLE_PLACES_API_KEY`; YouTube ingestion uses
`YOUTUBE_API_KEY`. Add channels under **Topics and related videos → YouTube
channels** in the admin dashboard; channel URLs are saved in Supabase.

Set browser-reachable `NEXT_PUBLIC_API_URL` and matching `CORS_ORIGINS`. Default
ports are backend `8000`, private RAG `8001`, dashboard `3000`; override with
`BACKEND_PORT`, `RAG_HTTP_PORT` and `FRONTEND_PORT`. For separate hosts, configure
`RAG_SERVICE_URL` for backend-to-RAG calls and `RAG_BACKEND_URL` for the worker's
backend connection. Keep the RAG service private and its token consistent.

For a fresh database, run [`supabase/fresh_schema.sql`](supabase/fresh_schema.sql)
once; it includes all current migrations. Follow [Supabase setup](supabase/README.md)
before starting services. Register an
account, then promote its normalized email in the Supabase SQL Editor:

```sql
update public.app_users set role = 'admin' where email = 'your-email@example.com';
```

## Build and run

Build the dashboard after installing dependencies or changing source/public
configuration, then use the Windows launcher:

```powershell
npm.cmd --prefix web run build
.\start-app.cmd
```

Recreate environments on each computer; absolute OCR paths are machine-specific.

The launcher starts one backend, the RAG API, the document-indexing worker and the
production dashboard, then opens `/login`. Keep its terminal open; Ctrl+C stops
its child services. `--no-browser` skips opening the browser; `--without-rag`
starts only the backend and dashboard. The launcher reuses a local Ollama server
or starts one when configured and available. Supabase and remote Ollama servers
are managed separately. Listening checks establish startup only.

To run services independently, use separate terminals:

```powershell
.\.venv\Scripts\python.exe -m backend
.\.venv\Scripts\python.exe -m rag.service
.\.venv\Scripts\python.exe -m rag.index_worker
npm.cmd --prefix web start
```

The API's `/health` checks liveness; `/docs` exposes its API contract. Run one
backend process because processing and content-mutation locks are process-local.
MinerU starts on demand for PDF extraction; Markdown skips OCR. Model weights may
download on first use.

After extraction completes, temporary Supabase connection errors are retried
automatically: up to three attempts per operation, then another recovery pass
every 15 seconds. Completed extractions are checkpointed in `output/documents`
so the handoff can resume after a backend restart without rerunning OCR. Preserve
this directory when restarting or deploying the backend.

For a backend-only installation, use `backend/requirements.txt`; keep OCR in its
separate environment. The dashboard build requires TypeScript and its type
packages. Emotion and TipTap ProseMirror packages satisfy runtime peer
dependencies; Transformers and einops support the embedding model loaded at
runtime.

After deployment, check `/health`, sign in to the dashboard, and verify document
processing, a scoped chat answer and the enabled external integrations. A passing
build or liveness check alone does not verify Supabase, OCR or model access.

## Documents and persistent data

Document review saves each admin's checklist and last source position by document
revision. Apply [`supabase/migrations/document_review_progress.sql`](supabase/migrations/document_review_progress.sql)
to existing databases before deploying the updated backend and dashboard. Fresh
installations include it in the initial schema. Review entries link to known PDF
pages; text without reliable page metadata uses manual navigation. Saved checklist
decisions do not approve or publish a document. Clarification questions and the
final source check remain explicit admin actions.

In the document review, admins can correct extracted section text, edit table
cells, or repair table structure in HTML while comparing the original. Each
correction requires a reason and source confirmation, retains the original
extraction and an audit history inside the bundle, and queues a fresh index
revision without rerunning OCR. The document must be offline; corrected content
needs indexing and a new review before publication. Existing schedule references
are not rewritten automatically. Later preparation requests rebuild from the
corrected bundle, and illustration reviews preserve its corrected text and tables.
This uses the existing extraction storage and requires no additional migration.

The document workspace also provides **Test this document**. Admins can save
questions for an associated vehicle/topic, run one or a batch of up to 10, inspect
answers and retrieved evidence, and record Passed/Needs fixing/Not reviewed with
private notes. Only the selected current indexed document enters the preview;
unpublished sources remain unavailable to driver chats. The existing source
verification and answer restrictions apply. Expected-answer notes are retained
for reviewers and are not sent to the model. Questions survive source changes;
older results are marked out of date when the revision, question, verification or
context changes. The latest 50 runs are shown, and archived questions retain
their historical results. Tests do not approve or publish documents.
Existing databases need [`supabase/migrations/document_testing.sql`](supabase/migrations/document_testing.sql).
Restart the backend, private RAG service and dashboard together after deployment.

The home dashboard and reference library summarize the latest run for each active
test question, including published documents that need follow-up. Answer corrections,
outdated results and failed runs have separate counts and library filters. Follow-up
links open the relevant question and result, including results older than the latest
50 runs. Archived questions are excluded; missing test status remains a loading error.
Apply [`supabase/migrations/document_test_follow_up.sql`](supabase/migrations/document_test_follow_up.sql)
after the document testing migration to index the latest-run lookup. Restart the
backend and dashboard for this follow-up integration; it does not change publication rules.

Maintenance assistance uses existing Supabase extraction bundles to list tables,
confirm item columns and prepare suggestions in the admin editor. Review and
publication remain explicit admin actions. Existing installations need
[`supabase/migrations/maintenance_assistance.sql`](supabase/migrations/maintenance_assistance.sql);
fresh installations include it in the initial schema. The worker maintains local
inventory artifacts automatically; admin review decisions live in Supabase.

In Service schedules, **Draft a schedule from this manual** can send a confirmed
table, all its cells and extracted notes to the configured private RAG provider.
AI proposals retain cited evidence and stay separate from the schedule until an
admin checks and accepts each row, selects rows to add, and saves the schedule
draft. First/subsequent timing, conflicting rules and unsupported units require
manual entry. Saved proposals are bound to the vehicle, document revision and
table selection; concurrent changes reject late generation results. This uses
the existing `maintenance_assistance` JSON data and needs no additional migration.
Restart the backend, private RAG service and dashboard together after deployment.
Schedule drafting has its own generation budget: `SCHEDULE_DRAFT_MAX_OUTPUT_TOKENS`
defaults to 32768 and `SCHEDULE_DRAFT_TIMEOUT` to 90 seconds per provider attempt.
Keep the backend's `RAG_SERVICE_TIMEOUT` long enough for a configured fallback.

The admin now saves clarification questions separately from driver guidance,
blocks new approval while relevant questions remain open, and remembers a
schedule draft's private return note and reference page. Existing databases need
the additive [admin workflow migration](supabase/migrations/admin_review_workflow.sql)
before running this version. New databases use the complete initial schema.

Document workspaces list schedules that reference the manual or its earlier
versions. Learning guides sharing those service tasks are listed as related
content; this is not automatic manual comparison or confirmation that the guides
cite the document. Saved questions do not automatically withdraw live content.

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

For YouTube ingestion, existing databases first need the additive
[channel migration](supabase/migrations/youtube_channels.sql). Adding a channel
in admin sends a sync request directly to the private RAG API, which prepares all
videos available from its uploads playlist in the background. Ingestion runs only
when an admin adds a channel or clicks **Sync videos** or **Retry sync**; there is
no periodic channel polling or scheduled refresh. The document index worker handles
documents only. Run one RAG API process per shared index; channel sync requests are
serialized. The dashboard shows sync status, counts and errors. **Sync videos** checks
for new uploads; **Retry sync** reuses cached work. After a backend restart,
interrupted syncs are marked failed for an explicit admin retry. Transcript-unavailable videos
keep the existing title/description fallback. Assign the relevant indexed video
links to vehicles/topics in **Related videos** before chatbot recommendations.

Channels share the video collection and have separate caches under
`output/youtube/channels/<channel-id>`. An existing single-channel cache is reused
for its matching channel. Adding its URL in admin brings it into the new workflow.
`YOUTUBE_CHANNEL_URL` remains an optional CLI fallback. Manual ingestion is also
available with
`.\.venv\Scripts\python.exe -m rag.app.youtube.pipeline --channel-url https://www.youtube.com/@handle`.

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
budget. It is not a full-history or spending-analysis feature. Car guide can also
supply a bounded service-plan snapshot as personal evidence; the complete plan
is calculated separately and stored using the companion migration. Restart the
backend and private RAG service together after updating their contracts.

Emergency guides come from the admin's reviewed publications. The app syncs
published guides and shared contacts at startup and on resume, downloads guide
text and illustrations automatically, and keeps complete copies for offline use.
It downloads changed revisions and removes withdrawn publications after a
successful online sync, including when the published catalogue becomes empty.
A failed refresh preserves existing downloads; a failed illustration update
keeps the previous complete offline revision. Before the first successful sync,
no admin guidance or shared contacts are available offline. Calling 999 and
device-saved personal contacts remain available. No bundled guide catalogue is
loaded. Learning guides and owner manuals still require an online connection.

Accident forms are available from Emergency, independently of published guides.
The Accident forms screen separates New accident form, Saved drafts and Past
accident forms. New forms capture the current device time and attempt to capture
the current location after location permission is granted. Both fields remain
editable for accidents recorded later. Address lookup falls back to GPS
coordinates; manual location entry remains available when capture fails. Opening
an existing draft or saved form preserves its recorded time and location.

Drafts autosave locally and are selected explicitly. Starting another form keeps
earlier drafts. Save to past accidents stores a completed form in history before
removing its draft; saved forms can be reopened and edited. Earlier single-draft
files are retained and imported into the new draft list. Drafts and history are
separate for guests and each account. Photos stay on the device, and the existing
optional account backup covers completed form text only.

Nearby search uses Places API (New) on the backend; configure a server API key
with that API enabled and the appropriate billing and API restrictions.
Gemini uses its own `GEMINI_API_KEY`
and `GEMINI_MODEL`. Alternatively, set `GOOGLE_CLOUD_PROJECT` and
`GOOGLE_APPLICATION_CREDENTIALS` to a server-side service-account JSON path,
with `GOOGLE_CLOUD_LOCATION=global`. A Cloud project with no `GEMINI_API_KEY`
selects Google Cloud authentication automatically; set
`GOOGLE_GENAI_USE_ENTERPRISE=true` to select it explicitly when both are present.
The service account needs access to the configured model and the project's AI
API must be enabled. Restart the private RAG service after changing credentials.

## RAG configuration

Local visual reranking and bounded original-image inputs are enabled by default.
Set `RAG_RERANK=false` or `RAG_VISUAL_INPUTS=false` to disable them. Restart
the private RAG service after changing these settings. Source approval and
publication remain explicit admin actions.

## Android build

Start the first available Android emulator from the repository root:

```powershell
.\start-emulator.cmd
```

To choose a specific virtual device, pass its name, for example
`.\start-emulator.cmd Medium_Phone`. The launcher uses `ANDROID_HOME`,
`ANDROID_SDK_ROOT`, or the default Windows Android SDK location.

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
and device storage configuration, which supports downloaded offline guest content.

## Local archive

Nonproduction tests, evaluation tools, documentation, debug output
and previous Android builds have been moved into `dumpster/` with their original
relative paths. The folder is ignored by Git and is outside the application build
roots. Its `CLEANUP.md` and `manifest.json` describe the archive and restoration.
The original README is preserved there. Later cleanup passes use separate dated
folders, including `dumpster/cleanup-2026-10-29/`, with their own manifests and
configuration backups. Archived files are local only and are not included in
commits or fresh clones.
