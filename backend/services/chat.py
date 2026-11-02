"""Account-owned, immutable conversation scopes and server-loaded history."""
import hashlib
import asyncio
import json
import logging
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
from shared.safety import immediate_emergency, emergency_guidance

# One process is the existing supported backend deployment. Concurrent turns
# in one conversation are rejected instead of interleaving their histories.
_active = set()
EMERGENCY_PROTOCOL_TIMEOUT = 1.0


def create_session(session_id, token, user):
    from backend.locks import content_lock
    with content_lock('chat:' + session_id):
        existing = db.all_rows('chat_sessions', id=session_id)
        if existing:
            row = authorize_session(session_id, token, user)
            enforce_automatic_vehicle(row, user)
        else:
            vehicle = vehicle_profiles.active_vehicle(user)
            values = {'id': session_id, 'automatic': True, 'user_id': user['id'],
                      'user_vehicle_id': vehicle['id'] if vehicle else None,
                      'vehicle_id': vehicle['catalogue_id'] if vehicle else None,
                      'token_hash': hashlib.sha256(token.encode()).hexdigest()}
            enforce_automatic_vehicle(values, user)
            db.insert('chat_sessions', values)
    return {'session_id': session_id, 'session_token': token}


def request_hash(request):
    values = request.model_dump(mode='json', exclude={'session_token', 'conversation'})
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


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


def conversation_scope(kind, identity, *, safety_only=False):
    if not safety_only:
        return scopes.resolve(kind, identity)
    # Safety guidance uses no manuals or personal maintenance evidence.
    return {'scope_type': kind, 'scope_id': str(identity), 'label': 'Emergency assistance',
            'document_ids': [], 'document_metadata': {}, 'content_sources': [], 'video_ids': []}


def automatic_scope(row, user, *, safety_only=False):
    return conversation_scope('auto', enforce_automatic_vehicle(row, user), safety_only=safety_only)


def load(request, user, *, safety_only=False):
    token = request.session_token
    automatic = not request.scope_type and not request.scope_id and not request.car_model
    if request.session_id:
        row = authorize_session(request.session_id, token, user)
        if row.get('automatic'):
            if request.scope_type or request.scope_id:
                raise HTTPException(409, 'Start a new chat to change conversation mode.')
            scope = automatic_scope(row, user, safety_only=safety_only)
            if safety_only:
                return row, token, scope, [], None, None
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
            scope = automatic_scope(values, user, safety_only=safety_only)
            profile = None if safety_only else vehicle_profiles.load(user)
            row = db.insert('chat_sessions', values)
            if safety_only:
                return row, token, scope, [], None, None
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
        conversation_scope(kind, identity, safety_only=safety_only)
        token = secrets.token_urlsafe(32)
        row = db.insert("chat_sessions", {kind + "_id": str(identity),
                         'user_id': user['id'], 'user_vehicle_id': personal_id,
                         "token_hash": hashlib.sha256(token.encode()).hexdigest()})
    enforce_vehicle(user, kind, identity, row.get('user_vehicle_id'))
    scope = conversation_scope(kind, identity, safety_only=safety_only)
    if safety_only:
        return row, token, scope, [], None, None
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
        safety_only = immediate_emergency(request.message)
        row, token, scope, history, profile, maintenance = await run_in_threadpool(
            load, request, user, safety_only=safety_only)
        identity = row["id"]
        _active.add(identity)
        if request.request_id:
            saved = await run_in_threadpool(db.all_rows, 'chat_messages', id=str(request.request_id))
            if saved:
                message = saved[0]
                if (message['session_id'] != identity or message['role'] != 'assistant'
                        or (message.get('reply') or {}).get('request_hash') != request_hash(request)):
                    raise HTTPException(409, 'This question ID has already been used. Restore the conversation before continuing.')
                if safety_only:
                    try:
                        scope['content_sources'] = await asyncio.wait_for(
                            run_in_threadpool(optional_emergency_sources), EMERGENCY_PROTOCOL_TIMEOUT)
                    except TimeoutError:
                        scope['content_sources'] = []
                restored = await run_in_threadpool(restore_messages, [message], scope, identity, user)
                return {**restored[0]['reply'], 'session_id': identity, 'session_token': token,
                        'scope_type': scope['scope_type'], 'scope_id': scope['scope_id']}
        if safety_only:
            answer = await emergency_reply(request.message)
            if row.get('automatic'):
                await run_in_threadpool(enforce_automatic_vehicle, row, user)
            else:
                await run_in_threadpool(enforce_vehicle, user, scope['scope_type'], scope['scope_id'], row.get('user_vehicle_id'))
            answer['message_id'] = await run_in_threadpool(
                save_turn, identity, request.message, answer, [],
                str(request.request_id) if request.request_id else None, request_hash(request))
            return {**answer, 'session_id': identity, 'session_token': token,
                    'scope_type': scope['scope_type'], 'scope_id': scope['scope_id']}
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
        if answer.get('response_type') in {'generation_error', 'retrieval_error'}:
            raise HTTPException(503, 'The AI service could not complete this question. Retry shortly.')
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
        answer['message_id'] = await run_in_threadpool(
            save_turn, identity, request.message, answer, attachment_refs,
            str(request.request_id) if request.request_id else None, request_hash(request))
        return {**answer, "session_id": identity, "session_token": token,
                "scope_type": scope["scope_type"], "scope_id": scope["scope_id"]}
    finally:
        _active.discard(identity)


