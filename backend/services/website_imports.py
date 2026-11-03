"""Durable website capture jobs and idempotent PDF handoff. No request-bound tasks."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
from shared.observability import observed
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from postgrest.exceptions import APIError

from backend import db, settings
from backend.website_renderer import validate_pdf, CaptureError
from shared.public_web import public_url, UnsafeURL
from shared.website_metadata import validate_metadata

logger = logging.getLogger(__name__)
TABLE = 'website_import_jobs'
ACTIVE = {'queued', 'capturing', 'captured', 'storing', 'retry_wait'}


def enabled():
    if not settings.WEBSITE_IMPORT_ENABLED:
        raise HTTPException(503, 'Website PDF capture is disabled. Use direct text import or upload a PDF.')


def rpc(name, **values):
    try:
        return db.client().rpc(name, values).execute().data
    except APIError as error:
        if error.code.startswith('PT') and error.code[2:].isdigit():
            raise HTTPException(int(error.code[2:]), error.message) from None
        if error.code in {'42P01', '42703', 'PGRST202', 'PGRST204', 'PGRST205'}:
            raise HTTPException(503, 'Website imports need the website PDF database migration. See supabase/README.md.') from None
        raise


def public_job(job):
    metadata = job.get('source_metadata') or {}
    return {key: job.get(key) for key in ('id', 'submitted_url', 'status', 'attempt_count',
        'next_attempt_at', 'document_id', 'error_code', 'error', 'created_at', 'updated_at', 'completed_at')} | {
        'title': metadata.get('article_title'), 'warnings': metadata.get('warnings', []),
        'page_count': job.get('page_count'), 'media': job.get('capture_options', {}).get('media', 'screen')}


def submit(user_id, key, url, media='screen', *, manual=False):
    if not manual:
        enabled()
    try:
        url = public_url(url, keep_fragment=True)
    except UnsafeURL as error:
        raise HTTPException(422, str(error)) from None
    if media not in {'screen', 'print'}:
        raise HTTPException(422, 'Choose screen or print layout.')
    options = {'media': media}
    if manual:
        options['manual'] = True
    fingerprint = sha256((url + '\n' + json.dumps(options, sort_keys=True)).encode()).hexdigest()
    return rpc('create_website_import', p_user=str(user_id), p_key=str(key), p_url=url,
               p_url_key=fingerprint, p_options=options)


def job_directory(job):
    return settings.WEBSITE_IMPORT_WORK_DIR / str(UUID(str(job['id'])))


def update(job, token, **values):
    return rpc('update_website_import', p_id=job['id'], p_token=str(token), p_values=values)


@contextmanager
def lease(job, token):
    stop, lost = threading.Event(), threading.Event()
    def maintain():
        last = time.monotonic()
        while not stop.wait(10):
            try:
                if not rpc('heartbeat_website_import', p_id=job['id'], p_token=str(token)):
                    lost.set()
                    return
                last = time.monotonic()
            except Exception:
                logger.warning('Import %s: heartbeat failed; finalization still requires current ownership', job['id'])
                if time.monotonic() - last > 150:
                    lost.set()
                    return
    thread = threading.Thread(target=maintain, daemon=True, name='website-import-lease')
    thread.start()
    try:
        yield lost
    finally:
        stop.set()
        thread.join(timeout=1)


def stop_child(process):
    if process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name == 'nt':
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        process.wait(timeout=5)


@observed('website_pdf_capture', job_arg='job', job_key='id')
def render(job, token, stop, lost):
    directory = job_directory(job) / str(token)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {'url': job['submitted_url'], 'options': job['capture_options'], 'output': str(directory),
        'limits': {'timeout': settings.WEBSITE_CAPTURE_TIMEOUT, 'max_bytes': settings.DOCUMENT_MAX_BYTES,
            'max_pages': settings.WEBSITE_CAPTURE_MAX_PAGES, 'network_bytes': settings.WEBSITE_CAPTURE_NETWORK_BYTES,
            'browser_path': str(settings.PLAYWRIGHT_BROWSERS_PATH)}}
    # Do not inherit Supabase keys, dotenv credentials or application tokens.
    environment = {key: value for key, value in os.environ.items() if key in {
        'PATH', 'HOME', 'TMPDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'LOCALAPPDATA'}}
    log = directory / 'renderer.log'
    with log.open('wb') as errors:
        process = subprocess.Popen([sys.executable, '-m', 'backend.website_renderer'],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors,
            cwd=settings.PROJECT_ROOT, env=environment, start_new_session=os.name != 'nt')
        try:
            process.stdin.write(json.dumps(payload).encode())
            process.stdin.close()
            deadline = time.monotonic() + settings.WEBSITE_CAPTURE_TIMEOUT + 15
            while process.poll() is None:
                if stop.wait(.25) or lost.is_set():
                    return None
                if time.monotonic() > deadline:
                    raise CaptureError('timeout', 'The website exceeded the capture deadline.', True)
            if process.returncode:
                lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
                try:
                    error = json.loads(lines[-1])
                    raise CaptureError(error['code'], error['message'], bool(error.get('retryable')))
                except (ValueError, KeyError, IndexError):
                    raise CaptureError('renderer_crashed', 'The browser stopped unexpectedly. Retry this import.', True) from None
        finally:
            stop_child(process)
    return load_capture(job, directory)


def load_capture(job, directory):
    metadata = validate_metadata(json.loads((directory / 'capture.json').read_text(encoding='utf-8')))
    path = directory / 'capture.pdf'
    if metadata['submitted_url'] != job['submitted_url'] or metadata.get('capture_options') != job['capture_options']:
        raise ValueError('Saved capture belongs to another request')
    if sha256(path.read_bytes()).hexdigest() != metadata['pdf_sha256']:
        raise ValueError('Saved PDF checksum mismatch')
    validate_pdf(path, settings.DOCUMENT_MAX_BYTES, settings.WEBSITE_CAPTURE_MAX_PAGES)
    return path, metadata


def recover_capture(job):
    root = job_directory(job)
    for checkpoint in sorted(root.glob('*/capture.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            return load_capture(job, checkpoint.parent)
        except (OSError, ValueError, CaptureError):
            logger.warning('Import %s: ignoring incomplete local capture', job['id'])
    return None


@observed('website_document_handoff', job_arg='job', job_key='id')
def store_capture(job, token, path, metadata):
    metadata = validate_metadata(metadata)
    count, _ = validate_pdf(path, settings.DOCUMENT_MAX_BYTES, settings.WEBSITE_CAPTURE_MAX_PAGES)
    data = path.read_bytes()
    digest = sha256(data).hexdigest()
    if digest != metadata['pdf_sha256']:
        raise CaptureError('checksum', 'The captured PDF changed before it could be saved.')
    # Immutable artifact per attempt. A stale owner cannot overwrite the PDF
    # chosen by a newer attempt; only the finalization RPC can attach it.
    artifact = f"documents/{job['target_document_id']}/captures/{path.parent.name}.pdf"
    job = update(job, token, status='storing', artifact_path=artifact, artifact_sha256=digest,
                 artifact_size=len(data), page_count=count, source_metadata=metadata)
    from backend.services.documents import retry_connection
    retry_connection(lambda: db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).upload(
        artifact, data, {'content-type': 'application/pdf', 'upsert': 'true'}))
    return rpc('finalize_website_import', p_id=job['id'], p_token=str(token))


def recover_remote(job, token):
    if not job.get('artifact_path'):
        return None
    try:
        data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(job['artifact_path'])
    except Exception as error:
        # Storage exposes a distinct APIError whose status is a string in some versions.
        status = getattr(error, 'status', None) or getattr(error, 'status_code', None)
        if str(status) == '404' or 'not found' in str(error).lower():
            return None
        raise
    if sha256(data).hexdigest() != job['artifact_sha256']:
        raise CaptureError('checksum', 'The saved PDF does not match its capture checkpoint.')
    return rpc('finalize_website_import', p_id=job['id'], p_token=str(token))


def fail(job, token, error):
    retryable = isinstance(error, (httpx.TransportError, OSError)) or getattr(error, 'retryable', False)
    if isinstance(error, httpx.HTTPStatusError):
        retryable = error.response.status_code == 429 or error.response.status_code >= 500
    status = str(getattr(error, 'status', None) or getattr(error, 'status_code', None))
    if status == '429' or (status.isdigit() and int(status) >= 500):
        retryable = True
    if isinstance(error, APIError) and error.code in {'PGRST000', 'PGRST001', 'PGRST002', '57014', '53300', '57P01'}:
        retryable = True
    retry = retryable and job['attempt_count'] < 3
    delay = 15 * 2 ** max(0, job['attempt_count'] - 1)
    values = {'status': 'retry_wait' if retry else 'failed',
              'error_code': getattr(error, 'code', 'dependency_error'),
              'error': str(error)[:1500] if isinstance(error, CaptureError) else 'A required service was unavailable. Retry this import.',
              'next_attempt_at': (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()}
    try:
        update(job, token, **values)
    except Exception:
        # Lease expiry makes a persisted in-flight job recoverable even when the
        # failure acknowledgement itself is interrupted.
        logger.exception('Import %s: could not save failure state', job['id'])


def run_once(stop):
    token = uuid4()
    job = rpc('claim_website_import', p_token=str(token))
    if not job:
        return False
    logger.info('Import %s: starting attempt %s', job['id'], job['attempt_count'])
    with lease(job, token) as lost:
        try:
            if recover_remote(job, token):
                return True
            saved = recover_capture(job)
            if saved is None:
                if (job.get('source_metadata') or {}).get('capture_method') == 'manual_pdf':
                    raise CaptureError('manual_pdf_missing', 'The manual PDF was not saved. Attach it again.')
                if importlib.util.find_spec('playwright') is None:
                    raise CaptureError('browser_missing', 'Install Playwright and Chromium to enable website PDF capture.')
                saved = render(job, token, stop, lost)
            if saved is None or stop.is_set() or lost.is_set():
                if not lost.is_set():
                    rpc('release_website_import', p_id=job['id'], p_token=str(token))
                return True
            path, metadata = saved
            update(job, token, status='captured')
            store_capture(job, token, path, metadata)
            logger.info('Import %s: PDF document saved', job['id'])
        except HTTPException as error:
            if error.status_code != 409:
                fail(job, token, error)
        except Exception as error:
            logger.exception('Import %s failed (%s)', job['id'], type(error).__name__)
            fail(job, token, error)
    return True


def attach_manual(job_id, file):
    current = db.get(TABLE, job_id)
    if current['status'] == 'completed':
        return current  # Lost upload response: return the already attached document.
    # Validate before claiming so a malformed upload cannot strand the old job.
    from backend.services.documents import validate_upload
    filename, kind, data = validate_upload(file)
    if kind != 'pdf':
        raise HTTPException(415, 'Attach a PDF saved from your browser.')
    token = uuid4()
    job = rpc('manual_website_import', p_id=str(job_id), p_token=str(token))
    with lease(job, token):
        try:
            directory = job_directory(job) / str(token)
            directory.mkdir(parents=True, exist_ok=True)
            staged = directory / 'capture.tmp.pdf'
            staged.write_bytes(data)
            count, _ = validate_pdf(staged, settings.DOCUMENT_MAX_BYTES, settings.WEBSITE_CAPTURE_MAX_PAGES)
            staged.replace(directory / 'capture.pdf')
            metadata = {'version': 1, 'source_kind': 'website', 'capture_method': 'manual_pdf',
                'submitted_url': job['submitted_url'], 'original_url': job['submitted_url'],
                'article_title': Path(filename).stem[:300], 'capture_options': job['capture_options'],
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'page_count': count,
                'pdf_sha256': sha256(data).hexdigest(),
                'warnings': ['User-supplied PDF: the website and capture time were not independently verified.']}
            checkpoint = directory / 'capture.json.tmp'
            checkpoint.write_text(json.dumps(metadata), encoding='utf-8')
            checkpoint.replace(directory / 'capture.json')
            return store_capture(job, token, directory / 'capture.pdf', metadata)
        except CaptureError as error:
            fail(job, token, error)
            raise HTTPException(422, str(error)) from None
        except Exception as error:
            fail(job, token, error)
            raise
