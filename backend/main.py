from backend.settings import CHAT_MAX_MESSAGE_LENGTH, CHAT_HISTORY_LIMIT
import logging
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError
from backend.routes import documents, guides, categories, emergency, dashboard, accounts, manuals, scopes, indexing, admin, mobile, nearby
from backend.services.documents import recover_interrupted
from backend import settings
from backend.routes import chat_sources
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from backend.settings import CORS_ORIGINS
from backend.models import MechanicPreparationRequest, MechanicPreparation

@asynccontextmanager
async def lifespan(app):
    try:
        await run_in_threadpool(recover_interrupted)
    except Exception:
        logging.getLogger(__name__).exception("Could not recover interrupted jobs; check Supabase configuration.")
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(chat_sources.router)


@app.middleware("http")
async def prevent_response_caching(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


for router in (documents.router, guides.router, categories.router, emergency.router, dashboard.router, accounts.router, manuals.router, scopes.router, indexing.router, admin.router, admin.mobile_router, mobile.router, nearby.router):
    app.include_router(router)


@app.exception_handler(APIError)
async def database_error(request, error):
    logging.getLogger(__name__).exception("Database operation failed", exc_info=error)
    if error.code == "23503":
        return JSONResponse(status_code=409, content={"detail": "This record is still referenced, or the selected related record no longer exists."})
    if error.code == "23505":
        return JSONResponse(status_code=409, content={"detail": "A record with this name already exists."})
    if error.code == "P0001":
        return JSONResponse(status_code=409, content={"detail": "This publication revision changed or is no longer eligible. Reload the record and review its current state."})
    return JSONResponse(status_code=503, content={"detail": "Database operation failed. Check the Supabase configuration and schema, then retry."})


@app.exception_handler(Exception)
async def integration_error(request, error):
    logging.getLogger(__name__).exception("Application operation failed", exc_info=error)
    return JSONResponse(status_code=503, content={"detail": "The operation failed. Check backend logs and service configuration, then retry."})
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    allow_credentials=True,
)

class ChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=CHAT_MAX_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(min_length=1, max_length=CHAT_MAX_MESSAGE_LENGTH)
    car_model: str | None = None
    conversation: list[ChatMessage] = Field(default_factory=list, max_length=CHAT_HISTORY_LIMIT)
    scope_type: Literal["vehicle", "category"] | None = None
    scope_id: str | None = None
    session_id: str | None = Field(default=None, max_length=36)
    session_token: str | None = Field(default=None, max_length=128)


@app.get("/")
def read_root():
    return {"message": "FYP backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest, user=Depends(mobile.require_user)):
    from backend.services.chat import send
    try:
        return await send(request, user)
    except HTTPException:
        raise
    except Exception as error:
        logging.getLogger(__name__).error("RAG chat request failed (%s)", type(error).__name__)
        raise HTTPException(
            status_code=503,
            detail="The chatbot is temporarily unavailable. Please try again shortly.",
        ) from None


@app.post('/chat/mechanic-questions', response_model=MechanicPreparation)
async def prepare_mechanic_questions(request: MechanicPreparationRequest, user=Depends(mobile.require_user)):
    from backend.services.mechanic_preparation import prepare
    return await prepare(request, user)


@app.get("/config")
def configuration():
    from backend.services.scopes import catalog
    knowledge = catalog()
    return {"knowledge_scopes": knowledge,
            "vehicle_scopes": [{"value": s["code"], "label": s["label"], "disabled": not s["available"]}
                               for s in knowledge if s["scope_type"] == "vehicle"],
            "chat_max_message_length": settings.CHAT_MAX_MESSAGE_LENGTH,
            "chat_history_limit": settings.CHAT_HISTORY_LIMIT,
            "api_page_size": settings.API_PAGE_SIZE,
            "image_max_bytes": settings.IMAGE_MAX_BYTES,
            "rag_configured": bool(settings.RAG_SERVICE_URL and settings.RAG_SERVICE_TOKEN)}
