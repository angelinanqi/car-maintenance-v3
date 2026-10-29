"""Small provider selector preserving the existing generate(prompt, schema) API."""
import logging

from rag.config import settings
from rag.app.generation.gemini import GeminiClient, GeminiError
from rag.app.generation.ollama import OllamaClient

logger = logging.getLogger(__name__)
FALLBACK_NOTICE = "Generation used the local Ollama fallback because Gemini was temporarily unavailable."


class GenerationClient:
    def __init__(self, *, max_output_tokens=None, timeout=None):
        self.provider = None
        self.model = None
        self.fallback_reason = None
        self.options = {}
        if max_output_tokens is not None:
            self.options["max_output_tokens"] = max_output_tokens
        if timeout is not None:
            self.options["timeout"] = timeout

    def generate(self, prompt: str, *, schema: dict | None = None, images=None) -> str:
        self.provider = self.model = self.fallback_reason = None
        if settings.LLM_PROVIDER == "ollama":
            if images:
                raise ValueError('Original-image answering requires the configured Gemini provider')
            client = OllamaClient(**self.options)
        else:
            try:
                client = GeminiClient(**self.options)
                answer = client.generate(prompt, schema=schema, images=images) if images else client.generate(prompt, schema=schema)
            except GeminiError as error:
                if images or not settings.LLM_FALLBACK_ENABLED or not error.retryable:
                    logger.warning("llm_error provider=gemini reason=%s", error)
                    raise
                self.fallback_reason = str(error)
                logger.warning("llm_fallback primary=gemini fallback=ollama reason=%s", error)
                client = OllamaClient(**self.options)
            else:
                self.provider, self.model = "gemini", client.model
                return answer
        answer = client.generate(prompt, schema=schema)
        self.provider, self.model = "ollama", client.model
        return answer
