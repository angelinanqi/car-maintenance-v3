import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from rag.app.query import handle_query

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

# temporary hard coded
MANUALS = {
    "general": None,
    "myvi": "myvi-2005-owner-manual-eng",
    "axia": "axia-2023---current-owner-manual-eng",
}


class ChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=4000)
    car_model: Literal["general", "myvi", "axia", "bezza"] = "general"
    conversation: list[ChatMessage] = Field(default_factory=list, max_length=6)


@app.get("/")
def read_root():
    return {"message": "FYP backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    if request.car_model not in MANUALS:
        raise HTTPException(
            status_code=422,
            detail="No Bezza manual is available. Choose another vehicle or General.",
        )
    try:
        return await handle_query(
            request.message,
            conversation=[message.model_dump() for message in request.conversation],
            document_name=MANUALS[request.car_model],
        )
    except Exception:
        logging.getLogger(__name__).exception("RAG chat request failed")
        raise HTTPException(
            status_code=503,
            detail="The chatbot could not complete your request. Check the backend's RAG configuration and try again.",
        ) from None
