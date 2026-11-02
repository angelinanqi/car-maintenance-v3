"""Small client for the native MinerU 3.4.5 task API (no OCR imports)."""
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
import shutil
import time
from zipfile import ZipFile

import httpx


class ProcessingStopped(Exception):
    """Leave persisted work queued when the backend stops."""


def unpack_result(archive_path, destination, max_bytes):
    with ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(item.file_size for item in entries) > max_bytes:
            raise ValueError('MinerU result exceeds extraction limits')
        names = set()
        for item in entries:
            name = item.orig_filename
            path = PurePosixPath(name)
            if (not path.parts or path.is_absolute() or '..' in path.parts
                    or '\\' in name or ':' in name or '\x00' in name
                    or (item.external_attr >> 16) & 0o170000 == 0o120000
                    or name.casefold() in names):
                raise ValueError('Unsafe MinerU result archive member')
            names.add(name.casefold())
        for item in entries:
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)


def extract_remote(source, destination, checkpoint, *, url, backend, timeout, max_bytes, stop=None):
    """Resume acknowledged tasks; never automatically retry an ambiguous POST.

    MinerU has no submission idempotency key. An interrupted POST is recorded
    before upload so a later retry cannot silently create a second expensive job.
    """
    digest = sha256()
    with source.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    identity = {'source_sha256': digest.hexdigest(), 'url': url, 'backend': backend}
    state = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    if any(state.get(key) != value for key, value in identity.items()):
        state = {}

    def save(value):
        staged = checkpoint.with_suffix('.tmp')
        staged.write_text(json.dumps(value, indent=2), encoding='utf-8')
        staged.replace(checkpoint)

    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=httpx.Timeout(60, connect=15), follow_redirects=False) as client:
        if stop and stop.is_set():
            raise ProcessingStopped()
        if not state:
            health = client.get(url + '/health')
            health.raise_for_status()
            info = health.json()
            if info.get('version') != '3.4.5' or info.get('protocol_version') != 2:
                raise ValueError('Remote OCR requires MinerU 3.4.5 with task protocol 2')
            if stop and stop.is_set():
                raise ProcessingStopped()
            state = {**identity, 'submission': 'unconfirmed'}
            save(state)
            data = {key: 'true' for key in (
                'formula_enable', 'table_enable', 'image_analysis', 'return_md',
                'return_middle_json', 'return_model_output', 'return_content_list',
                'return_images', 'response_format_zip', 'return_original_file')}
            data.update(lang_list='ch', backend=backend, parse_method='auto',
                        start_page_id='0', end_page_id='99999',
                        client_side_output_generation='false')
            with source.open('rb') as handle:
                response = client.post(url + '/tasks', data=data,
                    files={'files': (source.name, handle, 'application/pdf')})
            if response.status_code != 202:
                # Explicit rejection is safe to retry; unknown transport outcomes are not.
                if 400 <= response.status_code < 500:
                    checkpoint.unlink(missing_ok=True)
                    response.raise_for_status()
                raise RuntimeError(f'MinerU submission returned HTTP {response.status_code}')
            task_id = response.json().get('task_id')
            if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', task_id):
                raise ValueError('MinerU returned an invalid task identifier')
            state = {**identity, 'task_id': task_id}
            save(state)
        if not state.get('task_id'):
            raise RuntimeError(f'MinerU submission outcome is unknown. Inspect Windows OCR logs/tasks before '
                               f'archiving {checkpoint} and retrying; a task may already be running.')
        task_id = state['task_id']
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', task_id):
            raise ValueError('Invalid saved MinerU task identifier')
        # Construct URLs locally: API-generated URLs may contain the Windows loopback host.
        task_url = url + '/tasks/' + task_id
        while time.monotonic() < deadline:
            if stop and stop.is_set():
                raise ProcessingStopped()
            try:
                response = client.get(task_url)
                response.raise_for_status()
            except httpx.TransportError:
                time.sleep(min(2, max(0, deadline - time.monotonic())))
                continue
            status = response.json().get('status')
            if status == 'completed':
                break
            if status not in {'pending', 'processing'}:
                raise RuntimeError(f'MinerU task {task_id} ended with status {status!r}. '
                                   f'Inspect Windows OCR logs; checkpoint: {checkpoint}')
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        else:
            raise TimeoutError(f'MinerU task {task_id} exceeded {timeout:g}s; retry resumes the saved task')
        archive_path = destination.parent / 'mineru-result.zip'
        total = 0
        with client.stream('GET', task_url + '/result') as response:
            response.raise_for_status()
            if response.status_code != 200 or 'application/zip' not in response.headers.get('content-type', ''):
                raise ValueError('MinerU did not return a completed ZIP result')
            with archive_path.open('wb') as handle:
                for block in response.iter_bytes():
                    if stop and stop.is_set():
                        raise ProcessingStopped()
                    total += len(block)
                    if total > max_bytes:
                        raise ValueError('MinerU result download exceeds extraction limits')
                    if time.monotonic() >= deadline:
                        raise TimeoutError('MinerU result download exceeded the task deadline; retry to resume')
                    handle.write(block)
        unpack_result(archive_path, destination, max_bytes)
