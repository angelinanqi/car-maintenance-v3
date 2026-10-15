# Admin dashboard

Next.js/React dashboard with Chakra UI and TipTap. Administrators manage vehicles,
maintenance schedules, learning guides, emergency content, reference documents,
and chatbot previews through the FastAPI backend.

## Run

Use Node.js 22/npm. Complete the [root setup](../../README.md) for Supabase,
the backend, and administrator access. From this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:3000/login. The launcher loads the root `.env`;
`FRONTEND_PORT` defaults to `3000`. Set `NEXT_PUBLIC_API_URL` to a browser-reachable
backend URL and allow the dashboard origin in backend `CORS_ORIGINS`.

## Check and build

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd start
```

`start` requires a production build. Rebuild after public configuration changes.
On other operating systems, use `npm` in place of `npm.cmd`.

Document upload, processing, indexing, and publication are separate stages.
PDFs require MinerU; indexing and AI chat require the [RAG processes](../../rag/README.md).
