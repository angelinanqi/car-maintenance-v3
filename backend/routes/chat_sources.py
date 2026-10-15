from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from PIL import Image, UnidentifiedImageError

from backend import db, settings
from backend.routes.mobile import require_user
from backend.services import scopes
from backend.services.chat import enforce_vehicle
from backend.services.source_assets import extraction, element
from backend.source_elements import image_path

router = APIRouter(prefix='/chat/sessions', tags=['Chat source evidence'])


def authorized(session_id, document_id, revision, user):
    session = db.get('chat_sessions', session_id)
    if session.get('user_id') != user['id']:
        raise HTTPException(404, 'Source not found.')
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
        reference = record.get('asset_path') if record['kind'] == 'image' else record.get('visual_asset_path')
        if not reference:
            raise HTTPException(404, 'Image not found.')
        path = image_path(reference)
        if path not in archive.namelist():
            raise HTTPException(404, 'Image asset is missing.')
        if archive.getinfo(path).file_size > settings.IMAGE_MAX_BYTES:
            raise HTTPException(413, 'Image exceeds the configured limit.')
        data = archive.read(path)
    try:
        with Image.open(BytesIO(data)) as source:
            source.verify()
            mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp', 'GIF': 'image/gif'}.get(source.format)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(422, 'Invalid source image.') from None
    if not mime:
        raise HTTPException(415, 'Unsupported source image.')
    return Response(data, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/{session_id}/sources/{document_id}/{revision}/{element_id}/original')
def original(session_id: UUID, document_id: UUID, revision: UUID, element_id: str, user=Depends(require_user)):
    document = authorized(session_id, document_id, revision, user)
    if user.get('role') != 'admin' and not (document.get('published') and document.get('mobile_visible')):
        raise HTTPException(403, 'Original-source download is not enabled for this document. Ask an administrator to review the source.')
    with extraction(document) as archive:
        element(archive, element_id)
    # Short-lived access is minted only after the account/scope/revision checks.
    signed = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).create_signed_url(document['storage_path'], 300)
    return {'url': signed['signedURL'], 'expires_in': 300}
