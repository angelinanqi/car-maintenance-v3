"""Load non-secret application settings and private dotenv credentials."""
import json
import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREDENTIAL_SETTINGS = (
    'SUPABASE_SERVICE_ROLE_KEY',
    'RAG_SERVICE_TOKEN',
    'GEMINI_API_KEY',
    'GOOGLE_APPLICATION_CREDENTIALS',
    'GOOGLE_PLACES_API_KEY',
    'YOUTUBE_API_KEY',
)


def load_configuration():
    path = PROJECT_ROOT / 'app.config.json'
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError('Cannot read app.config.json; expected a JSON object of string settings') from None
    if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
        raise ValueError('app.config.json must contain a JSON object of string settings')
    for name, value in values.items():
        os.environ.setdefault(name, value)
    # Old non-secret dotenv entries must not override JSON settings or fallbacks.
    credentials = dotenv_values(PROJECT_ROOT / '.env')
    for name in CREDENTIAL_SETTINGS:
        value = credentials.get(name)
        if value is not None:
            os.environ.setdefault(name, value)
