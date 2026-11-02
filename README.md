# Roadie

Car maintenance help, service reminders, and answers grounded in your vehicle's manuals.

Roadie has an Android app for drivers and a web dashboard for managing its content.

[Start the app](#start-the-app) · [First-time setup](#first-time-setup) · [Settings](#settings) · [Troubleshooting](#troubleshooting)

## Your setup

| Device | What it does |
| --- | --- |
| **MacBook** | Runs the main app, admin dashboard, and AI search. |
| **Windows PC** | Reads PDFs using MinerU OCR, which turns pages into text and images. |
| **Android phone** | Runs the Roadie app. |

Keep Tailscale connected on all three devices. Supabase stores accounts and shared data; Gemini supplies AI responses.

## Start the app

Once setup is complete, these are the steps for normal use. Run commands from the project folder.

### 1. Start OCR on Windows

Double-click **`start-ocr.cmd`**, or run this in PowerShell:

```powershell
.\start-ocr.cmd
```

Wait for **“OCR ready.”** The launcher also sets up the Windows Tailscale forwarding automatically.

### 2. Start Roadie on the Mac

Double-click **`start-app.command`**, or run this in Terminal:

```bash
./start-app.command
```

The launcher starts the main services and opens the dashboard. AI search can take a few minutes to start while models load.

### 3. Open the dashboard or phone app

| What you want to open | Where to go |
| --- | --- |
| **Admin dashboard through Tailscale** | [Open dashboard](https://anqis-macbook-pro.tailcb3ca9.ts.net:8443/login) |
| **Dashboard directly on the Mac** | [Open local dashboard](http://127.0.0.1:3000/login) |
| **Android app** | Open the installed Roadie app with Tailscale connected. |

The Tailscale dashboard link needs the Mac forwarding configured during first-time setup below.

**To stop:** finish any document processing, then press **Ctrl+C** in the Mac terminal and wait for shutdown. Do the same in the Windows OCR terminal. Keep both terminals open while using Roadie.

After a reboot, start the launchers again. Tailscale remembers its forwarding settings; it does not start Roadie or OCR for you.

## First-time setup

Already using the app? You can skip this section.

<details>
<summary><strong>Windows — set up PDF reading</strong></summary>

Install Python **3.12** and Tailscale. Connect Tailscale to the same network as the Mac and phone, and make sure the `tailscale` command is available in PowerShell. Tailscale HTTPS must be enabled for your network.

Create the OCR environment only if `.venv-ocr` does not already exist:

```powershell
py -3.12 -m venv .venv-ocr
```

Install the OCR dependencies:

```powershell
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

Then run `start-ocr.cmd`. It expects MinerU **3.4.5**, as specified in the requirements file. The first PDF may take longer while models download or warm up; try a representative manual before a demonstration.

Windows only needs to run OCR for this setup. Start the main app on the Mac.

</details>

<details>
<summary><strong>Mac — set up the main app and dashboard</strong></summary>

Install native Apple Silicon Python **3.14**, Node.js **22**, and Tailscale. Python package compatibility still needs to be checked on the actual Mac.

Create a new Mac environment; a Windows `.venv` will not work on macOS:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
npm --prefix web ci
```

Keep your existing credentials in `.env`. If using a Google service-account file, set `GOOGLE_APPLICATION_CREDENTIALS` to its actual **Mac path**.

Build the dashboard and enable its launcher:

```bash
npm --prefix web run build
chmod +x start-app.command
```

Connect Tailscale and run these commands once on the Mac to make the backend and dashboard available to your other devices:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8000
tailscale serve --bg --https=8443 http://127.0.0.1:3000
```

These settings persist across reboots. Unlike the Windows OCR mapping, the Mac mappings are configured manually.

If this is a fresh Mac installation with existing documents already in Supabase, follow [Restore document search](docs/operations.md#restore-document-search) before starting the full stack.

Run `./start-app.command` when ready. Run only one main backend against this Supabase project; stop any old Windows backend before switching to the Mac.

</details>

<details>
<summary><strong>Android — use or build the phone app</strong></summary>

If Roadie is already installed with the correct backend address, connect Tailscale and open it. You do not need USB or Flutter running for normal use.

To run a development build from Windows:

```powershell
.\start-mobile.cmd
```

The launcher reads the public API and Supabase settings from `app.config.json`.

To create an installable APK, see [Build the Android app](docs/operations.md#build-the-android-app). Direct Flutter build commands need the public settings passed explicitly.

</details>

## Settings

| File | What belongs there |
| --- | --- |
| [`app.config.json`](app.config.json) | Device addresses, ports, model choices, folders, and other non-secret settings. |
| `.env` | Private API keys, service tokens, and the Google credential-file path. Keep this file private. |

Old non-secret entries in `.env` are ignored. You generally only need to edit `app.config.json` when an address or setting changes. Explicit process environment overrides still take priority.

Your device addresses are already configured:

| Setting | Current address | Used for |
| --- | --- | --- |
| `MINERU_API_URL` | `https://iphone15promax.tailcb3ca9.ts.net` | Mac sending PDFs to Windows OCR. Despite its name, this Tailscale device is the Windows PC. |
| `API_BASE_URL` | `https://anqis-macbook-pro.tailcb3ca9.ts.net` | Android connecting to the Mac backend. |
| `BACKEND_API_URL` | `http://127.0.0.1:8000` | Dashboard connecting to the backend on the same Mac. |

<details>
<summary><strong>Ports and settings you may want to change</strong></summary>

| Setting | Port | Purpose |
| --- | --- | --- |
| `BACKEND_PORT` | `8000` | Main backend on the Mac. |
| `FRONTEND_PORT` | `3000` | Admin dashboard on the Mac. |
| `RAG_HTTP_PORT` | `8001` | Private AI search service on the Mac. |
| `MINERU_API_PORT` | `8010` | OCR service on Windows. |
| `MINERU_TAILSCALE_HTTPS_PORT` | `443` | Windows OCR access through Tailscale HTTPS. |

The Mac's Tailscale dashboard port is **8443**, configured by the Mac setup command above.

Keep JSON values in quotes, including numbers and booleans. When changing a port, update the matching URLs and any manual Tailscale forwarding too. The Windows launcher updates its OCR forwarding from the JSON automatically when `MINERU_TAILSCALE_SERVE` is `"true"`.

Rebuild the dashboard after changing public browser settings. Rebuild the Android app after changing its API or Supabase build settings.

For credential names and forwarding details, see [Configuration reference](docs/operations.md#configuration-reference).

</details>

## Manage content

Use the admin dashboard to add manuals, website articles, and supported reference content. Review extracted text, tables, and images before approving and publishing them.

For a website article, open **Reference Library → Add website article**, paste its URL, and follow the review steps. Articles are read directly on the Mac; they do not use Windows OCR. Pages requiring login, JavaScript, or payment may not work. Compare the extracted content with the original before publishing.

For database setup, administrator accounts, and recovery tasks, see the [operations guide](docs/operations.md).

## Troubleshooting

| What you see | What to check |
| --- | --- |
| Dashboard will not open | Start the Mac launcher. Try the local dashboard link on the Mac. If local access works, check Tailscale and the Mac forwarding settings. |
| Phone cannot connect | Keep Tailscale connected on both devices. Confirm the installed app was built with the current `API_BASE_URL`. |
| PDF processing fails | Start Windows OCR, wait for “OCR ready,” then check `output/logs/ocr.log`. |
| AI search is slow to start | Give model loading time to finish. Check `output/logs/rag.log` for progress or errors. |
| A port is already in use | Stop the previous launcher or service using that port before starting another copy. |
| Document stays at `awaiting_index` | Check `output/logs/rag.log`. See [Recovery and logs](docs/operations.md#recovery-and-logs) before retrying. |

Logs are saved in **`output/logs/`**. Documents, search indexes, and recovery files live under **`output/`** too—keep that folder when restarting or updating the app.

## Working on the code

| Folder | Contains |
| --- | --- |
| `mobile/` | Android app, built with Flutter. |
| `web/` | Admin dashboard, built with Next.js. |
| `backend/` | Main API, built with FastAPI. |
| `rag/` | AI search, answers, and indexing. |
| `shared/` | Code shared by the Python services. |
| `scripts/` | Launchers and maintenance utilities. |
| `supabase/` | Database setup instructions and SQL. |

See [Detailed operations](docs/operations.md) for setup, Android release builds, account administration, and document recovery.
