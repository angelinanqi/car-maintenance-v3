# Car Maintenance and Assistance

An Android app and web admin dashboard for vehicle maintenance, learning guides,
roadside assistance, and AI answers based on published reference documents.

| Component | Stack | Setup |
| --- | --- | --- |
| Backend API | Python, FastAPI | [backend/](backend/README.md) |
| Admin dashboard | Next.js, React, Chakra UI | [web-app/frontend/](web-app/frontend/README.md) |
| Android app | Flutter, Dart | [car_app/](car_app/README.md) |
| AI retrieval and indexing | Chroma, Sentence Transformers, Gemini or Ollama | [rag/](rag/README.md) |
| Database and file storage | Supabase | [supabase/](supabase/README.md) |

## Setup

Use Python 3.12, Node.js 22/npm, and a Supabase project. The mobile app also
requires Flutter with Dart compatible with `^3.11.5` and Android SDK tools.
Commands below run from the repository root in Windows PowerShell.

1. Copy `.env.example` to `.env` for a new checkout; edit the existing file if
   already configured. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a
   random `JWT_SECRET` containing at least 32 bytes. See
   [`.env.example`](.env.example) for other settings.
2. Run [`supabase/initial_schema.sql`](supabase/initial_schema.sql) once in a
   **fresh** Supabase project's SQL Editor.
3. Install and start the backend:

   ```powershell
   py -3.12 -m venv .venv-api
   .\.venv-api\Scripts\python.exe -m pip install -r backend/requirements.txt
   .\.venv-api\Scripts\python.exe -m backend
   ```

4. In another terminal, install and start the admin dashboard:

   ```powershell
   npm.cmd --prefix web-app/frontend ci
   npm.cmd --prefix web-app/frontend run dev
   ```

5. Register at http://localhost:3000/register, then promote your account in the
   Supabase SQL Editor:

   ```sql
   update public.app_users
   set role = 'admin'
   where email = 'your-email@example.com';
   ```

   Sign in at http://localhost:3000/login. Mobile and web use the same accounts.

The API defaults to http://127.0.0.1:8000; its interactive documentation is at
http://127.0.0.1:8000/docs. Run one backend process. `/health` checks process
liveness only. Stop each service with Ctrl+C in its terminal.

## AI and reference documents

Follow the [RAG setup](rag/README.md) to start the AI service and indexing worker
as separate processes. PDF processing requires a separate MinerU installation
and `MINERU_EXECUTABLE`; Markdown skips PDF extraction.

In the dashboard, create a vehicle or category scope, upload a reference document,
start processing, wait for indexing, then publish the eligible document and scope.
Uploading alone does not make content available to chat.

Keep `output/` writable and persistent: it holds processing artifacts and the
Chroma index. Keep credentials server-side. Google Places and YouTube integrations
are optional and use the keys in `.env.example`.

## Development checks

```powershell
npm.cmd --prefix web-app/frontend run lint
npm.cmd --prefix web-app/frontend run typecheck
npm.cmd --prefix web-app/frontend run build
```

Run `flutter analyze` from `car_app/`. Backend and RAG changes need manual checks
against configured services; there is no retained automated Python test suite.
