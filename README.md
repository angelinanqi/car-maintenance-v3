# Roadie - Car Maintenance and Assistance

Flutter Android app, Next.js production admin, FastAPI backend, hosted Supabase,
and a private RAG API using Gemini, hybrid Chroma/BM25S retrieval and reranking.

## Repository and deployment

| Location | Responsibility |
| --- | --- |
| `mobile/` | Flutter Android application; package remains `car_app`. |
| `web/` | Next.js admin and same-origin backend proxy. |
| `backend/` | FastAPI, access control, uploads, extraction and review. |
| `rag/` | Private API, document indexing, retrieval and generation. |
| `shared/` | Shared contracts and extraction/provenance helpers. |
| `supabase/` | Single fresh-install script `supabase/init.sql`; see `supabase/README.md`. |
| `scripts/` | Shared launcher, PDF renderer and trusted admin utilities. |
| `output/` | Ignored persistent runtime files and rotating service logs. |
| `dumpster/` | Ignored local archive, absent from fresh clones. |
| `NEED-FOR-EVAL/tests/` | Focused regression tests, separated from production code. |

**Viva:** MacBook M3 8 GB runs backend, production web and one RAG process with
embedded Chroma and a document-indexing thread. Windows runs only MinerU 3.4.5.
Android runs the installed release APK. All three join the same Tailscale tailnet.
Supabase and Gemini remain remote. No emulator, Docker, subnet router or exit node
is required. Do not run a second backend against the same Supabase project during
cutover: interrupted-processing recovery and document locks are not distributed.

## One-time Windows OCR setup

From the repository root in PowerShell, reuse the existing environment if installed:

```powershell
py -3.12 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt
.\.venv-ocr\Scripts\python.exe -m pip check
.\start-ocr.cmd
Invoke-RestMethod http://127.0.0.1:8010/health
```

The launcher requires MinerU **3.4.5**, defaults to loopback port 8010, one
concurrent request, no VLM preload, and output under `output/mineru-api`.
`MINERU_API_HOST`, `MINERU_API_PORT`, `MINERU_API_OUTPUT_ROOT` and
`MINERU_API_MAX_CONCURRENT_REQUESTS` override these defaults. Models load on the
first actual PDF; download and warm them before the viva. Verify a representative
manual, including tables and images, rather than relying only on `/health`.
Windows does not need Node, Flutter, Supabase service-role credentials or Gemini
credentials to run OCR. The root `.env` is optional for the OCR launcher.

## One-time Mac setup

