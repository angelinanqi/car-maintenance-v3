"""Consume FastAPI extractions using the existing pipeline, without changing it.

Run embedded in the RAG API or separately: python -m rag.index_worker [--once].
Only versioned documents recorded in this worker's ledger are reconciled.
"""
import argparse
from io import BytesIO
import json
import logging
import os
import shutil
from pathlib import Path, PurePosixPath
import tempfile
from threading import Event, Thread
from uuid import UUID
from zipfile import ZipFile

import httpx
from rag.config import settings
from shared.source_elements import FORMAT_VERSION
from shared.observability import observed, span

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
        required = {'manifest.json', 'elements.json',
                    'document.html' if document.get('source_kind') in {'learning_guide', 'emergency_protocol'} else 'document.md'}
        if not required <= names:
            raise ValueError('Extraction is incomplete. Reprocess the document through the backend.')
        manifest = json.loads(archive.read('manifest.json'))
        if (manifest.get('format_version') != FORMAT_VERSION or manifest.get('document_id') != document['id']
                or manifest.get('source_revision') != document['source_revision']):
            raise ValueError('Extraction manifest does not match this document revision')
        processing = manifest.get('markdown')
        allowed_sources = {'document.html'} if document.get('source_kind') in {'learning_guide', 'emergency_protocol'} else {'document.md', 'metadata/processing.md'}
        if (not isinstance(processing, str) or processing not in allowed_sources
                or processing not in names):
            raise ValueError('Invalid processing Markdown in extraction manifest')
        for entry in entries:
            if entry.is_dir():
                continue
            if entry.filename not in {'manifest.json', 'document.md', 'document.html', 'elements.json'} and not entry.filename.startswith(('images/', 'metadata/')):
                raise ValueError('Unexpected extraction archive member')
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
    source = destination / (index_name(document['id'], document['source_revision']) + ('.html' if processing == 'document.html' else '.md'))
    # A derived structure copy may be supplied by packaging. Keep the original
    # extraction untouched; elements.json was built from this same copy.
    (destination / processing).rename(source)
    return source


@observed('index_catalogue_fetch')
def list_documents(client):
    rows = []
    for resource in ('documents', 'guides', 'emergency'):
        offset = 0
        while True:
            response = client.get('/internal/indexing/' + resource,
                                  params={'pending_only': 'false', 'offset': offset, 'limit': 100})
            response.raise_for_status()
            page = response.json()
            rows.extend(page)
            offset += len(page)
            if len(page) < 100:
                break
    return rows


def handoff_url(document):
    kind = {'learning_guide': 'guides', 'emergency_protocol': 'emergency'}.get(document.get('source_kind'), 'documents')
    return f'/internal/indexing/{kind}/{document["id"]}'


def write_ledger(path, ledger):
    staged = path.with_suffix('.tmp')
    staged.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    staged.replace(path)


