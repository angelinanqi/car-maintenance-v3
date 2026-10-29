"""Account-owned, immutable conversation scopes and server-loaded history."""
import hashlib
import secrets
from copy import deepcopy
from uuid import UUID
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from backend import db
from backend.services import scopes
from backend.services import rag_client
from backend.services import vehicle_profiles
from backend.services import personal_maintenance
from backend import settings

# One process is the existing supported backend deployment. Concurrent turns
# in one conversation are rejected instead of interleaving their histories.
_active = set()


def enforce_vehicle(user, kind, scope_id, personal_id=None):
    vehicle = vehicle_profiles.active_vehicle(user)
    if user.get('role') != 'admin':
        if kind == 'vehicle' and (not vehicle or vehicle['catalogue_id'] != str(scope_id)):
            raise HTTPException(409, 'Select this registered vehicle as active before starting or continuing its chat.')
        if personal_id is not None and (not vehicle or vehicle['id'] != personal_id):
            raise HTTPException(409, 'The active vehicle changed. Start or restore its separate conversation.')
    return vehicle['id'] if vehicle else None


def authorize_session(session_id, token, user):
    try:
        identity = str(UUID(str(session_id)))
    except ValueError:
        raise HTTPException(422, "Invalid chat session identifier.") from None
    row = db.get('chat_sessions', identity)
    if row.get('user_id') != user['id']:
        raise HTTPException(403, 'This chat session belongs to another account or a retired anonymous session.')
    digest = hashlib.sha256((token or '').encode()).hexdigest()
    if not secrets.compare_digest(digest, row['token_hash']):
        raise HTTPException(403, 'This chat session is not accessible.')
    return row


def enforce_automatic_vehicle(row, user):
    """Enforce the saved personal-vehicle identity, including a general chat."""
    vehicle = vehicle_profiles.active_vehicle(user)
    personal_id = vehicle['id'] if vehicle else None
    catalogue_id = vehicle['catalogue_id'] if vehicle else None
    if personal_id != row.get('user_vehicle_id') or catalogue_id != row.get('vehicle_id'):
        raise HTTPException(409, 'The active vehicle changed. Start or restore its separate conversation.')
    return catalogue_id or 'general'


def automatic_scope(row, user):
    return scopes.resolve('auto', enforce_automatic_vehicle(row, user))


def load(request, user):
    token = request.session_token
    automatic = not request.scope_type and not request.scope_id and not request.car_model
    if request.session_id:
        row = authorize_session(request.session_id, token, user)
        if row.get('automatic'):
            if request.scope_type or request.scope_id:
                raise HTTPException(409, 'Start a new chat to change conversation mode.')
            scope = automatic_scope(row, user)
            profile = vehicle_profiles.load(user)
            return row, token, scope, recent_messages(row['id']), profile, personal_maintenance.load(user, profile)
        kind = "vehicle" if row.get("vehicle_id") else "category"
        identity = row[kind + "_id"]
        if (request.scope_type and request.scope_type != kind) or (request.scope_id and request.scope_id != identity):
            raise HTTPException(409, "Start a new chat to change knowledge scope.")
    else:
        if automatic:
            vehicle = vehicle_profiles.active_vehicle(user)
            token = secrets.token_urlsafe(32)
            values = {'automatic': True, 'user_id': user['id'],
                      'user_vehicle_id': vehicle['id'] if vehicle else None,
                      'vehicle_id': vehicle['catalogue_id'] if vehicle else None,
                      'token_hash': hashlib.sha256(token.encode()).hexdigest()}
            scope = automatic_scope(values, user)
            profile = vehicle_profiles.load(user)
            row = db.insert('chat_sessions', values)
            return row, token, scope, [], profile, personal_maintenance.load(user, profile)
        kind, identity = request.scope_type, request.scope_id
        if not kind or not identity:
            # Old explicit vehicle clients can start a fresh scoped session;
            # their client-supplied conversation is never imported.
            matches = db.all_rows("knowledge_vehicles", code=request.car_model) if request.car_model and request.car_model != "general" else []
            if not matches:
                raise HTTPException(422, "Select a vehicle or category scope before starting a new chat.")
            kind, identity = "vehicle", matches[0]["id"]
        try:
            UUID(str(identity))
        except ValueError:
            raise HTTPException(422, "Use a valid knowledge scope identifier.") from None
        personal_id = enforce_vehicle(user, kind, identity)
        scopes.resolve(kind, identity)
        token = secrets.token_urlsafe(32)
        row = db.insert("chat_sessions", {kind + "_id": str(identity),
                         'user_id': user['id'], 'user_vehicle_id': personal_id,
                         "token_hash": hashlib.sha256(token.encode()).hexdigest()})
    enforce_vehicle(user, kind, identity, row.get('user_vehicle_id'))
    scope = scopes.resolve(kind, identity)
    profile = vehicle_profiles.load(user)
    personal_id = profile['vehicle_id'] if profile else None
    if user.get('role') != 'admin' and personal_id != row.get('user_vehicle_id'):
        raise HTTPException(409, 'The active vehicle changed. Start or restore its separate conversation.')
    if profile and kind == 'vehicle' and profile['catalogue_id'] != str(identity):
        raise HTTPException(409, 'The active vehicle does not match this knowledge scope.')
    # Client history is untrusted and may belong to another knowledge scope.
    messages = recent_messages(row["id"])
    maintenance = personal_maintenance.load(user, profile)
    return row, token, scope, messages, profile, maintenance


