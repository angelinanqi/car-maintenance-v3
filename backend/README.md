# Backend API

FastAPI handles accounts, permissions, admin content, personal maintenance data,
Supabase storage, document processing, and requests to the private AI service.

## Run

Complete the [root setup](../README.md) for `.env` and Supabase first. From the
repository root, using Python 3.12:

```powershell
py -3.12 -m venv .venv-api
.\.venv-api\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv-api\Scripts\python.exe -m backend
```

- API documentation: http://127.0.0.1:8000/docs.
- Health check: http://127.0.0.1:8000/health (process liveness only).
- Run one backend process; processing locks and recovery depend on this.
- PDF extraction needs a separate MinerU installation and `MINERU_EXECUTABLE`.
- AI chat and document indexing need the separate [RAG processes](../rag/README.md).
- Browser access uses session cookies and CSRF; mobile uses bearer tokens.

Set `NEXT_PUBLIC_API_URL` and `CORS_ORIGINS` for the admin's browser connection.
For a physical phone on the LAN, bind `BACKEND_HOST=0.0.0.0` and use the server's
reachable address. Keep the Supabase service-role key and other secrets on the server.
