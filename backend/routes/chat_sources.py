from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from backend import db, settings
from backend.auth import require_user
from backend.services import scopes
from backend.services.chat import automatic_scope, enforce_vehicle
from backend.services.source_assets import extraction, element, original_download_allowed, image_bytes

router = APIRouter(prefix='/chat/sessions', tags=['Chat source evidence'])


def authorized(session_id, document_id, revision, user):
    session = db.get('chat_sessions', session_id)
    if session.get('user_id') != user['id']:
        raise HTTPException(404, 'Source not found.')
    if session.get('automatic'):
        scope = automatic_scope(session, user)
    else:
        kind = 'vehicle' if session.get('vehicle_id') else 'category'
        enforce_vehicle(user, kind, session[kind + '_id'], session.get('user_vehicle_id'))
        scope = scopes.resolve(kind, session[kind + '_id'])
    if not any(m['document_id'] == str(document_id) and m['index_revision'] == str(revision)
               for m in scope['document_metadata'].values()):
        raise HTTPException(404, 'This source revision is no longer available in this conversation.')
    document = db.get('documents', document_id)
    if document.get('source_revision') != str(revision):
        raise HTTPException(404, 'This source revision is no longer available in this conversation.')
    return document


@router.get('/{session_id}/sources/{document_id}/{revision}/{element_id}/image')
def image(session_id: UUID, document_id: UUID, revision: UUID, element_id: str, user=Depends(require_user)):
    document = authorized(session_id, document_id, revision, user)
    with extraction(document) as archive:
        record = element(archive, element_id)
        data, mime = image_bytes(archive, record)
    return Response(data, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/{session_id}/sources/{document_id}/{revision}/{element_id}/original')
def original(session_id: UUID, document_id: UUID, revision: UUID, element_id: str, user=Depends(require_user)):
    document = authorized(session_id, document_id, revision, user)
    if not original_download_allowed(document, user):
        raise HTTPException(403, 'Original-source download is not enabled for this document. Ask an administrator to review the source.')
    with extraction(document) as archive:
        element(archive, element_id)
    return original_link(document)


def original_link(document):
    # Short-lived access is minted only after the account/scope/revision checks.
    signed = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).create_signed_url(document['storage_path'], 300)
    return JSONResponse({'url': signed['signedURL'], 'expires_in': 300}, headers={'Cache-Control': 'no-store'})


@router.get('/{session_id}/sources/{document_id}/{revision}/original')
def manual_original(session_id: UUID, document_id: UUID, revision: UUID, user=Depends(require_user)):
    document = authorized(session_id, document_id, revision, user)
    if not original_download_allowed(document, user):
        raise HTTPException(403, 'Original-source download is not enabled for this document. Ask an administrator to review the source.')
    return original_link(document)
