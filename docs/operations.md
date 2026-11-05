# MyRoadie operations guide

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

`MINERU_API_URL` must point to Windows for the split-device deployment. Leaving it empty selects local MinerU execution, which requires MinerU on the backend machine. Leave `MINERU_EXECUTABLE` empty for automatic discovery: `.venv-ocr/Scripts/mineru.exe` on Windows or `.venv-ocr/bin/mineru` on macOS, then the current Python environment, then `PATH`. An explicit executable override is still supported. This setting is unused when remote OCR is selected.

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

Supabase handles user authentication. Keep email confirmation and TOTP MFA enabled. All accounts now require MFA before accessing protected application data. Configure the mobile redirect `myroadie://auth/callback` and the dashboard redirect `https://anqis-macbook-pro.tailcb3ca9.ts.net:8443/auth/callback` in Supabase, plus local callbacks when used.

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

## Archive or remove learning topics

In **Learning Topics**, select **Remove** to see the guides (including drafts),
document assignments, video links and saved history attached to a topic.
**Archive topic** hides it and its guides from drivers, disables it in the
chatbot, and preserves content, assignments and history. Select **Show archived
topics**, then **Restore**, to bring it back as a draft. Publish the topic and
enable its chatbot setting separately when ready.

For permanent deletion, choose **Review permanent deletion**. Move any guides
to another active topic; published guides require a published destination.
The move and deletion happen in one transaction. Original documents and stored
files remain; only their topic assignments and video links are removed.
Topics with saved chats or learning recaps must be archived instead. If the
topic changes while the dialog is open, refresh its removal details before
confirming. Existing databases require the
[category management upgrade](../supabase/migrations/20261103_category_removal.sql).

## Delete unused catalogue entries

In **Vehicle Catalogue**, each vehicle, model and manufacturer has a **Delete**
action. Vehicles also offer it in their detail workspace. The dialog checks usage
and lists blockers with counts and links to available records. Models require
their vehicle variants to be removed first; manufacturers require their models
to be removed first. Inactive children still count as references.

An unused entry can be **Permanently deleted** after reviewing the dialog. Entries
with documents, schedules of any status, video assignments, user vehicles,
clarification questions, chats, saved document-test questions or test history
must retain their identity. Use **Deactivate** in the dialog to hide an entry
from new selections while preserving those references. No linked documents or
personal records are deleted or detached by this operation.

Deletion rechecks usage inside a database transaction and requires the preview's
fingerprint. If an entry or its references change, refresh the preview before
confirming again. Database triggers enforce the same rules for direct deletion,
and scope guards prevent new document tests from referencing a deleted vehicle.
Existing installations must first apply
[`20261103_catalogue_deletion.sql`](../supabase/migrations/20261103_catalogue_deletion.sql).

## Upload a document bundle and share its coverage

In **Reference Library → Add document**, select the files for the bundle. Tags
and document type apply to all selected files; a multi-file upload keeps each
filename as its title. **Upload and continue** shows progress and then opens
coverage in the same popup. Choose the vehicles, learning topics and optional
general-guidance flag once, then **Apply coverage** to all uploaded documents.
Year, engine and version qualifiers entered here also apply to the whole bundle.
Use this only for documents that share that coverage; each document can still be
adjusted in its workspace.

**Finish later** keeps the uploaded files for later setup. Partial upload failures
keep successful document IDs and leave only failed files selected for retry.
Coverage can also be applied to the successful subset before returning to the
remaining files. A failed coverage assignment can be retried without uploading
again; assignments already confirmed for the current selection are skipped.
Coverage does not publish documents or start preparation automatically.

## Manage document tags

Open **Reference Library → Manage tags** to see labels and document counts.
Select a tag to rename it across the library or merge it into an existing label.
**Remove tag from documents** removes that label from all documents using it;
other labels and coverage are preserved. Create new tags during upload or under
an individual document's **Edit details → Search Labels** section.

Tags are stored on documents, so unused tags disappear from the choices. Case and
extra whitespace are ignored for matching and duplicates within a document are
collapsed. Changes are reported per document; processing or busy documents can
be retried after their current operation finishes. Neither shared upload coverage
nor tag management requires a database migration.

## Duplicate document uploads

Uploads and replacements reject byte-identical sources with HTTP 409 and name
the existing document. Renaming a file or changing its library title does not
bypass the check. Assign additional vehicles or topics to the existing document
instead of uploading another copy. Website PDF capture and recovery use the same
check. Different source bytes are allowed, including revised editions with the
same filename; this check does not detect visually similar or re-exported PDFs.

The backend checks stored sources of the same size using SHA-256 and caches only
their digests, keyed by storage path and source revision. This also covers sources
uploaded before this feature, without a database migration or removal of existing
duplicates. Storage must be available to verify uncached sources. Source writes
are serialized per digest within the supported single backend process; multiple
backend processes would require a database uniqueness constraint or shared lock.

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

### Original pages for table answers

Chat retrieves tables through their extracted cells and supplies the original PDF
pages to the answer model. PDF table claims require citations to supplied full-page
images; OCR cells or cropped details alone cannot establish those claims. Missing
pages or unresolved symbols produce a limitation. Web and mobile replies show the
supporting pages with page numbers and enlargement controls, except when the user
explicitly requests text only.

Tables have a separate image budget: `RAG_TABLE_PAGE_LIMIT` defaults to 12 (allowed
range 1–24), with up to three supplemental table crops and three illustration
inputs. Related tables in the same contiguous extracted section supply additional
page context; they are not automatically declared continuations. The answer model
must check printed headings, legends and notes. Context packing can still omit
evidence, and the final packed coverage is reported to the model. Setting
`RAG_VISUAL_INPUTS=false` also prevents PDF table claims from using OCR alone.

Existing extractions containing packaged page assets work without rerunning OCR.
Older sources missing page assets need preparation again. Restart the backend and
RAG service after updating the code, rebuild/restart the dashboard, and rebuild the
mobile app to use its new page gallery.

### Correct several entries before indexing

In the document workspace, use **Save correction as draft** for each text or
table edit. Saved corrections have status `awaiting_confirmation` and remain
available for review and further edits after a reload or restart. The index
worker skips these drafts, including during `--restore-processed` recovery.
When all edits are saved, select **Confirm changes and rebuild index** below
the document review. This releases the latest saved revision for one rebuild.
Final source approval and publication remain blocked until indexing succeeds.
Illustration identity reviews follow the same flow. Check images and use
**Mark checked and next** to continue without saving or refreshing the document.
**Save all illustration reviews as draft** submits the whole review batch once,
preserving prepared text and tables without rerunning OCR. Then use **Confirm
changes and rebuild index** when all corrections and illustration reviews are
ready. Unsaved illustration edits must be saved or discarded before confirming
or making another text correction.
An older indexing pass already in progress may finish, but cannot confirm a
superseded revision. New installations include the draft status; existing
databases need the [status constraint upgrade](../supabase/migrations/20261103_deferred_correction_indexing.sql).

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

## Website references

Website importing has been removed. To add a webpage as a reference, use your
browser's **Print → Save as PDF**, then upload the file through
**Reference Library → Add document**. Assign coverage, process, review and publish
it through the normal document workflow.

Existing imported documents and their source attribution remain available.
The launcher no longer starts a website capture worker, and website import API
routes have been removed. Restart the app after updating to stop an existing
worker and load the updated dashboard and API. Historical import records and
local capture files are retained; no database migration is required.
