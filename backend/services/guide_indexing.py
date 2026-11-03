"""Guide handoffs for the existing private document index worker."""
from http.client import HTTPConnection, HTTPSConnection
from hashlib import sha256
from io import BytesIO
import json
import socket
import ssl
from urllib.parse import urljoin, urlsplit
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED
import httpx

from fastapi import HTTPException
from PIL import Image

from backend import db, settings
from backend.locks import content_lock
from shared.guide_index import revision, prepare_html
from shared.public_web import public_url, resolve_public


def index_rows(*, emergency=False):
    return {row['id']: row for row in db.all_rows('emergency_indexes' if emergency else 'guide_indexes')}


def content_revision(guide, emergency=False):
    if emergency:
        from shared.emergency_index import revision as emergency_revision
        return emergency_revision(guide)
    return revision(guide)


def eligible(guide, emergency=False):
    if emergency:
        from shared.emergency_index import eligible as emergency_eligible
        return emergency_eligible(guide)
    return guide['status'] == 'published'


def source_revision(guide, index=None, *, emergency=False):
    digest = content_revision(guide, emergency)
    return index['source_revision'] if index and index.get('content_hash') == digest else digest


def current(guide, index, *, emergency=False):
    return bool(index and index.get('content_hash') == content_revision(guide, emergency)
                and index.get('status') == 'processed' and index.get('chunk_count', 0) > 0)


def handoff(guide, index=None, *, category_published=True, emergency=False):
    available = eligible(guide, emergency) and category_published
    return dict(id=guide['id'], name=guide['title'], source_kind='emergency_protocol' if emergency else 'learning_guide', source_type='html',
                source_revision=source_revision(guide, index, emergency=emergency), revision=guide['updated_at'],
                status=('processed' if current(guide, index, emergency=emergency) else 'awaiting_index') if available else 'draft',
                chunk_count=index.get('chunk_count', 0) if current(guide, index, emergency=emergency) else 0,
                source_fidelity_verified=False)


def source_document(identity):
    guide = db.get('guides', identity)
    indexes = db.all_rows('guide_indexes', id=str(identity))
    index = indexes[0] if indexes else None
    if guide['status'] != 'published' or not current(guide, index):
        raise HTTPException(404, 'This guide revision is no longer indexed.')
    if guide.get('category_id') and not db.get('guide_categories', guide['category_id']).get('published'):
        raise HTTPException(404, 'This learning category is no longer published.')
    return dict(id=guide['id'], name=guide['title'], source_revision=index['source_revision'],
                extraction_storage_path=index['extraction_storage_path'], source_type='html',
                source_kind='learning_guide', published=True, mobile_visible=False)


def download_image(url):
    """Bound public fetches, pinning the validated address through TLS and redirects."""
    for _ in range(4):
        url = public_url(url)
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = resolve_public(parsed.hostname, port)
        connection = (HTTPSConnection if parsed.scheme == 'https' else HTTPConnection)(
            parsed.hostname, port, timeout=20)
        raw = socket.create_connection((addresses[0][4][0], port), timeout=20)
        try:
            connection.sock = (ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
                               if parsed.scheme == 'https' else raw)
            target = parsed.path + ('?' + parsed.query if parsed.query else '')
            connection.request('GET', target, headers={'Accept': 'image/*', 'User-Agent': 'Roadie-guide-indexer'})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.getheader('Location') or '')
                continue
            if response.status != 200:
                raise ValueError('Image download failed')
            data = response.read(settings.IMAGE_MAX_BYTES + 1)
            if len(data) > settings.IMAGE_MAX_BYTES:
                raise ValueError('Image exceeds the configured limit')
            return data
        finally:
            connection.close()
            raw.close()
    raise ValueError('Too many image redirects')


