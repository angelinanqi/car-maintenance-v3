"""Validated persistent image uploads for learning and emergency content."""
from io import BytesIO
import logging
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from backend import db, settings


def validate_image(data, *, extension=None, bounded=False):
    if not data or len(data) > settings.IMAGE_MAX_BYTES:
        raise HTTPException(413, 'Image exceeds the configured upload size limit.')
    try:
        with Image.open(BytesIO(data)) as image:
            if bounded and (image.width > 8192 or image.height > 8192 or
                            image.width * image.height > 16000000 or getattr(image, 'n_frames', 1) > 100):
                raise ValueError('Image dimensions or animation are too large')
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError):
        raise HTTPException(422, 'Upload a valid PNG, JPEG, WebP, or GIF image.') from None
    formats = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'),
               'WEBP': ('webp', 'image/webp'), 'GIF': ('gif', 'image/gif')}
    if image_format not in formats or formats[image_format][1] not in settings.IMAGE_CONTENT_TYPES:
        raise HTTPException(415, 'This image format is not enabled.')
    if extension and extension not in {'PNG': {'.png'}, 'JPEG': {'.jpg', '.jpeg'},
                                      'WEBP': {'.webp'}, 'GIF': {'.gif'}}[image_format]:
        raise HTTPException(422, 'The image bytes do not match the file extension.')
    return formats[image_format]


def upload_image(parent_id, file, *, emergency=False):
    data = file.file.read(settings.IMAGE_MAX_BYTES + 1)
    extension, mime = validate_image(data)
    image_id = str(uuid4())
    prefix, table, key = ('emergency', 'emergency_images', 'playbook_id') if emergency else ('guides', 'guide_images', 'guide_id')
    path = f'{prefix}/{parent_id}/images/{image_id}.{extension}'
    return store_upload(data, path, mime, table, {'id': image_id, key: str(parent_id), 'storage_path': path})


def store_upload(data, path, mime, table, values):
    """Existing immutable storage upload and database registration with rollback."""
    bucket = db.bucket(settings.SUPABASE_CONTENT_BUCKET)
    bucket.upload(path, data, {'content-type': mime, 'upsert': 'false'})
    try:
        url = bucket.get_public_url(path)
        row = db.insert(table, values)
        return {**row, 'url': url}
    except Exception:
        try:
            bucket.remove([path])
        except Exception:
            logging.getLogger(__name__).exception('Failed to clean up unrecorded content upload %s', path)
        raise
