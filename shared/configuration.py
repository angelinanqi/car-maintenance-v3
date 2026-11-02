"""Load non-secret application settings and private dotenv credentials."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_configuration():
    # Preserve process and dotenv overrides for existing deployments.
    load_dotenv(PROJECT_ROOT / '.env')
    path = PROJECT_ROOT / 'app.config.json'
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError('Cannot read app.config.json; expected a JSON object of string settings') from None
    if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
        raise ValueError('app.config.json must contain a JSON object of string settings')
    for name, value in values.items():
        os.environ.setdefault(name, value)
