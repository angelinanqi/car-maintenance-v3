import logging
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.routes import (
    accounts,
    admin,
    categories,
    chat,
    chat_sources,
    configuration,
    companion,
    dashboard,
    documents,
    document_tests,
    emergency,
    guides,
    indexing,
    maintenance_assistance,
    manuals,
    mobile,
    nearby,
    review_questions,
    scopes,
    youtube,
)
from backend.services.documents import recover_interrupted, retry_pending_extractions
from backend.services.youtube import recover_interrupted as recover_youtube_syncs
from backend.settings import CORS_ORIGINS
from shared.http_errors import http_error, validation_error


@asynccontextmanager
async def lifespan(app):
    try:
        await run_in_threadpool(recover_interrupted)
        await run_in_threadpool(recover_youtube_syncs)
    except Exception:
        logging.getLogger(__name__).exception("Could not recover interrupted jobs; check Supabase configuration.")
    stop_retries = asyncio.Event()
    retry_task = asyncio.create_task(resume_extractions(stop_retries))
    try:
        yield
    finally:
        stop_retries.set()
        await retry_task


async def resume_extractions(stop):
    while not stop.is_set():
        try:
            await run_in_threadpool(retry_pending_extractions)
        except Exception:
            logging.getLogger(__name__).exception("Extraction recovery pass failed; will retry")
        try:
            await asyncio.wait_for(stop.wait(), timeout=15)
        except TimeoutError:
            pass


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(RequestValidationError, validation_error)
app.add_exception_handler(StarletteHTTPException, http_error)
app.include_router(chat_sources.router)
app.include_router(maintenance_assistance.router)
app.include_router(review_questions.router)
app.include_router(chat.router)
app.include_router(document_tests.router)
app.include_router(configuration.router)


@app.middleware("http")
async def prevent_response_caching(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


for router in (
    documents.router,
    guides.router,
    categories.router,
    emergency.router,
    dashboard.router,
    accounts.router,
    manuals.router,
    scopes.router,
    indexing.router,
    youtube.router,
    youtube.internal_router,
    admin.router,
    admin.mobile_router,
    mobile.router,
    companion.router,
    nearby.router,
):
    app.include_router(router)


@app.exception_handler(APIError)
async def database_error(request, error):
    logging.getLogger(__name__).exception("Database operation failed", exc_info=error)
    if error.code in {"23503", "23001"}:
        return JSONResponse(status_code=409, content={"detail": "This record is still referenced, or the selected related record no longer exists."})
    if error.code == "23505":
        return JSONResponse(status_code=409, content={"detail": "A record with this name already exists."})
    if error.code == "P0001":
        return JSONResponse(status_code=409, content={"detail": "This publication revision changed or is no longer eligible. Reload the record and review its current state."})
    if error.code in {"42703", "42P01", "PGRST204", "PGRST205"}:
        return JSONResponse(status_code=503, content={"detail": "The database schema is out of date. Check supabase/README.md for schema setup and retry."})
    return JSONResponse(status_code=503, content={"detail": "Database operation failed. Check the Supabase configuration and schema, then retry."})


@app.exception_handler(Exception)
async def integration_error(request, error):
    logging.getLogger(__name__).exception("Application operation failed", exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "The operation could not be completed. Please retry."}, headers={"Cache-Control": "no-store"})


@app.exception_handler(httpx.RequestError)
async def network_error(request, error):
    logging.getLogger(__name__).warning("Dependency connection failed (%s)", type(error).__name__)
    return JSONResponse(status_code=503, content={"detail": "A required service is temporarily unavailable. Please retry."}, headers={"Cache-Control": "no-store"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    allow_credentials=True,
)


@app.get("/")
def read_root():
    return {"message": "FYP backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
