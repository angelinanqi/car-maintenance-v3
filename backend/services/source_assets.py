"""Resolve revision-bound chat evidence from the private extraction archive."""
from io import BytesIO
from hashlib import sha256
from contextlib import ExitStack
from functools import lru_cache
import json
from zipfile import ZipFile

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from backend import db, settings
from shared.source_elements import FORMAT_VERSION, public_element, image_path, sanitize_table
from shared.visual_identity import source_image_available
from shared.source_pages import page_assets, element_page, table_page_parts


def table_pages(archive, record):
    """Resolve originals from this revision's evidence, never caller-supplied paths."""
    if record['kind'] != 'table':
        return []
    manifest = json.loads(archive.read('elements.json'))
    assets = page_assets(manifest)
    roles = {}
    for part, role in table_page_parts(record, manifest['elements']):
        number = element_page(part)
        if number is not None:
            roles.setdefault(number, role)
    return [{'page': number, 'role': role, 'asset': assets.get(number)}
            for number, role in sorted(roles.items())]


def table_page_bytes(archive, record, number):
    page = next((page for page in table_pages(archive, record) if page['page'] == number), None)
    if not page or not page['asset']:
        raise HTTPException(404, 'Original table page is unavailable.')
    return image_bytes(archive, {'kind': 'image', **page['asset']})


def image_bytes(archive, record):
    reference = record.get('asset_path') if record['kind'] == 'image' else record.get('visual_asset_path')
    if not reference:
        raise HTTPException(404, 'Image not found.')
    path = image_path(reference)
    if path not in archive.namelist():
        raise HTTPException(404, 'Image asset is missing.')
    if archive.getinfo(path).file_size > settings.IMAGE_MAX_BYTES:
        raise HTTPException(413, 'Image exceeds the configured limit.')
    data = archive.read(path)
    if record.get('asset_sha256') and sha256(data).hexdigest() != record['asset_sha256']:
        raise HTTPException(409, 'Source image does not match its recorded identity.')
    try:
        with Image.open(BytesIO(data)) as source:
            source.verify()
            mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp', 'GIF': 'image/gif'}.get(source.format)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(422, 'Invalid source image.') from None
    if not mime:
        raise HTTPException(415, 'Unsupported source image.')
    return data, mime


@lru_cache(maxsize=2)
def extraction_data(document_id, revision, storage_path):
    """Keep two validated archives warm; callers still authorize every request."""
    data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(storage_path)
    if len(data) > settings.EXTRACTION_MAX_BYTES:
        raise HTTPException(413, 'Extraction exceeds the configured limit.')
    with ZipFile(BytesIO(data)) as archive:
        if sum(e.file_size for e in archive.infolist()) > settings.EXTRACTION_MAX_BYTES:
            raise HTTPException(413, 'Extraction exceeds the configured limit.')
        manifest = json.loads(archive.read('manifest.json'))
    if (manifest.get('format_version') != FORMAT_VERSION or manifest.get('document_id') != document_id
            or manifest.get('source_revision') != revision):
        raise HTTPException(409, 'Reprocess this source to enable attachments.')
    return data


def extraction(document):
    path = document.get('extraction_storage_path')
    if not path:
        raise HTTPException(409, 'Prepare this document before opening its extracted sources.')
    data = extraction_data(document['id'], document['source_revision'], path)
    return ZipFile(BytesIO(data))


def element(archive, identity):
    manifest = json.loads(archive.read('elements.json'))
    if manifest.get('format_version') != FORMAT_VERSION:
        raise HTTPException(409, 'Source format is incompatible.')
    record = next((e for e in manifest['elements'] if e['element_id'] == identity), None)
    if record is None:
        raise HTTPException(404, 'Source element not found.')
    return record


def original_download_allowed(document, user):
    if document.get('source_kind') == 'learning_guide':
        return False
    return user.get('role') == 'admin' or bool(document.get('published') and document.get('mobile_visible'))


