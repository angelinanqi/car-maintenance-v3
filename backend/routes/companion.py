"""Published learning discovery and account-owned learning tools."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from backend import auth, db, settings
from backend.companion_models import PlanPreviewInput, PlanSaveInput, SavedItemInput, NoteUpdate
from backend.services import learning_companion, service_planning
from backend.services.personal_records import owned

router = APIRouter(prefix='/mobile/me', tags=['Learning companion'])


@router.get('/companion')
def companion(user=Depends(auth.require_user)):
    return learning_companion.discovery(user)


@router.post('/service-plans/preview')
def preview_plan(request: PlanPreviewInput, user=Depends(auth.require_user)):
    return service_planning.preview(user, request.vehicle_id)


@router.post('/service-plans')
def save_plan(request: PlanSaveInput, user=Depends(auth.require_user)):
    return service_planning.save(user, request.vehicle_id, request.fingerprint)


@router.get('/service-plans/{plan_id}')
def get_plan(plan_id: UUID, user=Depends(auth.require_user)):
    return service_planning.get_plan(user, str(plan_id))


@router.post('/service-plans/{plan_id}/refresh')
def refresh_plan(plan_id: UUID, user=Depends(auth.require_user)):
    old = owned('service_plans', user['id'], str(plan_id))
    current = service_planning.preview(user, old['vehicle_id'])
    # A refresh returns a proposal; explicit Save creates a new snapshot.
    return current


def saved_view(row):
    result = dict(row)
    result['available'] = True
    if row['kind'] == 'guide':
        try:
            learning_companion.published_guide(row.get('guide_id'))
        except HTTPException as error:
            if error.status_code != 404:
                raise
            result['available'] = False
    if row['kind'] == 'explanation':
        # Explanations reopen through the session endpoint, which revalidates sources.
        result['available'] = bool(row.get('message_id'))
    if row['kind'] == 'plan':
        result['available'] = bool(row.get('plan_id'))
    return result


@router.get('/saved-items')
def saved_items(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000), user=Depends(auth.require_user)):
    return [saved_view(row) for row in db.list_rows('saved_items', user_id=user['id'], offset=offset, limit=limit)]


@router.post('/saved-items')
def save_item(request: SavedItemInput, user=Depends(auth.require_user)):
    from backend.locks import content_lock
    with content_lock('saved-items:' + user['id']):
        return persist_saved_item(request, user)


def persist_saved_item(request, user):
    values = request.model_dump(mode='json', exclude={'text'})
    if request.plan_id:
        plan = service_planning.get_plan(user, str(request.plan_id))
        values['vehicle_id'] = plan['vehicle_id']
    if request.id:
        existing = db.all_rows('saved_items', id=str(request.id))
        if existing:
            row = existing[0]
            if row['user_id'] != user['id']:
                raise HTTPException(404, 'Saved item not found.')
            if (request.kind != 'notes' or row['kind'] != 'notes'
                    or row['title'] != request.title or row.get('vehicle_id') != values.get('vehicle_id')
                    or row.get('plan_id') != (str(request.plan_id) if request.plan_id else None)
                    or row.get('payload', {}).get('text') != request.text):
                raise HTTPException(409, 'These notes were already saved. Reopen them from Saved to edit the saved copy.')
            return saved_view(row)
    else:
        values.pop('id', None)
    if request.vehicle_id:
        owned('user_vehicles', user['id'], request.vehicle_id)
    payload = {}
    if request.guide_id:
        guide = learning_companion.published_guide(request.guide_id)
        payload['revision'] = str(guide['updated_at'])
        values['title'] = guide['title']
    if request.message_id:
        message = db.get('chat_messages', request.message_id)
        session = owned('chat_sessions', user['id'], message['session_id'])
        if message['role'] != 'assistant':
            raise HTTPException(422, 'Save an assistant explanation.')
        values['vehicle_id'] = session.get('user_vehicle_id')
        payload['session_id'] = session['id']
    if request.kind == 'notes':
        payload['text'] = request.text
    # Repeat taps on a referenced resource are idempotent; notes remain distinct drafts.
    reference_field = {'guide': 'guide_id', 'plan': 'plan_id', 'explanation': 'message_id'}.get(request.kind)
    if reference_field:
        existing = db.all_rows('saved_items', user_id=user['id'], kind=request.kind, **{reference_field: values[reference_field]})
        if existing:
            return saved_view(existing[0])
    return saved_view(db.insert('saved_items', {**values, 'user_id': user['id'], 'payload': payload}))


@router.patch('/saved-items/{item_id}')
def edit_note(item_id: UUID, request: NoteUpdate, user=Depends(auth.require_user)):
    row = owned('saved_items', user['id'], str(item_id))
    if row['kind'] != 'notes':
        raise HTTPException(422, 'Only personal notes can be edited.')
    return db.update('saved_items', item_id, {'title': request.title, 'payload': {'text': request.text}})


@router.delete('/saved-items/{item_id}', status_code=204)
def remove_saved_item(item_id: UUID, user=Depends(auth.require_user)):
    owned('saved_items', user['id'], str(item_id))
    db.delete('saved_items', item_id)
    return Response(status_code=204)
