# MyRoadie

MyRoadie helps drivers keep service records, learn about maintenance, and ask questions using their vehicle's manuals.

| Part | Guide |
| --- | --- |
| Android app | [Mobile README](mobile/README.md) |
| Admin dashboard | [Web README](web/README.md) |
| Document processing and AI search | [AI pipeline README](rag/README.md) |
| Required fine-tuned model | [Fine-tuning README](fine-tuning/README.md) |

## Everyday use

1. Connect Tailscale on the Mac, Windows PC, and Android phone.
2. On Windows, run `start-ocr.cmd` and wait for **OCR ready**. OCR is needed when processing PDFs.
3. On the Mac, run `./start-app.command` from the project folder.
4. Open the [local dashboard](http://127.0.0.1:3000/login) or the installed Android app.

The Mac runs the backend, dashboard, AI search, and model server. Windows extracts PDFs. Supabase stores accounts, shared content, and personal records.

Keep the launcher terminal open. Press **Ctrl+C** and wait for shutdown before restarting. Run one main app launcher at a time.

## First-time Mac setup

Install Python **3.14**, Node.js **22**, Ollama, and Tailscale. Put their commands on `PATH`. Install FFmpeg too if you will upload emergency videos; the backend uses `ffprobe` to check them.

Run from the project root:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
npm --prefix web ci
npm --prefix web run build
chmod +x start-app.command
```

Create a native environment on each machine; do not copy `.venv` between Windows and macOS.

### Settings and credentials

Edit [app.config.json](app.config.json) for addresses and public settings:

| Setting | What to use |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Your Supabase project's URL and publishable key |
| `API_BASE_URL` | The Mac backend's Tailscale HTTPS address, used by Android |
| `BACKEND_API_URL` | `http://127.0.0.1:8000`, used by the dashboard server |
| `MINERU_API_URL` | The Windows OCR machine's Tailscale HTTPS address |
| `OLLAMA_MODEL` | `roadie-gemma3-ft` — required |

Keep JSON values as strings. Put private credentials in a root `.env` file:

```dotenv
SUPABASE_SERVICE_ROLE_KEY=your_server_only_key
RAG_SERVICE_TOKEN=your_random_private_token
```

Generate the token with `.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'` and paste it into `.env`.

Optional features use `GOOGLE_PLACES_API_KEY` for nearby workshops, `YOUTUBE_API_KEY` for video discovery, and `GEMINI_API_KEY` for ingestion-time image descriptions. Gemini can instead use Google Cloud credentials through `GOOGLE_APPLICATION_CREDENTIALS` and the project settings in JSON. Interactive answers use the local fine-tuned model.

Explicit environment variables override the JSON and `.env`. Rebuild the web or mobile app after changing its public configuration.

### Supabase

For a **new database**, run the complete [supabase/init.sql](supabase/init.sql) once in Supabase's SQL Editor. It needs PostgreSQL 15 or later. It creates the application schema and the private `documents` and public `content-images` buckets.

For an existing installation, use only the missing upgrades in [supabase/migrations](supabase/migrations). Do not run `init.sql` over existing application data.

Enable email confirmation, Secure email change, TOTP MFA, and Require current password when changing password in Supabase Auth. Add these Auth redirect URLs, using your Mac's hostname:

- `http://127.0.0.1:3000/auth/callback`
- `http://localhost:3000/auth/callback`
- `https://YOUR-MAC-HOSTNAME:8443/auth/callback`
- `myroadie://auth/callback`

Once the app is running, register, confirm your email, sign in, and complete authenticator setup. To make your account an administrator, find it in `public.app_users` using Supabase's Table Editor and change `role` to `admin`. Sign in again or refresh the dashboard. A fresh database contains no accounts, vehicles, manuals, or learning content.

### Tailscale and model

With Tailscale connected, configure the Mac forwarding once:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8000
tailscale serve --bg --https=8443 http://127.0.0.1:3000
```

Enable HTTPS and MagicDNS for your Tailscale network. The backend uses port **443**; the remote dashboard uses **8443**. Keep the private RAG service on loopback port **8001**.

Set up [Windows OCR](rag/README.md#windows-ocr-setup) and [import the fine-tuned model](fine-tuning/README.md#import-on-a-new-mac), then start the app normally. On a fresh Mac with existing Supabase documents, also [restore local search](rag/README.md#restore-search-on-a-new-mac).

## Live logs

Start the apps normally, then open another Mac terminal in the project folder:

```bash
./scripts/logs.sh
```

This follows backend events, web proxy requests, document/OCR progress, and available mobile debug output. It shows the most recent 30 matching entries first. **Ctrl+C stops only the viewer.**

| Option | Shows |
| --- | --- |
| `--web` | Web requests and their completed operations |
| `--mobile` | Backend-observed mobile requests and available device traces |
| `--api` | Backend/internal requests and application events |
| `--ocr` | Document preparation and OCR stages, task status, and failures |
| `--http` | HTTP requests only |
| `--errors` | Warnings and failures, including HTTP 4xx/5xx |

Combine filters, for example `./scripts/logs.sh --web --errors`. Use `--lines 0` for new entries only, `--once` for a snapshot, or `--colour never` to disable colours. Normal HTTP traffic is neutral; warnings are yellow, failures red, completed processing green, and other events cyan.

HTTP entries include the status, duration, and request ID. `observed=API` means FastAPI received it; `PROXY` means Next.js handled it; `DEVICE` means it came from mobile debug output. Matching observations are deduplicated. Client failures can appear separately from a later backend response because those are different outcomes. Paths mask variable IDs and omit query values; bodies and credentials are not collected.

To see mobile failures that never reach the backend, or direct Supabase requests, connect the debug phone to the Mac through authorised ADB, or run Flutter through the Mac's mobile launcher. See [mobile logging](mobile/README.md#live-logs). The viewer retries unavailable device connections. Windows OCR's native terminal is still the place for engine-specific diagnostics; the Mac viewer shows the processing stages and remote task states observed by the backend.

`DEV_LOGGING` is enabled in JSON for this local setup. Set it to `"false"`, rebuild the dashboard, and restart before production use to disable web console/proxy diagnostics. Flutter logging is additionally restricted to debug builds. Existing private backend telemetry is controlled separately by `MONITOR_ENABLED` and `MONITOR_LOG_LEVEL`.

Logs stay under `output/logs/`, which Git ignores. Web logs rotate at 5 MiB with three backups. Backend telemetry has the same rotation and removes files older than seven days on service startup. Browser-only errors and direct browser authentication failures remain in browser DevTools; they are not sent to a logging endpoint. Source labels are informational and never grant access. Server timings end at response headers; central web/mobile API-client timings include reading the response. Supabase debug transport timings end at its response headers.

## Troubleshooting and backups

| Problem | Check |
| --- | --- |
| Dashboard will not open | Start the launcher; try `http://127.0.0.1:3000/login` on the Mac. |
| Phone cannot connect | Check Tailscale, `API_BASE_URL`, and the Mac's port-443 forwarding. |
| PDF processing fails | Start Windows OCR; check `output/logs/ocr.log` there and `backend.log` on the Mac. |
| AI will not start | Check `output/logs/rag.log` and `ollama.log`; confirm the fine-tuned model is imported. First model downloads can take time. |
| Port already in use | Stop the old launcher before starting another. |

Keep `.env`, `output/`, fine-tuning artifacts, and Android signing keys. `output/` contains live search indexes, extraction caches, and recovery checkpoints. Back up Supabase data and Storage separately. Normal service logs are in `output/logs/`.
