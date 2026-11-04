"""Application configuration. No model or retrieval settings are loaded."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from shared.configuration import load_configuration

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_configuration()


def path_setting(name, default):
    path = Path(os.getenv(name) or default).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


BACKEND_HOST = os.getenv("BACKEND_HOST") or "127.0.0.1"
BACKEND_PORT = int(os.getenv("BACKEND_PORT") or "8000")
CORS_ORIGINS = [value.strip().rstrip("/") for value in
                os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if value.strip()]
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_DOCUMENT_BUCKET = os.getenv("SUPABASE_DOCUMENT_BUCKET") or "documents"
SUPABASE_CONTENT_BUCKET = os.getenv("SUPABASE_CONTENT_BUCKET") or "content-images"
SUPABASE_TIMEOUT = float(os.getenv("SUPABASE_TIMEOUT") or "60")
OUTPUT_DIR = path_setting("OUTPUT_DIR", "output")
DOCUMENT_WORK_DIR = path_setting("DOCUMENT_WORK_DIR", str(OUTPUT_DIR / "documents"))
DOCUMENT_MAX_BYTES = int(os.getenv("DOCUMENT_MAX_BYTES") or "52428800")
DOCUMENT_EXTENSIONS = [value.strip().lower() for value in (os.getenv("DOCUMENT_EXTENSIONS") or ".pdf,.md").split(",")]
DOCUMENT_BATCH_LIMIT = int(os.getenv("DOCUMENT_BATCH_LIMIT") or "20")
EXTRACTION_MAX_BYTES = int(os.getenv("EXTRACTION_MAX_BYTES") or "209715200")
IMAGE_MAX_BYTES = int(os.getenv("IMAGE_MAX_BYTES") or "10485760")
IMAGE_CONTENT_TYPES = [value.strip() for value in (os.getenv("IMAGE_CONTENT_TYPES") or "image/jpeg,image/png,image/webp,image/gif").split(",")]
API_PAGE_SIZE = int(os.getenv("API_PAGE_SIZE") or "100")
CHAT_MAX_MESSAGE_LENGTH = int(os.getenv("CHAT_MAX_MESSAGE_LENGTH") or "4000")
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT") or "12")
YOUTUBE_SEARCH_ALL_VIDEOS = (os.getenv("YOUTUBE_SEARCH_ALL_VIDEOS") or "true").lower() == "true"
DUE_SOON_KM = int(os.getenv("DUE_SOON_KM") or "1000")
DUE_SOON_DAYS = int(os.getenv("DUE_SOON_DAYS") or "30")
MINERU_EXECUTABLE = os.getenv("MINERU_EXECUTABLE", "").strip()
MINERU_API_URL = os.getenv("MINERU_API_URL", "").strip().rstrip('/')
MINERU_BACKEND = os.getenv("MINERU_BACKEND") or "pipeline"
MINERU_TIMEOUT = float(os.getenv("MINERU_TIMEOUT") or "7200")
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "").strip().rstrip("/")
RAG_SERVICE_TOKEN = os.getenv("RAG_SERVICE_TOKEN", "").strip()
RAG_SERVICE_TIMEOUT = float(os.getenv("RAG_SERVICE_TIMEOUT") or "240")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
GOOGLE_PLACES_TIMEOUT = float(os.getenv("GOOGLE_PLACES_TIMEOUT") or "15")

for name in ("SUPABASE_TIMEOUT", "DOCUMENT_MAX_BYTES", "DOCUMENT_BATCH_LIMIT", "EXTRACTION_MAX_BYTES",
             "IMAGE_MAX_BYTES", "CHAT_MAX_MESSAGE_LENGTH", "CHAT_HISTORY_LIMIT", "MINERU_TIMEOUT", "RAG_SERVICE_TIMEOUT", "GOOGLE_PLACES_TIMEOUT"):
    if not 0 < globals()[name] < float("inf"):
        raise ValueError(f"{name} must be finite and positive")
if not 1 <= BACKEND_PORT <= 65535 or not 1 <= API_PAGE_SIZE <= 1000:
    raise ValueError("BACKEND_PORT must be 1–65535 and API_PAGE_SIZE must be 1–1000")
if min(DUE_SOON_KM, DUE_SOON_DAYS) < 0:
    raise ValueError("DUE_SOON_KM and DUE_SOON_DAYS must be nonnegative")
if not DOCUMENT_EXTENSIONS or not set(DOCUMENT_EXTENSIONS) <= {".pdf", ".md"}:
    raise ValueError("DOCUMENT_EXTENSIONS must contain .pdf and/or .md")
if not set(IMAGE_CONTENT_TYPES) <= {"image/jpeg", "image/png", "image/webp", "image/gif"}:
    raise ValueError("Unsupported IMAGE_CONTENT_TYPES")
for origin in CORS_ORIGINS:
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("CORS_ORIGINS must contain explicit http(s) origins without paths or credentials")
for name in ('RAG_SERVICE_URL', 'MINERU_API_URL'):
    if globals()[name]:
        parsed = urlsplit(globals()[name])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError(f"{name} must be an http(s) service URL without credentials, query or fragment")
if RAG_SERVICE_TOKEN and len(RAG_SERVICE_TOKEN.encode()) < 32:
    raise ValueError("RAG_SERVICE_TOKEN must contain at least 32 bytes")