def optional_emergency_sources():
    from backend.services.content_sources import emergency_sources
    try:
        return emergency_sources()
    except Exception as error:
        # Only optional published-content loading is recoverable here. Session,
        # ownership and vehicle failures are never converted into safety replies.
        logging.getLogger(__name__).warning('Emergency protocols unavailable (%s)', type(error).__name__)
        return []


def reviewed_emergency_supplement(question):
    from backend.services.content_sources import emergency_supplement
    text, sources = emergency_supplement(question, optional_emergency_sources())
    if sources:
        # Recheck the exact revision before returning reviewed protocol text.
        current = {(source['source_id'], source['revision']) for source in optional_emergency_sources()}
        if any((source['source_id'], source['revision']) not in current for source in sources):
            text, sources = '', []
    return text, sources


async def emergency_reply(question):
    # Optional protocol reads have one shared, short deadline. A slow content
    # dependency cannot delay basic guidance until its normal database timeout.
    text, sources = '', []
    try:
        text, sources = await asyncio.wait_for(
            run_in_threadpool(reviewed_emergency_supplement, question), EMERGENCY_PROTOCOL_TIMEOUT)
    except Exception as error:
        logging.getLogger(__name__).warning('Emergency supplement skipped (%s)', type(error).__name__)
    return {'answer': emergency_guidance(question) + text, 'route': 'emergency',
            'response_type': 'emergency_protocol' if sources else 'emergency',
            'sources': sources, 'videos': [], 'attachments': [], 'manual_links': [],
            'recommended_guides': [], 'manual_relevant': False, 'external_warning': False}


def save_turn(session_id, question, answer, attachment_refs=None, message_id=None, fingerprint=None):
    # One database insert makes the pair visible atomically in order.
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    from uuid import uuid4
    message_id = message_id or str(uuid4())
    # Signed media URLs are regenerated under current source permissions on restore.
    reply = deepcopy(answer)
    reply.pop('attachments', None)
    reply.pop('manual_links', None)
    reply['attachment_refs'] = attachment_refs or []
    reply['request_hash'] = fingerprint
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
    # Reading history is independent of the short context window sent to the model.
    messages = db.all_rows('chat_messages', session_id=session_id)
    if message_id:
        anchor = next((message for message in messages if message['id'] == message_id), None)
        if not anchor or anchor['role'] != 'assistant':
            raise HTTPException(404, 'This saved explanation does not belong to the conversation.')
    result = restore_messages(messages, scope, session_id, user)
    token = secrets.token_urlsafe(32)
    db.update('chat_sessions', session_id, {'token_hash': hashlib.sha256(token.encode()).hexdigest()})
    return {'session_id': session_id, 'session_token': token, 'activity': row.get('activity'), 'messages': result,
            'selected_message_id': message_id}


def restore_messages(messages, scope, session_id, user):
    content = {(source['source_type'], source['source_id']): source for source in scope.get('content_sources', [])}
    result = []
    for message in messages:
        reply = deepcopy(message.get('reply') or {})
        reply.pop('request_hash', None)
        from backend.services.content_sources import resolve_guide_recommendations
        reply['recommended_guides'] = resolve_guide_recommendations(
            reply.get('recommended_guides', []), scope.get('content_sources', []))
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
            resolved, links = resolve_manual_sources(
                manuals, scope, session_id, user,
                browse=reply.get('response_type') == 'insufficient_information')
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
    return result