Use a native arm64 terminal and a fresh native Python environment, not a copied
Windows environment or Rosetta packages. Python 3.14 is the existing application
baseline; installed binary wheels on the actual Mac must be checked. MinerU stays
on Windows/Python 3.12. Install Python and Node.js 22 with your normal package manager:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
npm --prefix web ci
```

No Flutter SDK, Android SDK or MinerU installation is needed on the Mac. The backend
now renders original PDF pages with its own Python/PDFium. Configure a private root
`.env` using the existing Supabase and Gemini settings. Keep server secrets and
service-account JSON out of Git; set `GOOGLE_APPLICATION_CREDENTIALS` to a real Mac
path if using Cloud authentication. Do not copy a Windows executable/credential path.

Recommended Mac settings in `app.config.json` (replace the hostname, not with a temporary LAN IP):

```json
{
  "BACKEND_HOST": "127.0.0.1",
  "BACKEND_PORT": "8000",
  "FRONTEND_HOST": "127.0.0.1",
  "FRONTEND_PORT": "3000",
  "BACKEND_API_URL": "http://127.0.0.1:8000",
  "RAG_HTTP_HOST": "127.0.0.1",
  "RAG_HTTP_PORT": "8001",
  "RAG_SERVICE_URL": "http://127.0.0.1:8001",
  "RAG_BACKEND_URL": "http://127.0.0.1:8000",
  "RAG_INDEX_WORKER_MODE": "embedded",
  "RAG_INDEX_POLL_SECONDS": "30",
  "MINERU_API_URL": "https://WINDOWS_FULL_MAGICDNS_NAME",
  "MINERU_BACKEND": "pipeline",
  "MINERU_TIMEOUT": "7200",
  "OUTPUT_DIR": "output/viva-mac",
  "CHROMA_PATH": "output/viva-mac/embeddings/chroma",
  "RAG_INDEX_WORK_DIR": "output/viva-mac/index-worker",
  "DOCUMENT_WORK_DIR": "output/viva-mac/documents",
  "YOUTUBE_OUTPUT_DIR": "output/viva-mac/youtube",
  "MODEL_DEVICE": "cpu",
  "EMBEDDING_BATCH_SIZE": "1",
  "EMBEDDING_CPU_THREADS": "2",
  "OMP_NUM_THREADS": "2",
  "TOKENIZERS_PARALLELISM": "false"
}
```

Use **new empty** `output/viva-mac` paths. Do not copy old Chroma, BM25, embeddings,
source manifests, worker ledger or YouTube cache into them. BM25S lexical indexes
are built/cached in memory from current records; there is no separate BM25 server.
Keep all RAG output/asset paths consistent. Models use the normal Hugging Face
user cache; an optional `HF_HOME` should be an absolute ignored/external directory.
Do not commit downloaded models or runtime data. The launcher logs remain at
`output/logs` regardless of `OUTPUT_DIR`.

The unchanged model is `nomic-ai/nomic-embed-text-v1.5`, 768 dimensions, 8192-token
limit; the reranker remains `cross-encoder/ms-marco-MiniLM-L6-v2`. CPU is a
conservative starting choice, not a measured claim that CPU beats MPS. `MODEL_DEVICE=mps`
is available for a controlled Mac benchmark; an unsupported device fails rather
than silently selecting another model. Batch size 1 reduces peak inference memory
at the expense of ingestion throughput. Keep indexing/YouTube sync separate from
live chat demonstrations. Swapping is still possible with long chunks, browser
tabs and model caches on an 8 GB machine; physical Mac measurements are required.

Configuration is loaded from repository-relative paths, independent of the working
directory used for supported launch commands:

- `app.config.json`: all non-secret application settings, including machine addresses,
  paths, model settings, public Supabase configuration, and operational limits.
- `.env`: private credentials and `GOOGLE_APPLICATION_CREDENTIALS`, which locates
  credential material. This file remains Git-ignored.

These are the only configuration files needed. Both are included when transferring
the whole project as a zip; no templates or local override files are required.
Preserve the existing values. A zip preserves configuration, but Windows executable
and credential paths do not become valid Mac paths automatically. Use the Mac setup
above for native dependencies and adjust only machine-specific paths/addresses when
needed; Windows continues to run OCR separately.

Settings retain their existing names and JSON string values. Explicit process
environment values take precedence, followed by dotenv values, then JSON settings;
existing code defaults apply to omitted settings. Do not put secrets in JSON or
pass the root config to Flutter as a build asset. Invalid/missing JSON fails early
with a filename-only error. OCR can run without `.env`; the app launcher requires it.

The settings below retain their existing meaning:

| Setting | Purpose |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Public URL in `app.config.json`; service-role key stays server-only in `.env`. |
| `SUPABASE_PUBLISHABLE_KEY` | Public client Auth key in `app.config.json`; safe in browser/APK configuration. |
| `RAG_SERVICE_TOKEN` | Server-to-server secret of at least 32 bytes; preserve the existing value. |
| `GEMINI_MODEL`, `GEMINI_API_KEY` | Model in `app.config.json`; server API key in `.env`. |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS` | Cloud project/location in `app.config.json`; credential-file path stays in `.env`. |
| `CORS_ORIGINS` | `app.config.json`: explicit admin origins, including `https://MAC_FULL_MAGICDNS_NAME:8443` when used. |
| `YOUTUBE_API_KEY`, `GOOGLE_PLACES_API_KEY` | Optional existing video/nearby integrations. |

Keep the admin's existing `/api/backend` proxy. Do not set a remote public
`NEXT_PUBLIC_API_URL` to bypass it. After configuring, build once:

```bash
npm --prefix web run build
```

Initialise a fresh Supabase database manually with [supabase/init.sql](supabase/init.sql),
following [supabase/README.md](supabase/README.md). Do not
rerun fresh-schema SQL or reset existing records. Supabase Auth remains unchanged;
keep email confirmation and admin TOTP requirements. Allow `myroadie://auth/callback`
and each admin origin's `/auth/callback` in the Supabase redirect settings when
setting up that origin.

