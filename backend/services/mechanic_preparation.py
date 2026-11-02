"""Prepare a private, account-owned discussion brief without requiring a manual."""
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from shared.mechanic_questions import vehicle_summary
from shared.models import MechanicQuestionDraft
from backend import db
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
    plan = None
    if request.plan_id:
        from backend.services.service_planning import get_plan
        plan = await run_in_threadpool(get_plan, user, str(request.plan_id))
        if plan['stale']:
            raise HTTPException(409, 'Refresh your service plan before preparing new mechanic notes.')
        # Keep model input bounded; the complete plan remains available in the UI.
        import json
        facts = {'as_of': plan['snapshot']['as_of'], 'mileage': plan['snapshot']['mileage'], 'items': []}
        for group, entries in plan['snapshot']['groups'].items():
            if group == 'upcoming':
                continue
            for item in entries:
                candidate = {key: item[key] for key in ('title', 'action', 'status', 'schedule_source')}
                if len(json.dumps(facts)) + len(json.dumps(candidate)) > 12000:
                    break
                facts['items'].append({'group': group, **candidate})
        questions.append('Server-calculated service proposal (not a diagnosis): ' + json.dumps(facts))
    draft, tailored = await rag_client.mechanic_questions(request.question, questions, profile)
    configuration = await run_in_threadpool(db.get, 'chat_settings', 'default')
    if not tailored:
        template = configuration.get('mechanic_template')
        if not template:
            raise HTTPException(503, 'Personalised preparation is unavailable and no administrator checklist is published. You can still write your own notes.')
        draft = MechanicQuestionDraft.model_validate({**template, 'concern_summary': request.question[:600]})
    current = await run_in_threadpool(vehicle_profiles.load, user)
    if current != profile:
        raise HTTPException(409, 'Your active vehicle profile changed. Please prepare the questions again.')
    if plan:
        fresh = await run_in_threadpool(get_plan, user, str(request.plan_id))
        if fresh['stale']:
            raise HTTPException(409, 'Your maintenance changed. Refresh the plan before preparing notes.')
    return MechanicPreparation(**draft.model_dump(), vehicle_summary=vehicle_summary(profile),
                               details_to_note=configuration.get('mechanic_details', []), tailored=tailored)
