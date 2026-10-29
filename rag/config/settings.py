"""Shared settings. Relative data paths are resolved from the repository root."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def path_setting(name, default):
    path = Path(os.getenv(name) or default).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


OLLAMA_HOST = os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or "phi4-mini:latest"
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT") or "120")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX") or "4096")
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT") or "512")
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
LLM_FALLBACK_ENABLED = (os.getenv("LLM_FALLBACK_ENABLED") or "true").strip().lower()
if LLM_PROVIDER not in {"gemini", "ollama"}:
    raise ValueError("LLM_PROVIDER must be gemini or ollama")
if LLM_FALLBACK_ENABLED not in {"true", "false"}:
    raise ValueError("LLM_FALLBACK_ENABLED must be true or false")
LLM_FALLBACK_ENABLED = LLM_FALLBACK_ENABLED == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "").strip() or "global"
# A Cloud project without an API key uses Application Default Credentials,
# including GOOGLE_APPLICATION_CREDENTIALS for local service-account files.
_cloud_default = "true" if GOOGLE_CLOUD_PROJECT and not GEMINI_API_KEY else "false"
_cloud_mode = (os.getenv("GOOGLE_GENAI_USE_ENTERPRISE") or
               os.getenv("GOOGLE_GENAI_USE_VERTEXAI") or _cloud_default).strip().lower()
if _cloud_mode not in {"true", "false"}:
    raise ValueError("GOOGLE_GENAI_USE_ENTERPRISE must be true or false")
GEMINI_USE_CLOUD = _cloud_mode == "true"
# Select an accessible model in your account; there is no assumed model default.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT") or "30")
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES") or "1")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE") or "0")
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS") or "2048")
if not 0 <= GEMINI_MAX_RETRIES <= 3:
    raise ValueError("GEMINI_MAX_RETRIES must be between 0 and 3")
if not 0 <= GEMINI_TEMPERATURE <= 2:
    raise ValueError("GEMINI_TEMPERATURE must be between 0 and 2")
if OLLAMA_NUM_CTX < 2048 or OLLAMA_NUM_PREDICT < 1:
    raise ValueError("OLLAMA_NUM_CTX must be at least 2048 and OLLAMA_NUM_PREDICT must be positive")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL") or "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION") or "768")
OUTPUT_DIR = path_setting("OUTPUT_DIR", "output")
CHROMA_PATH = path_setting("CHROMA_PATH", str(OUTPUT_DIR / "embeddings/chroma"))
MANUAL_COLLECTION = os.getenv("MANUAL_COLLECTION") or "rag_chunks"
# Soft character target for packing whole source blocks. No word overlap.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE") or "2000")
RAG_RETRIEVAL_MODE = os.getenv("RAG_RETRIEVAL_MODE") or "hybrid"
RAG_CANDIDATES = int(os.getenv("RAG_CANDIDATES") or "20")
RAG_RRF_K = int(os.getenv("RAG_RRF_K") or "60")
RAG_CONTEXT_CHARS = int(os.getenv("RAG_CONTEXT_CHARS") or "16000")
# In the chat path this reranks retrieved visual candidates before their budgets;
# paragraph order stays hybrid-ranked. These are the evaluated candidate defaults.
RAG_RERANK = (os.getenv("RAG_RERANK") or "true").lower() == "true"
# Supply a bounded set of original pages/crops in the existing answer call.
RAG_VISUAL_INPUTS = (os.getenv('RAG_VISUAL_INPUTS') or 'true').lower() == 'true'
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
if RAG_RETRIEVAL_MODE not in {"dense", "hybrid", "adaptive", "lexical"}:
    raise ValueError("RAG_RETRIEVAL_MODE must be dense, hybrid, adaptive or lexical")
if min(RAG_CANDIDATES, RAG_RRF_K, RAG_CONTEXT_CHARS) < 1:
    raise ValueError("RAG_CANDIDATES, RAG_RRF_K and RAG_CONTEXT_CHARS must be positive")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_CHANNEL_URL = os.getenv("YOUTUBE_CHANNEL_URL", "").strip()
YOUTUBE_OUTPUT_DIR = path_setting("YOUTUBE_OUTPUT_DIR", str(OUTPUT_DIR / "youtube"))
YOUTUBE_COLLECTION = os.getenv("YOUTUBE_COLLECTION") or "youtube_chunks"
YOUTUBE_API_URL = os.getenv("YOUTUBE_API_URL") or "https://www.googleapis.com/youtube/v3"
YOUTUBE_WATCH_URL = os.getenv("YOUTUBE_WATCH_URL") or "https://www.youtube.com/watch"
YOUTUBE_CHUNK_TOKENS = int(os.getenv("YOUTUBE_CHUNK_TOKENS") or "400")
YOUTUBE_OVERLAP_TOKENS = int(os.getenv("YOUTUBE_OVERLAP_TOKENS") or "60")
VIDEO_RELEVANCE_THRESHOLD = float(os.getenv("VIDEO_RELEVANCE_THRESHOLD") or "0.75")

# Retrieval, request limits, and ingestion tuning.
SCHEDULE_DRAFT_MAX_OUTPUT_TOKENS = int(os.getenv("SCHEDULE_DRAFT_MAX_OUTPUT_TOKENS") or "32768")
SCHEDULE_DRAFT_TIMEOUT = float(os.getenv("SCHEDULE_DRAFT_TIMEOUT") or "90")
RAG_TOP_K = int(os.getenv("RAG_TOP_K") or "5")
CHAT_MAX_MESSAGE_LENGTH = int(os.getenv("CHAT_MAX_MESSAGE_LENGTH") or "4000")
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT") or "6")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE") or "8")
EMBEDDING_CPU_THREADS = int(os.getenv("EMBEDDING_CPU_THREADS") or "4")
if EMBEDDING_CPU_THREADS < 1:
    raise ValueError("EMBEDDING_CPU_THREADS must be positive")
EMBEDDING_MAX_TOKENS = int(os.getenv("EMBEDDING_MAX_TOKENS") or "8192")
MALAY_CONFIDENCE_THRESHOLD = float(os.getenv("MALAY_CONFIDENCE_THRESHOLD") or "0.97")
YOUTUBE_API_TIMEOUT = float(os.getenv("YOUTUBE_API_TIMEOUT") or "30")
YOUTUBE_PAGE_SIZE = int(os.getenv("YOUTUBE_PAGE_SIZE") or "50")
YOUTUBE_TRANSCRIPT_LANGUAGES = [
    language.strip() for language in
    (os.getenv("YOUTUBE_TRANSCRIPT_LANGUAGES") or "ms,en").split(",")
    if language.strip()
]

# Fail early with setting names instead of obscure runtime failures.
for name in (
    "OLLAMA_TIMEOUT", "GEMINI_TIMEOUT", "GEMINI_MAX_OUTPUT_TOKENS",
    "EMBEDDING_DIMENSION", "CHUNK_SIZE",
    "RAG_TOP_K", "CHAT_MAX_MESSAGE_LENGTH", "CHAT_HISTORY_LIMIT",
    "EMBEDDING_BATCH_SIZE", "EMBEDDING_MAX_TOKENS",
    "YOUTUBE_API_TIMEOUT", "YOUTUBE_CHUNK_TOKENS",
    "SCHEDULE_DRAFT_MAX_OUTPUT_TOKENS", "SCHEDULE_DRAFT_TIMEOUT",
):
    value = globals()[name]
    if not 0 < value < float("inf"):
        raise ValueError(f"{name} must be a finite positive number")
if not 1 <= YOUTUBE_PAGE_SIZE <= 50:
    raise ValueError("YOUTUBE_PAGE_SIZE must be between 1 and 50")
if not 0 <= YOUTUBE_OVERLAP_TOKENS < YOUTUBE_CHUNK_TOKENS:
    raise ValueError("YOUTUBE_OVERLAP_TOKENS must be nonnegative and less than YOUTUBE_CHUNK_TOKENS")
if not 0 <= MALAY_CONFIDENCE_THRESHOLD <= 1:
    raise ValueError("MALAY_CONFIDENCE_THRESHOLD must be between 0 and 1")

if not -1 <= VIDEO_RELEVANCE_THRESHOLD <= 1:
    raise ValueError("VIDEO_RELEVANCE_THRESHOLD must be between -1 and 1")

# HTTP timeout for the index worker's backend requests.
SUPABASE_TIMEOUT = float(os.getenv("SUPABASE_TIMEOUT") or "60")
if not 0 < SUPABASE_TIMEOUT < float("inf"):
    raise ValueError("SUPABASE_TIMEOUT must be finite and positive")