def run_once(client, work_dir, *, restore_processed=False):
    work_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = work_dir / 'managed_indexes.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}
    documents = list_documents(client)  # Never reconcile on a failed/partial catalogue fetch.
    eligible = {'awaiting_index', 'processed'} if restore_processed else {'awaiting_index'}
    if not ledger and not any((d['status'] in eligible or (
            d.get('source_kind') in {'learning_guide', 'emergency_protocol'} and d['status'] == 'processed'))
            and not d.get('superseded_by_id') for d in documents):
        return  # Empty/idle installations do not initialize Chroma or import model code.
    from rag.pipeline import run_pipeline
    from rag.app.embedding.vector_store import VectorStore
    store = VectorStore()
    try:
        failures = []
        for document in documents:
            if (document['status'] not in eligible and not (
                    document.get('source_kind') in {'learning_guide', 'emergency_protocol'} and document['status'] == 'processed')) or document.get('superseded_by_id'):
                continue
            name = index_name(document['id'], document['source_revision'])
            warnings = []
            try:
                with span('document_index_attempt', module=__name__, job_id=document['id']):
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
                        response = client.get(handoff_url(document) + '/extraction',
                                              params={'source_revision': document['source_revision']},
                                              timeout=300 if document.get('source_kind') in {'learning_guide', 'emergency_protocol'} else settings.SUPABASE_TIMEOUT)
                        response.raise_for_status()
                        if len(response.content) > MAX_EXTRACTION_BYTES:
                            raise ValueError('Extraction download exceeds configured limits')
                        # Record ownership before any write so an interrupted index is also reconciled.
                        ledger[name] = {'document_id': document['id'], 'revision': document['source_revision'], 'complete': False}
                        write_ledger(ledger_path, ledger)
                        with tempfile.TemporaryDirectory(dir=work_dir) as directory:
                            source = unpack(response.content, document, Path(directory))
                            if document.get('source_kind') == 'learning_guide':
                                from rag.app.youtube.pipeline import ingest_guide_videos
                                manifest = json.loads((Path(directory) / 'elements.json').read_text(encoding='utf-8'))
                                try:
                                    warnings = ingest_guide_videos(manifest.get('guide_videos', []))
                                except Exception:
                                    logger.exception('Guide video preparation failed; indexing guide text continues')
                                    warnings = ['Some YouTube videos could not be prepared. Retry preparation to try again.']
                            result = run_pipeline(source, settings.OUTPUT_DIR, settings.CHROMA_PATH,
                                metadata={'document_id': document['id'], 'index_revision': document['source_revision'],
                                          'document_title': document['name'],
                                          'source_fidelity_verified': document.get('source_fidelity_verified', False)})
                            count = result['documents'][0]['chunks']
                        if count < 1:
                            raise ValueError('The pipeline produced no indexable chunks')
                        if document['status'] == 'processed' and count != document.get('chunk_count'):
                            raise ValueError('Restored chunk count differs from the published record. '
                                             'Review this document through the admin reprocessing workflow before using it.')
                        ledger[name]['complete'] = True
                        ledger[name]['format_version'] = FORMAT_VERSION
                        ledger[name]['chunk_count'] = count
                        write_ledger(ledger_path, ledger)
                    else:
                        count = len(indexed['ids'])
                    if document['status'] == 'awaiting_index':
                        response = client.post(handoff_url(document) + '/result', json={
                            'source_revision': document['source_revision'], 'status': 'indexed', 'chunk_count': count,
                            **({'warnings': warnings} if warnings else {})})
                        response.raise_for_status()
                    logger.info('Indexed %s: %d chunks', name, count)
            except Exception as error:
                failures.append(name)
                logger.exception('Index handoff failed for %s', name)
                if document['status'] == 'processed':
                    continue  # A local rebuild must never reset authoritative publication/index records.
                try:
                    response = client.post(handoff_url(document) + '/result', json={
                        'source_revision': document['source_revision'], 'status': 'failed',
                        'error': f'{type(error).__name__}: {error}'[:2000]})
                    response.raise_for_status()
                except httpx.HTTPError:
                    logger.warning('Failure acknowledgement unavailable or stale; retry on next poll')
        # Fetch again so a replacement/deletion during embedding cannot preserve stale vectors.
        current = list_documents(client)
        # Backfill/retry assistance for existing revisions without OCR or embedding.
        # Each artifact is cached; failures remain independent of index acknowledgements.
        for document in current:
            if document['status'] != 'processed' or document.get('superseded_by_id'):
                continue
            if document.get('source_kind') in {'learning_guide', 'emergency_protocol'}:
                continue
            try:
                from shared.maintenance_extraction import prepare_safely
                name = index_name(document['id'], document['source_revision'])
                path = settings.OUTPUT_DIR / 'sources' / f'{name}.json'
                if path.is_file():
                    manifest = json.loads(path.read_text(encoding='utf-8'))
                    if (manifest.get('document_id') != document['id']
                            or manifest.get('source_revision') != document['source_revision']):
                        raise ValueError('Maintenance source revision mismatch')
                    prepare_safely(manifest, settings.OUTPUT_DIR)
            except Exception:
                logger.exception('Maintenance assistance retry failed; indexing is unaffected')
        keep = {index_name(d['id'], d['source_revision']) for d in current
                if d['status'] in {'awaiting_index', 'processed'} and not d.get('superseded_by_id')}
        for name in list(ledger):
            # Validate ledger identifiers before using them to delete worker-owned vectors.
            entry = ledger[name]
            if name != index_name(entry['document_id'], entry['revision']):
                raise ValueError('Invalid managed-index ledger entry')
            if name not in keep:
                assets = (settings.OUTPUT_DIR / 'assets' / name).resolve()
                if assets.parent != (settings.OUTPUT_DIR / 'assets').resolve():
                    raise ValueError('Invalid managed asset directory')
                if assets.exists():
                    shutil.rmtree(assets)
                try:
                    (settings.OUTPUT_DIR / 'maintenance' / f'{name}.json').unlink(missing_ok=True)
                    (settings.OUTPUT_DIR / 'maintenance' / f'{name}.suggestions.json').unlink(missing_ok=True)
                except OSError:
                    logger.warning('Could not remove stale maintenance artifact %s', name)
                store.collection.delete(where={'document_name': name})
                # Remove worker-owned source text as well as vectors and manifests.
                # The validated ledger name cannot target an unmanaged document.
                for directory, suffix in (
                    ('sources', '.json'), ('sources', '.tmp'),
                    ('cleaning', '.md'), ('parse', '.html'),
                    ('cleaning', '.html'),
                    ('cleaning', '.removed_malay.json'),
                    ('parse', '_html_tree.json'), ('nodes', '_html_tree.json'),
                    ('chunks', '.json'),
                ):
                    (settings.OUTPUT_DIR / directory / f'{name}{suffix}').unlink(missing_ok=True)
                del ledger[name]
        write_ledger(ledger_path, ledger)
        if failures:
            raise RuntimeError(f'{len(failures)} document handoffs failed; see per-document logs')
    finally:
        store.client.close()


