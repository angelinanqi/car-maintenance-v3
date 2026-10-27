"""Prepare a private, account-owned discussion brief without requiring a manual."""
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from shared.mechanic_questions import DETAILS_TO_NOTE, vehicle_summary
from backend.models import MechanicPreparation
from backend.services import chat, rag_client, vehicle_profiles


def load_context(request, user):
    profile = vehicle_profiles.load(user)
    personal_id = profile['vehicle_id'] if profile else None
    if request.vehicle_id != personal_id:
        raise HTTPException(409, 'The active vehicle changed. Reopen question preparation for the selected vehicle.')
    questions = []
    if request.session_id:
        session = chat.authorize_session(request.session_id, request.session_token, user)
        if session.get('automatic'):
            chat.automatic_scope(session, user)
        else:
            kind = 'vehicle' if session.get('vehicle_id') else 'category'
            chat.enforce_vehicle(user, kind, session[kind + '_id'], session.get('user_vehicle_id'))
        if personal_id != session.get('user_vehicle_id'):
            raise HTTPException(409, 'This conversation belongs to a different active vehicle.')
        # Assistant answers may be uncertain. They are not evidence for a diagnosis.
        questions = [m['content'] for m in chat.recent_messages(session['id']) if m['role'] == 'user']
    return profile, questions


async def prepare(request, user):
    profile, questions = await run_in_threadpool(load_context, request, user)
    draft, tailored = await rag_client.mechanic_questions(request.question, questions, profile)
    current = await run_in_threadpool(vehicle_profiles.load, user)
    if current != profile:
        raise HTTPException(409, 'Your active vehicle profile changed. Please prepare the questions again.')
    return MechanicPreparation(**draft.model_dump(), vehicle_summary=vehicle_summary(profile),
                               details_to_note=DETAILS_TO_NOTE, tailored=tailored)
