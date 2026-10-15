"""Resolve revision-bound chat evidence from the private extraction archive."""
from io import BytesIO
from contextlib import ExitStack
import json
from zipfile import ZipFile

from fastapi import HTTPException
from backend import db, settings
from backend.source_elements import FORMAT_VERSION, public_element, image_path, sanitize_table


def extraction(document):
    data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(document['extraction_storage_path'])
    if len(data) > settings.EXTRACTION_MAX_BYTES:
        raise HTTPException(413, 'Extraction exceeds the configured limit.')
    archive = ZipFile(BytesIO(data))
    if sum(e.file_size for e in archive.infolist()) > settings.EXTRACTION_MAX_BYTES:
        archive.close()
        raise HTTPException(413, 'Extraction exceeds the configured limit.')
    try:
        manifest = json.loads(archive.read('manifest.json'))
    except Exception:
        archive.close()
        raise
    if (manifest.get('format_version') != FORMAT_VERSION or manifest.get('document_id') != document['id']
            or manifest.get('source_revision') != document['source_revision']):
        archive.close()
        raise HTTPException(409, 'Reprocess this source to enable attachments.')
    return archive


def element(archive, identity):
    manifest = json.loads(archive.read('elements.json'))
    if manifest.get('format_version') != FORMAT_VERSION:
        raise HTTPException(409, 'Source format is incompatible.')
    record = next((e for e in manifest['elements'] if e['element_id'] == identity), None)
    if record is None:
        raise HTTPException(404, 'Source element not found.')
    return record


def attachments(descriptors, scope, session_id):
    documents = {m['document_id']: m for m in scope['document_metadata'].values()}
    result = []
    if len(descriptors) > 5:
        raise ValueError('Too many source attachments')
    with ExitStack() as resources:
        loaded = {}
        for descriptor in descriptors:
            identity = descriptor.get('document_id')
            allowed = documents.get(identity)
            if not allowed or descriptor.get('source_revision') != allowed['index_revision']:
                raise ValueError('Attachment revision is outside the resolved scope')
            if identity not in loaded:
                document = db.get('documents', identity)
                if document['source_revision'] != allowed['index_revision']:
                    raise HTTPException(409, 'The attachment source changed. Retry the question.')
                loaded[identity] = (document, resources.enter_context(extraction(document)))
            document, archive = loaded[identity]
            record = element(archive, descriptor.get('element_id'))
            if record['kind'] != descriptor.get('kind'):
                raise ValueError('Attachment kind does not match the source')
            item = public_element(record)
            if record['kind'] == 'image':
                item['asset_available'] = image_path(record['asset_path']) in archive.namelist()
            if record['kind'] == 'table':
                if record.get('visual_asset_path'):
                    item['asset_available'] = image_path(record['visual_asset_path']) in archive.namelist()
                item['html'] = sanitize_table(item['html'])
                if len(item['html']) > 1000000:
                    item['html'] = ''
                    item['cells'] = []
                    item['structure_valid'] = False
            base = f"/chat/sessions/{session_id}/sources/{identity}/{document['source_revision']}/{record['element_id']}"
            item.update(document_id=identity, source_revision=document['source_revision'],
                        document_title=document['name'], source_fidelity_verified=allowed['source_fidelity_verified'],
                        source_endpoint=base + '/original')
            if record['kind'] == 'image' or record.get('visual_asset_path'):
                item['asset_endpoint'] = base + '/image'
            result.append(item)
    return result