def recent_messages(session_id):
    messages = db.client().table("chat_messages").select("role,content").eq(
        "session_id", session_id).order("created_at", desc=True).order("id", desc=True).limit(
        settings.CHAT_HISTORY_LIMIT).execute().data
    return list(reversed(messages))


async def send(request, user):
    identity = request.session_id
    activity = getattr(request, 'activity', None)
    if identity:
        try:
            identity = str(UUID(identity))
        except ValueError:
            raise HTTPException(422, 'Invalid chat session identifier.') from None
    if identity and identity in _active:
        raise HTTPException(409, "A reply is already being generated for this conversation.")
    if identity:
        _active.add(identity)
    try:
        row, token, scope, history, profile, maintenance = await run_in_threadpool(load, request, user)
        identity = row["id"]
        _active.add(identity)
        activity_context = None
        activity_notice = None
        if activity:
            from backend.services.learning_companion import resolve
            try:
                activity_context = await run_in_threadpool(resolve, activity, user, scope)
            except HTTPException as error:
                if error.status_code not in {404, 409}:
                    raise
                # A withdrawn/stale activity must not prevent an ordinary or urgent question.
                activity_notice = error.detail
                activity = None
        rag_maintenance = maintenance
        if activity_context and activity_context['kind'] == 'plan' and maintenance:
            rag_maintenance = {**maintenance, 'service_plan': activity_context['plan']}
            activity_context = {key: value for key, value in activity_context.items() if key != 'plan'}
        answer = await rag_client.query(request.message, history, scope, vehicle_profile=profile,
                                       maintenance_context=rag_maintenance, activity_context=activity_context,
                                       assistance=getattr(request, 'assistance', None))
        if activity_notice:
            answer['activity_notice'] = activity_notice
        attachment_refs = deepcopy(answer.get('attachments', []))
        # Re-resolve before exposing an answer if an admin changed eligibility
        # during retrieval/generation. Do not persist the stale response.
        current = await run_in_threadpool(scopes.resolve, scope["scope_type"], scope["scope_id"])
        if current != scope:
            raise HTTPException(409, "Knowledge associations changed. Please retry your question.")
        if row.get('automatic'):
            await run_in_threadpool(enforce_automatic_vehicle, row, user)
        else:
            await run_in_threadpool(enforce_vehicle, user, scope['scope_type'], scope['scope_id'], row.get('user_vehicle_id'))
        from backend.services.source_assets import attachments, resolve_manual_sources
        answer['attachments'] = await run_in_threadpool(attachments, answer.get('attachments', []), current, identity)
        answer['sources'], answer['manual_links'] = await run_in_threadpool(
            resolve_manual_sources, answer.get('sources', []), current, identity, user,
            browse=answer.get('response_type') == 'insufficient_information')
        if answer['attachments'] or answer['sources'] or answer['manual_links']:
            final_scope = await run_in_threadpool(scopes.resolve, scope['scope_type'], scope['scope_id'])
            if final_scope != scope:
                raise HTTPException(409, 'Knowledge associations changed while resolving sources. Retry your question.')
        current_profile = await run_in_threadpool(vehicle_profiles.load, user)
        if current_profile != profile:
            raise HTTPException(409, 'Your active vehicle profile changed. Please retry your question.')
        current_maintenance = await run_in_threadpool(personal_maintenance.load, user, current_profile)
        if current_maintenance != maintenance:
            raise HTTPException(409, 'Your maintenance records or schedule changed. Please retry your question.')
        if activity:
            fresh = await run_in_threadpool(resolve, activity, user, current)
            if fresh['kind'] == 'plan':
                fresh = {key: value for key, value in fresh.items() if key != 'plan'}
            if fresh != activity_context:
                raise HTTPException(409, 'The activity changed. Reopen it before retrying.')
            await run_in_threadpool(db.update, 'chat_sessions', identity,
                                    {'activity': activity.model_dump(mode='json')})
        if answer.get('response_type') not in {'generation_error', 'retrieval_error'}:
            answer['message_id'] = await run_in_threadpool(save_turn, identity, request.message, answer, attachment_refs)
        return {**answer, "session_id": identity, "session_token": token,
                "scope_type": scope["scope_type"], "scope_id": scope["scope_id"]}
    finally:
        _active.discard(identity)