def worker_loop(stop, *, once=False, restore_processed=False, ready=None):
    from filelock import FileLock
    token = os.getenv('RAG_SERVICE_TOKEN', '')
    if len(token.encode()) < 32:
        raise ValueError('Configure RAG_SERVICE_TOKEN with at least 32 bytes')
    url = os.getenv('RAG_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')
    interval = float(os.getenv('RAG_INDEX_POLL_SECONDS', '15'))
    if not 0 < interval < float('inf'):
        raise ValueError('RAG_INDEX_POLL_SECONDS must be finite and positive')
    work_dir = settings.path_setting('RAG_INDEX_WORK_DIR', str(settings.OUTPUT_DIR / 'index-worker'))
    work_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(str(work_dir / '.worker.lock'), timeout=0), httpx.Client(
            base_url=url, headers={'Authorization': 'Bearer ' + token},
            timeout=settings.SUPABASE_TIMEOUT, follow_redirects=False) as client:
        from shared.observability import ready as monitor_ready
        monitor_ready()
        if ready:
            ready.set()
        while not stop.is_set():
            try:
                run_once(client, work_dir, restore_processed=restore_processed)
            except Exception:
                logger.exception('Index worker pass failed; see logs for acknowledgement/reconciliation results')
                if once:
                    raise
            if once:
                return
            stop.wait(interval)


def start_embedded():
    """One lightweight poller, sharing the RAG process and its cached encoder."""
    stop = Event()
    ready = Event()
    errors = []

    def run():
        try:
            worker_loop(stop, ready=ready)
        except Exception as error:
            errors.append(error)
            ready.set()
            logger.exception('Embedded index worker stopped. Restart RAG after correcting the configuration.')

    thread = Thread(target=run, name='document-indexer', daemon=False)
    thread.start()
    if not ready.wait(timeout=10):
        stop.set()
        raise RuntimeError('Embedded index worker did not initialize')
    if errors:
        thread.join()
        raise RuntimeError('Embedded index worker could not start; check token, paths and duplicate workers') from errors[0]
    return stop, thread


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--restore-processed', action='store_true',
                        help='Rebuild local indexes from stored extractions without changing processed records')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from shared.observability import configure
    configure('index-worker')
    from shared.observability import shutdown
    try:
        worker_loop(Event(), once=args.once, restore_processed=args.restore_processed)
    finally:
        shutdown()


if __name__ == '__main__':
    main()
