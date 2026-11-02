"""Authenticated chat and mechanic-preparation endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from backend import auth
from backend.models import ChatRequest, MechanicPreparationRequest, MechanicPreparation
from backend.companion_models import ActivityUpdate, ChatSessionInput
from uuid import UUID

router = APIRouter()


@router.put('/chat/sessions/{session_id}')
def create_session(session_id: UUID, request: ChatSessionInput, user=Depends(auth.require_user)):
    from backend.services.chat import create_session
    return create_session(str(session_id), request.session_token, user)


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


@router.post('/chat/sessions/{session_id}/resume')
def resume_chat(session_id: UUID, message_id: UUID | None = None, user=Depends(auth.require_user)):
    from backend.services.chat import resume
    return resume(str(session_id), user, str(message_id) if message_id else None)


@router.put('/chat/sessions/{session_id}/activity')
def set_activity(session_id: UUID, request: ActivityUpdate, user=Depends(auth.require_user)):
    from backend.services.chat import automatic_scope, enforce_vehicle
    from backend.services.personal_records import owned
    from backend.services.learning_companion import resolve
    from backend import db
    row = owned('chat_sessions', user['id'], str(session_id))
    if row.get('automatic'):
        scope = automatic_scope(row, user)
    else:
        from backend.services import scopes
        kind = 'vehicle' if row.get('vehicle_id') else 'category'
        enforce_vehicle(user, kind, row[kind + '_id'], row.get('user_vehicle_id'))
        scope = scopes.resolve(kind, row[kind + '_id'])
    if request.activity:
        resolve(request.activity, user, scope)
    activity = request.activity.model_dump(mode='json') if request.activity else None
    db.update('chat_sessions', session_id, {'activity': activity})
    return {'activity': activity}