def source_document(identity, metadata):
    if metadata.get('source_type') == 'learning_guide':
        from backend.services.guide_indexing import source_document as guide_document
        return guide_document(identity)
    return db.get('documents', identity)


def resolve_manual_sources(sources, scope, session_id, user, *, browse=False):
    """Attach protected document links; browse choices are not answer evidence."""
    allowed = {m['document_id']: m for m in scope['document_metadata'].values()}
    loaded = {}

    def link(metadata):
        identity = metadata['document_id']
        if identity not in loaded:
            loaded[identity] = source_document(identity, metadata)
        document = loaded[identity]
        if document['source_revision'] != metadata['index_revision']:
            raise HTTPException(409, 'The manual source changed. Retry the question.')
        result = {'document_id': identity, 'source_revision': document['source_revision'],
                  'document_title': document['name']}
        if document.get('source_metadata') or document.get('source_type') == 'md' or document.get('original_filename', '').startswith('website-'):
            with extraction(document) as archive:
                article = json.loads(archive.read('metadata/article.json')) if 'metadata/article.json' in archive.namelist() else None
            if article:
                result.update(source_kind='website', title=article['article_title'],
                              original_url=article['original_url'], retrieved_at=article['retrieved_at'])
        if original_download_allowed(document, user):
            result['source_endpoint'] = (
                f"/chat/sessions/{session_id}/sources/{identity}/{document['source_revision']}/original")
        return result

    resolved = []
    for source in sources:
        if source.get('source_type') != 'manual':
            resolved.append(source)
            continue
        metadata = allowed.get(source.get('document_id'))
        if not metadata or source.get('source_revision') != metadata['index_revision']:
            raise ValueError('Citation revision is outside the resolved scope')
        # A text chunk currently has no established PDF page mapping. Do not
        # borrow a page from an adjacent image or accept a guessed page/URL.
        item = {key: source[key] for key in ('label', 'source_type', 'chunk_id', 'section_path') if key in source}
        item.update(link(metadata))
        resolved.append(item)
    manuals = []
    if browse:
        for metadata in allowed.values():
            # Indexed guides share the retrieval pool but are not documents
            # with original manual downloads (especially emergency protocols).
            if metadata.get('source_type', 'manual') != 'manual':
                continue
            item = link(metadata)
            if item.get('source_endpoint'):
                manuals.append(item)
    return resolved, manuals


def attachments(descriptors, scope, session_id):
    documents = {m['document_id']: m for m in scope['document_metadata'].values()}
    result = []
    shown_pages = set()
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
                document = source_document(identity, allowed)
                if document['source_revision'] != allowed['index_revision']:
                    raise HTTPException(409, 'The attachment source changed. Retry the question.')
                loaded[identity] = (document, resources.enter_context(extraction(document)))
            document, archive = loaded[identity]
            record = element(archive, descriptor.get('element_id'))
            if record['kind'] != descriptor.get('kind'):
                raise ValueError('Attachment kind does not match the source')
            if record['kind'] == 'image' and not source_image_available(record):
                continue
            if record['kind'] == 'image':
                image_bytes(archive, record)
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
            if record['kind'] == 'table':
                item['page_previews'] = []
                for page in table_pages(archive, record):
                    key = (identity, document['source_revision'], page['page'])
                    if key in shown_pages:
                        continue
                    shown_pages.add(key)
                    item['page_previews'].append({
                        'page': page['page'], 'role': page['role'],
                        'asset_available': bool(page['asset'] and page['asset']['asset_path'] in archive.namelist()),
                        'asset_endpoint': f"{base}/pages/{page['page']}/image"})
            item.update(document_id=identity, source_revision=document['source_revision'],
                        reference_label=descriptor.get('reference_label'),
                        document_title=document['name'], source_fidelity_verified=allowed['source_fidelity_verified'])
            if document.get('source_kind') != 'learning_guide':
                item['source_endpoint'] = base + '/original'
            if record['kind'] == 'image' or record.get('visual_asset_path'):
                item['asset_endpoint'] = base + '/image'
            result.append(item)
    return result