User authentication uses Supabase Auth exclusively in both clients. The backend
accepts Supabase bearer tokens, verifies the provider identity, and enforces
application roles, MFA and ownership. Custom admin login and local session cookies
are retired. Existing administrators must have a confirmed Supabase identity linked
to their original application profile before signing in. The trusted linking helper
preserves the profile ID and historical attribution; it does not run automatically:

```powershell
.venv\Scripts\python.exe -m scripts.link_supabase_admin AUTH_USER_UUID
```

To create a new administrator, register through the interface, confirm the email
and sign in once to create the application profile. In Supabase's Table Editor,
open `public.app_users`, find the account by email and change `role` from `user`
to `admin`. Refresh the admin page and complete MFA setup. Repeat for additional
administrators; existing admins retain their roles.
The unused legacy authentication settings (`JWT_SECRET`, `JWT_ISSUER`,
`JWT_AUDIENCE`, `SESSION_TTL_SECONDS`, and `SESSION_COOKIE_SECURE`) have been
removed from `.env`. Supabase Auth configuration
and active service credentials are retained unchanged. The unused `CHUNK_OVERLAP` entry has also been removed.

## Private Tailscale HTTPS preparation

**These are proposed one-time commands, not changes already applied. Obtain the
separate approval required for live Serve, DNS, grants or security configuration.**
Install Tailscale on Mac, Windows and Android and join the same tailnet directly.
Enable MagicDNS/HTTPS as appropriate for that tailnet. Use full device FQDNs from
`tailscale status --json`, not guessed names. The current Windows device already
has a Serve target for port 8000; inspect `tailscale serve status` before replacing
it. A Mac device/hostname has not yet been verified in this environment.

Proposed private HTTPS targets after approval:

```powershell
# Windows: replace the previous HTTPS 443 backend target only at cutover.
tailscale serve --bg --https=443 http://127.0.0.1:8010
tailscale serve status
```

```bash
# Mac: backend at HTTPS 443; admin at HTTPS 8443.
tailscale serve --bg --https=443 http://127.0.0.1:8000
tailscale serve --bg --https=8443 http://127.0.0.1:3000
tailscale serve status
curl -f https://WINDOWS_FULL_MAGICDNS_NAME/health
```

Serve is tailnet-private; do not use Funnel. Restrict Windows OCR access to the Mac
using tailnet grants/ACLs after separate approval. The native OCR API has no
application token: private reachability and tailnet access rules are its access
boundary. RAG port 8001 stays loopback, with existing bearer authentication; it has
no Serve target. Android uses `https://MAC_FULL_MAGICDNS_NAME` without port 8000.
Admin browsers use `https://MAC_FULL_MAGICDNS_NAME:8443/login`. Run `tailscale ping`
between laptops; a relayed connection may make large PDF/ZIP transfers slower.
Do not disable TLS certificate validation or expose application ports publicly.

## Fresh local indexing without resetting Supabase

Existing `processed` records still have their publication and indexed-revision
metadata, even on a Mac with an empty Chroma directory. Normal Process skips those
records; force reprocessing also requires unpublishing. Do not reset them with SQL.

The explicit restore command reads the **current stored extraction ZIP**, including
saved corrections and original image/page provenance, rebuilds only local artifacts,
and leaves processed Supabase records unchanged. It checks the rebuilt chunk count
against the authoritative record. Superseded sources are excluded. Older extraction
formats or changed chunk counts require deliberate admin review/reprocessing.

For initial restoration, run the backend alone and restore before starting the full
stack; this avoids a second model process or index worker at the same time:

```bash
# Terminal 1; root .env already configured, Windows backend stopped.
.venv/bin/python -m backend
# Terminal 2; do not run the app launcher simultaneously.
.venv/bin/python scripts/run.py index --once --restore-processed
```

The command also handles pending `awaiting_index` work using the existing revision-
checked acknowledgement. Failed local restores do not change processed records.
Inspect the worker log and command exit code. Stop Terminal 1 with Ctrl+C, then
start the full stack below. Treat each published revision as ready for the viva
only after testing it in a scoped query. No Supabase data, storage objects, accounts or
publication records are reset automatically. Missing original extractions must be
reprocessed through the existing admin workflow; reviewed corrections must be kept.

