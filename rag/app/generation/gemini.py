"""Gemini Developer API transport using the existing httpx dependency."""
import asyncio
import json
import random
import re

import httpx

from rag.config import settings
from rag.app.generation.ollama import SYSTEM_PROMPT

API_URL = "https://generativelanguage.googleapis.com/v1beta"
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


class GeminiError(RuntimeError):
    """Sanitised provider failure; only transient failures permit fallback."""

    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class GeminiClient:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise GeminiError("GEMINI_API_KEY is not configured")
        self.model = settings.GEMINI_MODEL.removeprefix("models/")
        if not self.model or not re.fullmatch(r"[A-Za-z0-9._-]+", self.model):
            raise GeminiError("GEMINI_MODEL must name a model accessible to your API key")

    def generate(self, prompt: str, *, schema: dict | None = None) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        # RAG invokes the synchronous interface in a worker thread. Bound the
        # metadata check, generation, retries and backoff together.
        async def run():
            return await asyncio.wait_for(self._generate(prompt, schema), settings.GEMINI_TIMEOUT)

        try:
            return asyncio.run(run())
        except TimeoutError:
            raise GeminiError("Gemini request deadline exceeded", retryable=True) from None

    async def _generate(self, prompt, schema):
        config = {"temperature": settings.GEMINI_TEMPERATURE,
                  "maxOutputTokens": settings.GEMINI_MAX_OUTPUT_TOKENS}
        if schema is not None:
            config["responseFormat"] = {"text": {"mimeType": "application/json", "schema": schema}}
        body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": config}
        async with httpx.AsyncClient(headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                                     timeout=settings.GEMINI_TIMEOUT, follow_redirects=False) as client:
            metadata = await self._request(client, "GET", f"/models/{self.model}")
            methods = metadata.get("supportedGenerationMethods") if isinstance(metadata, dict) else None
            if not isinstance(methods, list) or "generateContent" not in methods:
                raise GeminiError("Configured Gemini model does not support generateContent")
            limit = metadata.get("outputTokenLimit")
            if isinstance(limit, int) and settings.GEMINI_MAX_OUTPUT_TOKENS > limit:
                raise GeminiError("GEMINI_MAX_OUTPUT_TOKENS exceeds the configured model limit")
            maximum = metadata.get("maxTemperature")
            if isinstance(maximum, (int, float)) and settings.GEMINI_TEMPERATURE > maximum:
                raise GeminiError("GEMINI_TEMPERATURE exceeds the configured model limit")
            result = await self._request(client, "POST", f"/models/{self.model}:generateContent", body)
        return self._text(result, structured=schema is not None)

    async def _request(self, client, method, path, body=None):
        for attempt in range(settings.GEMINI_MAX_RETRIES + 1):
            response = None
            try:
                if body is None:
                    response = await client.request(method, API_URL + path)
                else:
                    response = await client.request(method, API_URL + path, json=body)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                failure = GeminiError("Gemini network request failed", retryable=True)
            else:
                if response.is_success:
                    try:
                        return response.json()
                    except ValueError:
                        raise GeminiError("Gemini returned invalid response JSON") from None
                failure = GeminiError(f"Gemini HTTP {response.status_code}",
                                      retryable=response.status_code in TRANSIENT_STATUS)
            if not failure.retryable or attempt == settings.GEMINI_MAX_RETRIES:
                raise failure from None
            delay = 2 ** attempt + random.uniform(0, 0.25)
            if response is not None:
                # Honour numeric Retry-After within the overall deadline.
                try:
                    delay = max(delay, float(response.headers.get("Retry-After", "0")))
                except ValueError:
                    pass
            await asyncio.sleep(delay)

    @staticmethod
    def _text(result, *, structured):
        if not isinstance(result, dict):
            raise GeminiError("Gemini returned an invalid response")
        feedback = result.get("promptFeedback") or {}
        if not isinstance(feedback, dict):
            raise GeminiError("Gemini returned invalid prompt feedback")
        if feedback.get("blockReason"):
            raise GeminiError("Gemini blocked the prompt")
        candidates = result.get("candidates") or []
        if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
            raise GeminiError("Gemini returned no answer candidate")
        candidate = candidates[0]
        if candidate.get("finishReason") != "STOP":
            # Safety blocks and truncated output are not availability failures.
            raise GeminiError("Gemini did not return a complete answer")
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            raise GeminiError("Gemini returned invalid candidate content")
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            raise GeminiError("Gemini returned invalid content parts")
        text = "".join(part["text"] for part in parts if isinstance(part, dict)
                       and not part.get("thought") and isinstance(part.get("text"), str)).strip()
        if not text:
            raise GeminiError("Gemini returned empty answer text")
        if structured:
            try:
                json.loads(text)
            except ValueError:
                raise GeminiError("Gemini returned invalid structured answer JSON") from None
        # Existing grounded generation validates schema, evidence and citations.
        return text
