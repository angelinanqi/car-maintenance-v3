"""Consume FastAPI extractions using the existing pipeline, without changing it.

Run separately from chat: python -m rag.index_worker [--once].
Only versioned documents recorded in this worker's ledger are reconciled.
"""
import argparse
from io import BytesIO
import json
import logging
import os
from pathlib import Path, PurePosixPath
import tempfile
import time
from uuid import UUID
from zipfile import ZipFile

import httpx
from rag.config import settings
from backend.source_elements import FORMAT_VERSION

logger = logging.getLogger(__name__)
MAX_EXTRACTION_BYTES = int(os.getenv('EXTRACTION_MAX_BYTES') or '209715200')
if MAX_EXTRACTION_BYTES <= 0:
    raise ValueError('EXTRACTION_MAX_BYTES must be positive')


def index_name(document_id, revision):
    return f'{UUID(document_id)}_{UUID(revision)}'


def unpack(data, document, destination):
    """Validate exact revision, archive paths and total size before extracting."""
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_EXTRACTION_BYTES:
            raise ValueError('Extraction archive exceeds configured limits')
        names = set()
        for entry in entries:
            raw_name = entry.orig_filename
            path = PurePosixPath(raw_name)
            if (path.is_absolute() or '..' in path.parts or '\\' in raw_name or ':' in raw_name
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000 or entry.filename in names):
                raise ValueError('Unsafe extraction archive member')
            names.add(entry.filename)
        if not {'manifest.json', 'document.md', 'elements.json'} <= names:
            raise ValueError('Extraction is incomplete. Reprocess the document through the backend.')
        manifest = json.loads(archive.read('manifest.json'))
        if (manifest.get('format_version') != FORMAT_VERSION or manifest.get('document_id') != document['id']
                or manifest.get('source_revision') != document['source_revision']
                or manifest.get('markdown') != 'document.md'):
            raise ValueError('Extraction manifest does not match this document revision')
        for entry in entries:
            if entry.is_dir():
                continue
            if entry.filename not in {'manifest.json', 'document.md', 'elements.json'} and not entry.filename.startswith(('images/', 'metadata/')):
                raise ValueError('Unexpected extraction archive member')
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
    source = destination / (index_name(document['id'], document['source_revision']) + '.md')
    (destination / 'document.md').rename(source)
    return source


def list_documents(client):
    rows = []
    while True:
        response = client.get('/internal/indexing/documents', params={'pending_only': 'false', 'offset': len(rows), 'limit': 100})
        response.raise_for_status()
        page = response.json()
        rows.extend(page)
        if len(page) < 100:
            return rows


def write_ledger(path, ledger):
    staged = path.with_suffix('.tmp')
    staged.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    staged.replace(path)


