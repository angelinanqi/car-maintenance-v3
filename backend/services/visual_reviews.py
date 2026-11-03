"""Save an illustration review batch without rerunning preparation or indexing."""
from hashlib import sha256
import json

from fastapi import HTTPException

from backend import db, settings
from backend.services import documents
from backend.services.source_assets import extraction, image_bytes
from shared.visual_identity import apply_reviews


def save(document_id, request, reviewer):
    with documents.document_lock('schedule-sources'), documents.document_lock(document_id):
        row = documents.editable(document_id)
        if row['source_revision'] != str(request.source_revision):
            raise HTTPException(409, 'The source changed. Reload before saving image reviews.')
        if row.get('published') or row.get('superseded_by_id'):
            raise HTTPException(409, 'Unpublish this document or stage a replacement before changing image identities.')
        if row.get('status') not in {'processed', 'awaiting_confirmation', 'awaiting_index'} or not row.get('extraction_storage_path'):
            raise HTTPException(409, 'Prepare this document before reviewing its images.')
        source = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(row['storage_path'])
        with extraction(row) as archive:
            manifest = json.loads(archive.read('elements.json'))
            assets = {e['asset_sha256']: e['identity_review'] for e in manifest['elements']
                      if e.get('asset_sha256') and e.get('identity_review')}
            for review in request.reviews:
                record = next((item for item in manifest['elements'] if item['element_id'] == review.element_id), None)
                if record is None:
                    raise HTTPException(404, 'This illustration is no longer available in the extraction.')
                if record['kind'] != 'image':
                    raise HTTPException(422, 'Review an image identity, not a table or paragraph.')
                data, _ = image_bytes(archive, record)
                digest = sha256(data).hexdigest()
                record['asset_sha256'] = digest
                record['asset_available'] = True
                if review.approved:
                    if not review.title.strip():
                        raise HTTPException(422, 'A reviewed image needs an identifying title.')
                    assets[digest] = {'title': review.title, 'description': review.description,
                                     'uncertainty': review.uncertainty,
                                     'reviewed_by': reviewer['user']['id'], 'reviewed_at': documents.now()}
                else:
                    assets.pop(digest, None)
        from backend.services import extraction_corrections
        files = extraction_corrections.read_bundle(row)
        # Keep prepared text, corrected tables and original image bytes intact.
        # Reapply the complete hash-bound review set, including removed approvals.
        files.setdefault('metadata/original-elements.json', files['elements.json'])
        for record in manifest['elements']:
            record.pop('identity_review', None)
        apply_reviews(manifest, assets)
        files['elements.json'] = json.dumps(manifest, ensure_ascii=False).encode()
        files['metadata/visual-reviews.json'] = json.dumps({
            'source_sha256': sha256(source).hexdigest(), 'assets': assets}).encode()
        return extraction_corrections.commit(row, files, defer_indexing=True)