def save_turn(session_id, question, answer, attachment_refs=None):
    # One database insert makes the pair visible atomically in order.
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    from uuid import uuid4
    message_id = str(uuid4())
    # Signed media URLs are regenerated under current source permissions on restore.
    reply = deepcopy(answer)
    reply.pop('attachments', None)
    reply.pop('manual_links', None)
    reply['attachment_refs'] = attachment_refs or []
    db.client().table("chat_messages").insert([
        {"id": str(uuid4()), "session_id": session_id, "role": "user", "content": question,
         "reply": None, "created_at": now.isoformat()},
        {"id": message_id, "session_id": session_id, "role": "assistant", "content": answer['answer'], 'reply': reply,
         "created_at": (now + timedelta(microseconds=1)).isoformat()},
    ]).execute()
    return message_id


def resume(session_id, user, message_id=None):
    from backend.services.personal_records import owned
    row = owned('chat_sessions', user['id'], session_id)
    scope = automatic_scope(row, user) if row.get('automatic') else scopes.resolve(
        'vehicle' if row.get('vehicle_id') else 'category', row.get('vehicle_id') or row.get('category_id'))
    if not row.get('automatic'):
        enforce_vehicle(user, scope['scope_type'], scope['scope_id'], row.get('user_vehicle_id'))
    if session_id in _active:
        raise HTTPException(409, 'A reply is pending. Retry restoring this conversation shortly.')
    messages = db.client().table('chat_messages').select('*').eq('session_id', session_id).order(
        'created_at', desc=True).order('id', desc=True).limit(settings.CHAT_HISTORY_LIMIT).execute().data
    if message_id and not any(message['id'] == message_id for message in messages):
        anchor = db.get('chat_messages', message_id)
        if anchor['session_id'] != session_id or anchor['role'] != 'assistant':
            raise HTTPException(404, 'This saved explanation does not belong to the conversation.')
        # Include the explicitly saved older answer even outside the recent window.
        messages.append(anchor)
    content = {(source['source_type'], source['source_id']): source for source in scope.get('content_sources', [])}
    result = []
    for message in reversed(messages):
        reply = deepcopy(message.get('reply') or {})
        # Historical answers can be read, but old citations never regain permissions.
        valid = []
        for source in reply.get('sources', []):
            kind = source.get('source_type', 'manual')
            if kind in {'personal_maintenance', 'personal_vehicle_profile'}:
                valid.append(source)
            elif kind != 'manual':
                current = content.get((kind, source.get('source_id')))
                if current and current['revision'] == source.get('revision'):
                    valid.append(source)
        from backend.services.source_assets import resolve_manual_sources
        manuals = [source for source in reply.get('sources', []) if source.get('source_type', 'manual') == 'manual']
        try:
            resolved, links = resolve_manual_sources(manuals, scope, session_id, user)
        except (HTTPException, ValueError):
            resolved, links = [], []
        restored_attachments = []
        from backend.services.source_assets import attachments
        for descriptor in reply.pop('attachment_refs', []):
            try:
                restored_attachments.extend(attachments([descriptor], scope, session_id))
            except (HTTPException, ValueError):
                continue
        reply.update(answer=message['content'], sources=valid + resolved, manual_links=links,
                     attachments=restored_attachments, videos=[], message_id=message['id'])
        result.append({'id': message['id'], 'role': message['role'], 'content': message['content'],
                       'reply': reply if message['role'] == 'assistant' else None})
    token = secrets.token_urlsafe(32)
    db.update('chat_sessions', session_id, {'token_hash': hashlib.sha256(token.encode()).hexdigest()})
    return {'session_id': session_id, 'session_token': token, 'activity': row.get('activity'), 'messages': result,
            'selected_message_id': message_id}
