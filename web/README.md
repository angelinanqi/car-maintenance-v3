# Admin dashboard

The Next.js dashboard manages vehicles, manuals, schedules, learning guides, emergency content, and chatbot settings. It uses React and Chakra UI and sends requests through its server-side proxy to the FastAPI backend.

## Set up and run

Complete the Python, Supabase, and account setup in the [main README](../README.md). Install Node.js 22, then run from the project root:

```bash
npm --prefix web ci
npm --prefix web run build
./start-app.command
```

Open [http://127.0.0.1:3000/login](http://127.0.0.1:3000/login). For Tailscale access, use your Mac's HTTPS hostname on port **8443**. Sign in with an administrator account and complete MFA.

The normal launcher starts the dashboard automatically. To run only the dashboard against an already running backend, use `npm --prefix web start` instead. Keep port 3000 free before doing so.

## Configuration and changes

The npm scripts load the root [app.config.json](../app.config.json). The main settings are:

| Setting | Purpose |
| --- | --- |
| `BACKEND_API_URL` | Backend address reached by the Next.js server; normally `http://127.0.0.1:8000` |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Browser authentication |
| `FRONTEND_HOST`, `FRONTEND_PORT` | Dashboard listener; normally `127.0.0.1:3000` |

After code or public-setting changes, stop the app launcher, run `npm --prefix web run build`, and restart the launcher. Keep private keys in the backend's `.env`.

## Live logs

Run `./scripts/logs.sh --web` from the project root for proxy HTTP results and operation summaries. The same-origin proxy labels its backend requests `WEB` and preserves request IDs. The viewer merges matching proxy/backend observations into one entry.

Browser DevTools also shows completed shared-client requests, direct authentication failures, and unexpected browser errors while `DEV_LOGGING` is `"true"`. Detailed exception locations remain in private server logs. Browser-only failures are not transmitted to the laptop viewer. Set `DEV_LOGGING` to `"false"` and rebuild/restart to disable these diagnostics in production.

## Add content

1. Create the vehicle or learning topic first.
2. In **Reference Library**, upload PDF or Markdown files and assign their coverage.
3. Process the document with Windows OCR available for PDFs.
4. Check the extracted text, tables, images, and vehicle applicability. Save corrections, then confirm and rebuild the index.
5. Approve and publish the source. Enable the relevant chatbot scope separately.

To use a webpage, save it as a PDF in your browser and upload it through the same workflow.

Learning guides support uploaded images and embedded YouTube videos. Emergency media is uploaded against individual steps. For emergency MP4 uploads, install FFmpeg so `ffprobe` is available on the backend's `PATH`; use H.264 video and optional AAC audio. The default video limit is 50 MiB and image limit is 10 MiB. If the Supabase content bucket has MIME or size restrictions, allow these uploads there too.

For failures, check the terminal and `output/logs/web.log`. API or document-processing failures are usually explained in `output/logs/backend.log` or `rag.log`.