For intentionally fresh OCR, upload/process a new document, or unpublish an existing
one and explicitly reprocess it through the admin workflow. Existing correction
bundles are intentionally reused. Reviewed documents move through `awaiting_index`
to `processed` only after indexing succeeds; use normal review/publication controls.
YouTube channel records likewise remain in Supabase: explicitly Retry/Sync each
channel against the empty local collection before using video retrieval.

## Indexing and model lifecycle

The normal launcher starts three application processes: backend, RAG, production
Next.js. A lightweight indexing thread in RAG polls every 30 seconds with the above
settings. It initializes no model/Chroma on an empty idle installation, and shares
one locked cached embedding model with chat, guide embeddings and YouTube ingestion.
Document embedding releases the inference lock between configured batches so a
whole manual does not hold it for a single uninterrupted model call. Batch
progress bars are suppressed; document completion/failure logs remain available.
Indexing clients explicitly release their Chroma handles after each document/pass.
No extra model-serving process is introduced. Idle indexing retains no separate
model. The RAG query model remains cached for reasonable response latency.
A file lock prevents embedded/standalone workers using the same worker directory
from overlapping. Different directories pointing at the same Chroma are unsupported.

`RAG_INDEX_WORKER_MODE=external` retains the standalone worker arrangement when
needed; the app launcher starts it in that mode. Direct `python -m rag.service`
defaults to external mode for compatibility. Do not start a separate worker alongside
embedded mode. Embedded-worker initialization failures stop RAG startup; per-document
failures are logged/acknowledged and retried on the next pass. At shutdown, the
worker stops polling and waits for its current pass. Finish active OCR/indexing
before stopping the stack; the launcher allows 120 seconds per child before forcing
shutdown, leaving recoverable checkpoints for interrupted work.

## Windows release APK

Build on Windows with the existing Flutter/Android tooling and existing signing key.
Use actual public configuration values; no server keys belong in Dart defines.
The existing release defines remain supported unchanged. `start-mobile.cmd` reads
the JSON configuration and forwards only the public Supabase URL/key; continue to
supply `API_BASE_URL` explicitly for the target host:

```powershell
Push-Location mobile
flutter pub get
flutter analyze
flutter build apk --release `
  "--dart-define=API_BASE_URL=https://MAC_FULL_MAGICDNS_NAME" `
  "--dart-define=SUPABASE_URL=https://YOUR_PROJECT.supabase.co" `
  "--dart-define=SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_SUPABASE_KEY"
Pop-Location
```

Output: `mobile/build/app/outputs/flutter-apk/app-release.apk`. The Mac hostname is
not yet known, so an APK built without the real defines is only a build check,
not a deployable viva configuration. Internet permission, HTTPS-only release account
access, API compile-time configuration, package ID `com.example.car_app` and signing
configuration are retained. Release currently uses the local debug signing key.
Use the same certificate as the APK already installed on the phone so installation
can update it without clearing app data. Do not uninstall to resolve a certificate
mismatch; locate the matching existing key first. Install the APK before the viva
by trusted transfer/on-phone installation or `adb install -r` while connected.
Normal demonstration needs neither USB nor Flutter tools: enable Tailscale and open
the installed app. Existing Supabase authentication/data behaviour is unchanged.

## Viva quick-start and shutdown

After the one-time configuration, restoration, model warmup and APK installation:

1. Windows: connect Tailscale, run `.\start-ocr.cmd` from the repository root.
2. Mac: connect Tailscale, run `./start-app.command --no-browser`.
3. Check Mac `curl -f http://127.0.0.1:8000/health` and
   `curl -f http://127.0.0.1:8001/openapi.json`; check Windows OCR HTTPS health from Mac.
4. Open `https://MAC_FULL_MAGICDNS_NAME:8443/login`; sign in and test a scoped
   chatbot question with a citation. Port readiness does not prove model/cloud access.
5. Phone: enable Tailscale, open APK, sign in and verify the same backend knowledge.

Keep both launcher terminals open. Complete document processing and indexing before
shutdown. Press Ctrl+C on the Mac launcher, wait for its child processes to exit,
then Ctrl+C on Windows OCR. Persistent Serve configuration remains configured;
services become unavailable while stopped. Caches/checkpoints remain on disk.