def prepare(guide, expected_revision, *, emergency=False):
    table = 'emergency_indexes' if emergency else 'guide_indexes'
    parent_table = 'emergency_playbooks' if emergency else 'guides'
    prefix = 'emergency' if emergency else 'guides'
    rows = db.all_rows(table, id=guide['id'])
    index = rows[0] if rows else None
    if str(expected_revision) != source_revision(guide, index, emergency=emergency) or not eligible(guide, emergency):
        raise HTTPException(409, 'This guide revision is no longer available.')
    if index and index.get('content_hash') == content_revision(guide, emergency) and index.get('extraction_storage_path'):
        return db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(index['extraction_storage_path'])

    uploaded = [] if emergency else db.all_rows('guide_images', guide_id=guide['id'])
    bucket = db.bucket(settings.SUPABASE_CONTENT_BUCKET)
    known = {bucket.get_public_url(image['storage_path']): image['storage_path'] for image in uploaded}
    images, descriptions = {}, {}
    total_bytes = 0

    def load_image(url):
        nonlocal total_bytes
        if url in images:
            return images[url]
        if len(images) >= 100:
            raise ValueError('Too many images in one guide')
        data = bucket.download(known[url]) if url in known else download_image(url)
        if len(data) > settings.IMAGE_MAX_BYTES:
            raise ValueError('Image exceeds the configured limit')
        with Image.open(BytesIO(data)) as image:
            image.verify()
            if image.format not in {'PNG', 'JPEG', 'WEBP', 'GIF'}:
                raise ValueError('Unsupported image')
        total_bytes += len(data)
        if total_bytes > settings.EXTRACTION_MAX_BYTES:
            raise ValueError('Guide assets exceed the extraction limit')
        images[url] = data
        return data

    def describe_image(data):
        digest = sha256(data).hexdigest()
        if digest in descriptions:
            return descriptions[digest]
        if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
            raise ValueError('The private RAG service is not configured')
        response = httpx.post(settings.RAG_SERVICE_URL + '/v1/visual-description',
            headers={'Authorization': 'Bearer ' + settings.RAG_SERVICE_TOKEN},
            files={'original': ('image.png', data, 'application/octet-stream')}, timeout=120)
        response.raise_for_status()
        descriptions[digest] = response.json()
        return descriptions[digest]

    if emergency:
        from shared.emergency_index import prepare_html as prepare_emergency
        html, manifest, assets, media, videos, warnings = prepare_emergency(guide)
    else:
        html, manifest, assets, media, videos, warnings = prepare_html(guide, load_image, describe_image=describe_image)
    manifest['source_revision'] = str(expected_revision)
    manifest['guide_videos'] = videos
    data = BytesIO()
    with ZipFile(data, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(dict(format_version=manifest['format_version'],
            document_id=guide['id'], source_revision=str(expected_revision), markdown='document.html')))
        archive.writestr('document.html', html)
        archive.writestr('elements.json', json.dumps(manifest, ensure_ascii=False))
        for asset_path, image in assets.items():
            archive.writestr(asset_path, image)
    if len(data.getvalue()) > settings.EXTRACTION_MAX_BYTES:
        raise HTTPException(413, 'Guide extraction exceeds the configured limit.')
    storage_path = f'{prefix}/{guide["id"]}/{expected_revision}/extraction.zip'
    with content_lock(('playbook:' if emergency else 'guide:') + guide['id']):
        latest = db.get(parent_table, guide['id'])
        latest_rows = db.all_rows(table, id=guide['id'])
        latest_index = latest_rows[0] if latest_rows else None
        if (not eligible(latest, emergency) or content_revision(latest, emergency) != content_revision(guide, emergency)
                or source_revision(latest, latest_index, emergency=emergency) != str(expected_revision)):
            raise HTTPException(409, 'The guide changed during processing.')
        db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).upload(storage_path, data.getvalue(),
            {'content-type': 'application/zip', 'upsert': 'true'})
        db.client().table(table).upsert(dict(id=guide['id'], content_hash=content_revision(guide, emergency),
            source_revision=str(expected_revision), status='awaiting_index', chunk_count=0,
            extraction_storage_path=storage_path, media=media, videos=videos, warnings=warnings,
            error=None)).execute()
        if index and index.get('extraction_storage_path') and index['extraction_storage_path'] != storage_path:
            db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove([index['extraction_storage_path']])
    return data.getvalue()


def retry(guide):
    # A new revision also invalidates the worker's cached result, even if the URL is unchanged.
    values = dict(id=guide['id'], content_hash=revision(guide), source_revision=str(uuid4()),
                  status='awaiting_index', chunk_count=0, extraction_storage_path=None,
                  media=[], videos=[], warnings=[], error=None)
    previous = db.all_rows('guide_indexes', id=guide['id'])
    db.client().table('guide_indexes').upsert(values).execute()
    if previous and previous[0].get('extraction_storage_path'):
        db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove([previous[0]['extraction_storage_path']])
    return {'status': 'awaiting_index'}
