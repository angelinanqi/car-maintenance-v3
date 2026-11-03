"""Owned emergency uploads, reviewed descriptions, and canonical offline references."""
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4

import httpx
from fastapi import HTTPException

from backend import db, settings
from backend.services.content_uploads import validate_image, store_upload


def meaningful_video_description(value):
    words = re.findall(r'\w+', value.lower())
    return len(words) >= 6 and len(set(words)) >= 5 and len(value.strip()) >= 30


def validate_file(file):
    extension = Path(file.filename or '').suffix.lower()
    video = extension == '.mp4'
    if extension not in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4'}:
        raise HTTPException(415, 'Choose a PNG, JPEG, WebP, GIF image or an MP4 video.')
    limit = settings.DOCUMENT_MAX_BYTES if video else settings.IMAGE_MAX_BYTES
    data = file.file.read(limit + 1)
    if not data or len(data) > limit:
        raise HTTPException(413, 'The file is empty or exceeds the configured upload limit.')
    if video:
        if data[4:8] != b'ftyp':
            raise HTTPException(422, 'Upload a valid MP4 file containing H.264 video and optional AAC audio.')
        executable = shutil.which('ffprobe')
        if not executable:
            raise HTTPException(503, 'Video validation is unavailable. Install FFmpeg (ffprobe) on the backend server.')
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'upload.mp4'
                path.write_bytes(data)
                result = subprocess.run([executable, '-v', 'error', '-protocol_whitelist', 'file', '-count_frames',
                    '-show_entries', 'stream=codec_type,codec_name,width,height,nb_read_frames:format=duration,format_name',
                    '-of', 'json', str(path)], capture_output=True, timeout=20, check=True)
            probe = json.loads(result.stdout)
            streams = probe['streams']
            videos = [stream for stream in streams if stream.get('codec_type') == 'video']
            valid = (not result.stderr.strip() and len(videos) == 1 and videos[0].get('codec_name') == 'h264'
                     and int(videos[0].get('nb_read_frames', 0)) > 0
                     and 0 < videos[0].get('width', 0) <= 3840
                     and 0 < videos[0].get('height', 0) <= 3840
                     and float(probe['format']['duration']) > 0
                     and all(stream.get('codec_type') == 'video' or (
                         stream.get('codec_type') == 'audio' and stream.get('codec_name') == 'aac') for stream in streams))
            if not valid:
                raise ValueError('Unsupported video tracks')
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
            raise HTTPException(422, 'Use an undamaged MP4 with H.264 video (up to 3840 pixels) and optional AAC audio.') from None
        return data, 'video', 'mp4', 'video/mp4'
    ext, mime = validate_image(data, extension=extension, bounded=True)
    return data, 'image', ext, mime


def draft_description(data):
    if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
        raise ValueError('Image description service is not configured')
    response = httpx.post(settings.RAG_SERVICE_URL + '/v1/visual-description',
        headers={'Authorization': 'Bearer ' + settings.RAG_SERVICE_TOKEN},
        files={'original': ('image.png', data, 'application/octet-stream')}, timeout=120)
    response.raise_for_status()
    result = response.json()['identity']
    return '\n'.join(filter(None, [result.get('description'), result.get('uncertainty')]))[:4000]


def upload(playbook_id, step_id, file, description=''):
    data, kind, extension, mime = validate_file(file)
    if kind == 'video' and not meaningful_video_description(description):
        raise HTTPException(422, 'Describe the actual actions demonstrated in the video (at least six words and 30 characters).')
    warning = None
    if kind == 'image':
        try:
            description = draft_description(data)
        except Exception:
            description = ''
            warning = 'The image was uploaded, but its draft description could not be generated. Add a description and review it before publishing.'
    identity = str(uuid4())
    path = f'emergency/{playbook_id}/media/{identity}.{extension}'
    row = store_upload(data, path, mime, 'emergency_media_assets', dict(id=identity,
        playbook_id=str(playbook_id), step_id=str(step_id), storage_path=path, kind=kind,
        mime_type=mime, size_bytes=len(data), sha256=sha256(data).hexdigest()))
    return dict(id=identity, asset_id=identity, kind=kind, url=row['url'],
        title=(Path(file.filename or 'Uploaded media').name[:200]), description=description,
        vehicle_context='', source_reference='', section_id=None, reviewed=False,
        start_seconds=0, transcript=[], sha256=row['sha256'], size_bytes=row['size_bytes'],
        mime_type=mime, warning=warning)


def validate_steps(playbook_id, steps):
    """Never trust a submitted URL, asset hash, or cross-playbook/step asset reference."""
    assets = {row['id']: row for row in db.all_rows('emergency_media_assets', playbook_id=str(playbook_id))}
    bucket = db.bucket(settings.SUPABASE_CONTENT_BUCKET)
    for step in steps:
        if step.get('imageUrl'):
            raise HTTPException(422, 'Replace the legacy image URL with a direct image upload before saving or publishing.')
        for media in step.get('media', []):
            asset = assets.get(str(media.get('asset_id') or ''))
            if (not asset or asset['step_id'] != step['id'] or asset['kind'] != media['kind']
                    or media['url'] != bucket.get_public_url(asset['storage_path'])):
                raise HTTPException(422, 'Emergency media must be uploaded directly to this playbook step. External links are not supported.')
            if media.get('transcript') or media.get('start_seconds'):
                raise HTTPException(422, 'Emergency videos use a written description, without transcripts or external timestamps.')
            if media['kind'] == 'video' and not meaningful_video_description(media.get('description', '')):
                raise HTTPException(422, 'Describe the actual actions demonstrated in every video (at least six words and 30 characters).')
            for key in ('sha256', 'size_bytes', 'mime_type'):
                media[key] = asset[key]
    return steps
