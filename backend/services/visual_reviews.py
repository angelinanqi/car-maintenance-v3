"""Review original image identity, then reuse the existing revision/index workflow."""
from hashlib import sha256
import json

from fastapi import HTTPException

from backend import db, settings
from backend.services import documents
from backend.services.source_assets import extraction, element, image_bytes


def save(document_id, request, reviewer):
    with documents.document_lock(document_id):
        row = documents.editable(document_id)
        if row['source_revision'] != str(request.source_revision):
            raise HTTPException(409, 'The source changed. Reload before saving image reviews.')
        if row.get('published'):
            raise HTTPException(409, 'Unpublish this document or stage a replacement before changing image identities.')
        if row.get('status') not in {'processed', 'awaiting_index'} or not row.get('extraction_storage_path'):
            raise HTTPException(409, 'Prepare this document before reviewing its images.')
        source = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(row['storage_path'])
        with extraction(row) as archive:
            manifest = json.loads(archive.read('elements.json'))
            assets = {e['asset_sha256']: e['identity_review'] for e in manifest['elements']
                      if e.get('asset_sha256') and e.get('identity_review')}
            for review in request.reviews:
                record = element(archive, review.element_id)
                if record['kind'] != 'image':
                    raise HTTPException(422, 'Review an image identity, not a table or paragraph.')
                data, _ = image_bytes(archive, record)
                digest = sha256(data).hexdigest()
                if review.approved:
                    if not review.title.strip():
                        raise HTTPException(422, 'A reviewed image needs an identifying title.')
                    assets[digest] = {'title': review.title, 'description': review.description,
                                     'uncertainty': review.uncertainty,
                                     'reviewed_by': reviewer['id'], 'reviewed_at': documents.now()}
                else:
                    assets.pop(digest, None)
        directory = documents.work_directory(document_id)
        directory.mkdir(parents=True, exist_ok=True)
        staged = directory / 'visual-reviews.tmp'
        staged.write_text(json.dumps({'source_sha256': sha256(source).hexdigest(), 'assets': assets}), encoding='utf-8')
        staged.replace(directory / 'visual-reviews.json')
        values = documents.reset_processing()
        values.update(status='processing', processing_started_at=documents.now())
        return db.update('documents', document_id, values)