def run_once(client, work_dir):
    from rag.pipeline import run_pipeline
    from rag.app.embedding.vector_store import VectorStore
    work_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = work_dir / 'managed_indexes.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}
    documents = list_documents(client)  # Never reconcile on a failed/partial catalogue fetch.
    store = VectorStore()
    failures = []
    for document in documents:
        if document['status'] != 'awaiting_index' or document.get('superseded_by_id'):
            continue
        name = index_name(document['id'], document['source_revision'])
        try:
            indexed = store.collection.get(where={'document_name': name}, include=['metadatas'])
            source_path = settings.OUTPUT_DIR / 'sources' / f'{name}.json'
            source_manifest = {}
            if source_path.is_file():
                try:
                    source_manifest = json.loads(source_path.read_text(encoding='utf-8'))
                except (ValueError, UnicodeError):
                    pass  # An interrupted/corrupt manifest must be rebuilt.
            if not isinstance(source_manifest, dict):
                source_manifest = {}
            ready = (source_manifest.get('format_version') == FORMAT_VERSION
                     and source_manifest.get('document_id') == document['id']
                     and source_manifest.get('source_revision') == document['source_revision']
                     and bool(indexed['ids']) and ledger.get(name, {}).get('format_version') == FORMAT_VERSION and ledger.get(name, {}).get('complete')
                     and len(indexed['ids']) == ledger[name].get('chunk_count') and
                     all(m.get('document_id') == document['id'] and m.get('format_version') == FORMAT_VERSION
                         and m.get('index_revision') == document['source_revision'] for m in indexed['metadatas']))
            if not ready:
                response = client.get(f"/internal/indexing/documents/{document['id']}/extraction",
                                      params={'source_revision': document['source_revision']})
                response.raise_for_status()
                if len(response.content) > MAX_EXTRACTION_BYTES:
                    raise ValueError('Extraction download exceeds configured limits')
                # Record ownership before any write so an interrupted index is also reconciled.
                ledger[name] = {'document_id': document['id'], 'revision': document['source_revision'], 'complete': False}
                write_ledger(ledger_path, ledger)
                with tempfile.TemporaryDirectory(dir=work_dir) as directory:
                    source = unpack(response.content, document, Path(directory))
                    result = run_pipeline(source, settings.OUTPUT_DIR, settings.CHROMA_PATH,
                        metadata={'document_id': document['id'], 'index_revision': document['source_revision'],
                                  'document_title': document['name'],
                                  'source_fidelity_verified': document.get('source_fidelity_verified', False)})
                    count = result['documents'][0]['chunks']
                if count < 1:
                    raise ValueError('The pipeline produced no indexable chunks')
                ledger[name]['complete'] = True
                ledger[name]['format_version'] = FORMAT_VERSION
                ledger[name]['chunk_count'] = count
                write_ledger(ledger_path, ledger)
            else:
                count = len(indexed['ids'])
            response = client.post(f"/internal/indexing/documents/{document['id']}/result", json={
                'source_revision': document['source_revision'], 'status': 'indexed', 'chunk_count': count})
            response.raise_for_status()
            logger.info('Indexed %s: %d chunks', name, count)
        except Exception as error:
            failures.append(name)
            logger.exception('Index handoff failed for %s', name)
            try:
                response = client.post(f"/internal/indexing/documents/{document['id']}/result", json={
                    'source_revision': document['source_revision'], 'status': 'failed',
                    'error': f'{type(error).__name__}: {error}'[:2000]})
                response.raise_for_status()
            except httpx.HTTPError:
                logger.warning('Failure acknowledgement unavailable or stale; retry on next poll')
    # Fetch again so a replacement/deletion during embedding cannot preserve stale vectors.
    current = list_documents(client)
    keep = {index_name(d['id'], d['source_revision']) for d in current
            if d['status'] in {'awaiting_index', 'processed'} and not d.get('superseded_by_id')}
    for name in list(ledger):
        # Validate ledger identifiers before using them to delete worker-owned vectors.
        entry = ledger[name]
        if name != index_name(entry['document_id'], entry['revision']):
            raise ValueError('Invalid managed-index ledger entry')
        if name not in keep:
            store.collection.delete(where={'document_name': name})
            # Remove worker-owned source text as well as vectors and manifests.
            # The validated ledger name cannot target an unmanaged document.
            for directory, suffix in (
                ('sources', '.json'), ('sources', '.tmp'),
                ('cleaning', '.md'), ('parse', '.html'),
                ('parse', '_html_tree.json'), ('nodes', '_html_tree.json'),
                ('chunks', '.json'),
            ):
                (settings.OUTPUT_DIR / directory / f'{name}{suffix}').unlink(missing_ok=True)
            del ledger[name]
    write_ledger(ledger_path, ledger)
    if failures:
        raise RuntimeError(f'{len(failures)} document handoffs failed; see per-document logs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    token = os.getenv('RAG_SERVICE_TOKEN', '')
    if len(token.encode()) < 32:
        raise ValueError('Configure RAG_SERVICE_TOKEN with at least 32 bytes')
    url = os.getenv('RAG_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')
    interval = float(os.getenv('RAG_INDEX_POLL_SECONDS', '15'))
    if not 0 < interval < float('inf'):
        raise ValueError('RAG_INDEX_POLL_SECONDS must be finite and positive')
    work_dir = settings.path_setting('RAG_INDEX_WORK_DIR', str(settings.OUTPUT_DIR / 'index-worker'))
    logging.basicConfig(level=logging.INFO)
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + token},
                      timeout=settings.SUPABASE_TIMEOUT, follow_redirects=False) as client:
        while True:
            try:
                run_once(client, work_dir)
            except Exception:
                logger.exception('Index worker pass failed; see logs for acknowledgement/reconciliation results')
                if args.once:
                    raise
            if args.once:
                break
            time.sleep(interval)


if __name__ == '__main__':
    main()
