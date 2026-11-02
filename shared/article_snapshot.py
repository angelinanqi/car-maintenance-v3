"""Self-contained Markdown snapshots; metadata never enters article embeddings."""
import base64
import json
from hashlib import sha256
from urllib.parse import urlsplit

PREFIX = '<!-- roadie-article-v1\n'
SUFFIX = '\n-->\n'


def encode(metadata, markdown, assets):
    payload = dict(metadata, assets={path: base64.b64encode(data).decode('ascii')
                                     for path, data in assets.items()})
    # Escaping prevents an article title or URL from terminating the comment.
    header = json.dumps(payload, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e')
    return (PREFIX + header + SUFFIX + markdown).encode('utf-8')


def decode(text):
    if not text.startswith(PREFIX):
        return None, text, {}
    header, separator, markdown = text[len(PREFIX):].partition(SUFFIX)
    if not separator:
        raise ValueError('Article snapshot metadata is incomplete.')
    metadata = json.loads(header)
    if not isinstance(metadata, dict) or any(not isinstance(metadata.get(key), str) or not metadata[key]
            for key in ('original_url', 'article_title', 'retrieved_at', 'content_sha256')):
        raise ValueError('Article snapshot metadata is invalid.')
    url = urlsplit(metadata['original_url'])
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password:
        raise ValueError('Article snapshot URL is invalid.')
    assets = metadata.pop('assets', {})
    from shared.source_elements import image_path
    assets = {image_path(path): base64.b64decode(data, validate=True) for path, data in assets.items()}
    if sha256(markdown.encode('utf-8')).hexdigest() != metadata.get('content_sha256'):
        raise ValueError('Article snapshot content hash does not match.')
    return metadata, markdown, assets