On the Mac, enable the launcher once with `chmod +x start-app.command`. Then
double-click it in Finder to start the stack and open the admin login, or run
`./start-app.command` in Terminal. It resolves the repository from its own location,
uses `.venv/bin/python` and forwards options such as `--no-browser` and
`--without-rag` to the existing launcher. Build the production dashboard and
configure `.env` using the setup above before launching. Stop with Ctrl+C.

Retained commands and supporting entry points:

| Command/script | Purpose |
| --- | --- |
| `start-ocr.cmd` / `scripts/run.py ocr` | Windows native MinerU API only. |
| `start-app.command` / `scripts/run.py app` / `start-app.cmd` | Managed production stack; `.command` is for Mac, `.cmd` for Windows. |
| `scripts/run.py index [--once] [--restore-processed]` | Explicit local indexing/restoration with logs. |
| `scripts/run.py youtube ...` | Existing manual YouTube ingestion; avoid simultaneous heavy jobs. |
| `start-mobile.cmd` / `scripts/run.py mobile ...` | Development-only Flutter run; public Supabase defines injected. |
| `backend/__main__.py`, `rag/service.py`, `rag/index_worker.py` | Direct component entry points. |
| `web/scripts/next.mjs`, npm `build`/`start` | Existing production web launcher/build wrapper. |
| `scripts/render_pdf_pages.py` | Shared PDF page renderer, not an independent service. |
| `mobile/android/gradlew`, `gradlew.bat` | Required Android build wrappers. |
| `mobile/scripts/generate_launcher_icons.ps1` | Asset maintenance, not a runtime service. |

Emulator and sample-UI preview launchers are unnecessary for this viva; archived
copies under `dumpster/start-app-cmd/` retain their original names. Shared application
and build scripts remain active. No other dumpster contents are modified.

## Verification, performance and troubleshooting

Implementation validation on Windows (2026-11-02): the focused deployment suite,
five existing OCR tests and twelve document-recovery tests passed. A native MinerU
3.4.5 instance on isolated port 18010 processed a generated one-page PDF and returned
Markdown, both content-list formats, middle/model JSON and the original PDF in
70.72 seconds. This blank-page smoke test does not validate real table/crop quality.
The backend rendered its original page independently with PDFium 5.14.0, and the
OCR launcher exited cleanly. An offline CPU model/reranker/temporary-Chroma smoke
test passed in 45.51 seconds including model loading, with 768-dimensional output
and confirmed shared model identity. These timings are Windows measurements under
concurrent local workloads, not comparative benchmarks or Mac memory estimates.
A separate real Markdown-to-Chroma indexing/query smoke test passed in 21.51 seconds,
with maintenance suggestion generation mocked to avoid unrelated cloud calls.

The isolated Next.js production build, Flutter analysis and a 66.2 MB release APK
build passed. That APK lacks the final Mac/public Supabase deployment defines and
must be rebuilt before installation. Backend `/health` returned 200 with startup
database recovery mocked; backend/RAG OpenAPI contracts matched the saved baseline
exactly (143 backend operations, 6 RAG operations). `pip check` reported no broken
installed-package requirements; this does not validate every root constraint or
Mac wheel availability.

Of 57 additional archived document/visual/YouTube tests, 52 passed and five older
source-page reference tests failed: their assertions expect singular image fields
that the unchanged query implementation replaced with plural references. The query
and source-page helpers match the pre-implementation source hashes. These archived
failures were not hidden or changed as part of deployment work. The full physical
Supabase/Gemini/admin/phone workflow, representative PDF assets and Mac CPU/MPS
memory/latency remain unverified here.

Run focused offline checks with `.venv/bin/python -m unittest discover -s NEED-FOR-EVAL/tests -v`
(or `.venv\Scripts\python.exe` on Windows). They cover remote result preservation,
unsafe archives, interrupted/ambiguous requests, shared model reuse and local restore
without database writes. Mocks are not proof of cross-device operation.

On the actual Mac, record cold and warm timings, RSS and system memory pressure:

```bash
.venv/bin/python -c "import platform, torch; print(platform.machine(), torch.__version__, torch.backends.mps.is_available())"
/usr/bin/time -l .venv/bin/python -c "from rag.app.embedding.embedder import embed_query; from rag.app.retrieval.hybrid import reranker; from time import perf_counter; t=perf_counter(); print(len(embed_query('engine oil maintenance'))); r=reranker(); print('cold seconds',perf_counter()-t); t=perf_counter(); print(len(embed_query('tyre pressure'))); print(r.predict([('tyre pressure','Check cold tyre pressure.')])); print('warm seconds',perf_counter()-t)"
ps -axo pid,rss,%cpu,command | sort -nk2 | tail -15
vm_stat
sysctl vm.swapusage
```

