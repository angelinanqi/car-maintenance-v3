"""Gemini generation adapter preserving the existing generate(prompt, schema) API."""
from shared.observability import observed
import logging

from rag.app.generation.gemini import GeminiClient, GeminiError

logger = logging.getLogger(__name__)


class GenerationClient:
    def __init__(self, *, max_output_tokens=None, timeout=None):
        self.provider = None
        self.model = None
        self.options = {}
        if max_output_tokens is not None:
            self.options["max_output_tokens"] = max_output_tokens
        if timeout is not None:
            self.options["timeout"] = timeout

    @observed('gemini_call')
    def generate(self, prompt: str, *, schema: dict | None = None, images=None) -> str:
        self.provider = self.model = None
        try:
            client = GeminiClient(**self.options)
            answer = client.generate(prompt, schema=schema, images=images) if images else client.generate(prompt, schema=schema)
        except GeminiError as error:
            logger.warning("llm_error provider=gemini reason=%s", error)
            raise
        self.provider, self.model = "gemini", client.model
        return answer
