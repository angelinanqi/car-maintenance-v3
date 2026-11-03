"""Validate website provenance without trusting PDF filenames or embedded metadata."""
import json
import re
from shared.public_web import public_url


def validate_metadata(value):
    if not isinstance(value, dict) or value.get('version') != 1 or value.get('source_kind') != 'website':
        raise ValueError('Invalid website source metadata')
    result = json.loads(json.dumps(value))
    if result.get('capture_method') not in {'browser_pdf', 'manual_pdf'}:
        raise ValueError('Unknown website capture method')
    for key in ('original_url', 'submitted_url'):
        result[key] = public_url(result[key], keep_fragment=True)
    for key in ('article_title', 'retrieved_at'):
        if not isinstance(result.get(key), str) or not result[key].strip() or len(result[key]) > 300:
            raise ValueError('Missing website source details')
    if not re.fullmatch('[0-9a-f]{64}', result.get('pdf_sha256', '')):
        raise ValueError('Missing website PDF checksum')
    if not isinstance(result.get('warnings', []), list) or any(
            not isinstance(item, str) or len(item) > 1000 for item in result.get('warnings', [])):
        raise ValueError('Invalid capture warnings')
    if len(result.get('warnings', [])) > 30:
        raise ValueError('Too many capture warnings')
    return result