Repeat the isolated model command with `MODEL_DEVICE=mps` as a shell environment
override to compare CPU/MPS; do not run it alongside the stack on an 8 GB machine.
Use Activity Monitor memory pressure while running the real stack, a representative
PDF ingestion and phone/admin queries. Record end-to-end chat latency and citation
correctness separately from encoder time. No Mac memory/latency figures are inferred
from Windows results. First model downloads, long token sequences, sequential model
access, Gemini/Supabase calls and OCR over relayed Tailscale remain bottlenecks.

Before the viva validate on the physical devices:

- Backend health, RAG actual inference, Supabase sign-in and Gemini access.
- Mac-to-Windows HTTPS health and actual PDF upload/result ZIP transfer.
- Tables, content-list/middle/model JSON, page indices/bounding boxes and original-page citations.
- Admin extraction review/corrections, indexing acknowledgement and publication.
- Fresh/restored Chroma retrieval, hybrid ranking, reranker, chatbot citations and assets.
- Android HTTPS connectivity, persisted authentication and chatbot images/tables.
- Existing admin content operations and mobile vehicles, maintenance and learning flows.
- Ctrl+C shutdown, restart recovery, duplicate-launch rejection and no remaining child ports.

Logs: `output/logs/{backend,rag,web,ocr,index-worker,app-launcher,ocr-launcher}.log`.
Embedded worker messages are in `rag.log`, not a separate worker file. Files rotate
at 5 MiB with three backups. For example, `Get-Content output/logs/ocr.log -Tail 80 -Wait`.

If indexing remains `awaiting_index`, inspect RAG logs, bearer token, backend URL,
worker lock and extraction compatibility. Retry after fixing the cause; do not reset
records. If an acknowledged OCR job is interrupted, retry processing to resume its
saved task. An unknown submission, failed/expired native task or Windows API restart
requires checking Windows task/log state before **archiving** the document's
`*.mineru-job.json` checkpoint and deliberately retrying. Never blindly resubmit an
unknown upload. Invalid/missing outputs cannot replace a completed extraction cache.
Do not remove live persistent runtime files just because Git ignores them.

## Website article references

In the admin Reference Library, choose **Add website article** and submit a public
HTTP/HTTPS article URL. The backend uses Trafilatura to extract HTML directly on
the Mac; Windows OCR is not involved. Choose vehicle/topic coverage, prepare the
source, review its text/tables/illustrations, then approve and publish through the
existing document workflow.

The private document bucket stores a self-contained Markdown snapshot with a JSON
metadata comment and bounded, base64-encoded image assets. Metadata includes the
submitted/final URL, title, retrieval time, source identifier and content hash.
Processing unpacks the assets into the existing extraction archive and keeps
metadata out of embeddings. Identical URL/content snapshots are rejected; changed
content creates a new document and never refreshes or overwrites the old source.
Publication and vehicle/topic coverage remain independently controlled for each
snapshot. Review the older snapshot's publication if importing an update.

Website citations retain title, original URL, section and retrieval time without
invented PDF pages. Review shows any missing illustrations or embedded media.
The importer checks robots rules, public DNS/IPs and every redirect, pins the TCP
connection to a checked address while retaining TLS hostname verification, and
limits downloads and timeouts. No JavaScript or linked-page crawling runs.

Login/paywall pages, JavaScript-only articles, files, inaccessible/blocked robots
rules, missing tables and unsupported embedded diagrams are rejected. Ordinary
raster images are saved where possible; SVG/canvas diagrams, video and interactive
media are not captured. Extraction cannot prove completeness: compare the review
with the original before publication. MinerU accepts PDFs but does not render web
pages, so automatic PDF fallback is intentionally absent. An authorised PDF can
still use the existing upload path.

Focused checks: `.venv/bin/python -m unittest discover -s NEED-FOR-EVAL/tests -p test_website_articles.py -v`
(use `.venv\Scripts\python.exe` on Windows). The isolated Chroma/BM25 test uses stub
embeddings; it does not verify live Supabase publication, model relevance or Gemini.
