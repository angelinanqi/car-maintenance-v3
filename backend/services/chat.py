"""Account-owned, immutable conversation scopes and server-loaded history."""
import hashlib
import secrets
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


def load(request, user):
    token = request.session_token
    if request.session_id:
        row = authorize_session(request.session_id, token, user)
        kind = "vehicle" if row.get("vehicle_id") else "category"
        identity = row[kind + "_id"]
        if (request.scope_type and request.scope_type != kind) or (request.scope_id and request.scope_id != identity):
            raise HTTPException(409, "Start a new chat to change knowledge scope.")
    else:
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
        answer = await rag_client.query(request.message, history, scope, vehicle_profile=profile,
                                       maintenance_context=maintenance)
        # Re-resolve before exposing an answer if an admin changed eligibility
        # during retrieval/generation. Do not persist the stale response.
        current = await run_in_threadpool(scopes.resolve, scope["scope_type"], scope["scope_id"])
        if current != scope:
            raise HTTPException(409, "Knowledge associations changed. Please retry your question.")
        await run_in_threadpool(enforce_vehicle, user, scope['scope_type'], scope['scope_id'], row.get('user_vehicle_id'))
        from backend.services.source_assets import attachments
        answer['attachments'] = await run_in_threadpool(attachments, answer.get('attachments', []), current, identity)
        if answer['attachments']:
            final_scope = await run_in_threadpool(scopes.resolve, scope['scope_type'], scope['scope_id'])
            if final_scope != scope:
                raise HTTPException(409, 'Knowledge associations changed while resolving sources. Retry your question.')
        current_profile = await run_in_threadpool(vehicle_profiles.load, user)
        if current_profile != profile:
            raise HTTPException(409, 'Your active vehicle profile changed. Please retry your question.')
        current_maintenance = await run_in_threadpool(personal_maintenance.load, user, current_profile)
        if current_maintenance != maintenance:
            raise HTTPException(409, 'Your maintenance records or schedule changed. Please retry your question.')
        if answer.get('response_type') not in {'generation_error', 'retrieval_error'}:
            await run_in_threadpool(save_turn, identity, request.message, answer["answer"])
        return {**answer, "session_id": identity, "session_token": token,
                "scope_type": scope["scope_type"], "scope_id": scope["scope_id"]}
    finally:
        _active.discard(identity)


def save_turn(session_id, question, answer):
    # One database insert makes the pair visible atomically in order.
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    db.client().table("chat_messages").insert([
        {"session_id": session_id, "role": "user", "content": question, "created_at": now.isoformat()},
        {"session_id": session_id, "role": "assistant", "content": answer,
         "created_at": (now + timedelta(microseconds=1)).isoformat()},
    ]).execute()
