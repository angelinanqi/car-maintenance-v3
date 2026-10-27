"""Bound, hash-checked original image inputs for the existing generation call."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image


@dataclass(frozen=True)
class ImageInput:
    label: str
    data: bytes
    mime_type: str


def original_image(path, expected_hash, label):
    data = path.read_bytes()
    if len(data) > 7 * 1024 * 1024 or sha256(data).hexdigest() != expected_hash:
        raise ValueError('Original visual bytes are oversized or do not match their source hash')
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
            mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}.get(image.format)
    except Image.DecompressionBombError:
        raise ValueError('Original visual exceeds safe image dimensions') from None
    if mime is None:
        raise ValueError('Unsupported model image format')
    return ImageInput(label, data, mime)
