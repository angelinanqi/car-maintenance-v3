"""Authenticated chat and mechanic-preparation endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from backend import auth
from backend.models import ChatRequest, MechanicPreparationRequest, MechanicPreparation

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest, user=Depends(auth.require_user)):
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


@router.post('/chat/mechanic-questions', response_model=MechanicPreparation)
async def prepare_mechanic_questions(request: MechanicPreparationRequest, user=Depends(auth.require_user)):
    from backend.services.mechanic_preparation import prepare
    return await prepare(request, user)
