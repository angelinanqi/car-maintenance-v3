"""Gemini Interactions SDK adapter for the existing RAG generation interface."""
import asyncio
import base64
import json
import random
import re

import httpx
from google import genai
from google.auth.exceptions import GoogleAuthError
from google.genai import interactions, types
# Interactions has a separate error hierarchy from google.genai.errors in
# google-genai 2.31.0. Keep this import aligned with the pinned dependency.
from google.genai._gaos.lib import compat_errors as interaction_errors
from pydantic import ValidationError

from rag.config import settings
from rag.app.generation.ollama import SYSTEM_PROMPT

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


class GeminiError(RuntimeError):
    """Sanitised provider failure; only transient failures permit fallback."""

    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class GeminiClient:
    def __init__(self, *, max_output_tokens=None, timeout=None):
        self.last_usage = None
        self.max_output_tokens = max_output_tokens or settings.GEMINI_MAX_OUTPUT_TOKENS
        self.timeout = timeout or settings.GEMINI_TIMEOUT
        if settings.GEMINI_USE_CLOUD and not settings.GOOGLE_CLOUD_PROJECT:
            raise GeminiError("Configure GOOGLE_CLOUD_PROJECT for Gemini Cloud authentication")
        if not settings.GEMINI_USE_CLOUD and not settings.GEMINI_API_KEY:
            raise GeminiError("GEMINI_API_KEY is not configured")
        self.model = settings.GEMINI_MODEL.removeprefix("models/")
        if not self.model or not re.fullmatch(r"[A-Za-z0-9._-]+", self.model):
            raise GeminiError("GEMINI_MODEL must name a model accessible to the configured credentials")

    def generate(self, prompt: str, *, schema: dict | None = None, images=None) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        # RAG invokes the synchronous interface in a worker thread. Bound the
        # SDK call, retries and backoff together. Create and close the SDK
        # transports inside this event loop rather than sharing them across calls.
        async def run():
            task = self._generate(prompt, schema, images) if images else self._generate(prompt, schema)
            return await asyncio.wait_for(task, self.timeout)

        try:
            return asyncio.run(run())
        except TimeoutError:
            raise GeminiError("Gemini request deadline exceeded", retryable=True) from None
        except GoogleAuthError:
            raise GeminiError("Gemini Cloud authentication failed. Check Application Default Credentials and service-account access.") from None

    async def _generate(self, prompt, schema, images=None):
        request = {
            "model": self.model,
            "input": prompt,
            "system_instruction": SYSTEM_PROMPT,
            "generation_config": {
                "temperature": settings.GEMINI_TEMPERATURE,
                "max_output_tokens": self.max_output_tokens,
            },
            # RAG already supplies the applicable evidence and conversation history.
            "store": False,
            "stream": False,
            "background": False,
        }
        if schema is not None:
            request["response_format"] = interactions.TextResponseFormat(
                mime_type="application/json", schema=schema,
            )
        if images:
            request['input'] = [{'type': 'text', 'text': prompt}]
            for image in images:
                request['input'].extend([
                    {'type': 'text', 'text': 'Original source image: ' + image.label},
                    {'type': 'image', 'mime_type': image.mime_type,
                     'data': base64.b64encode(image.data).decode('ascii')},
                ])
        # Let Interactions validate model access and generation limits; a legacy
        # generateContent capability check would reject Interactions-only models.
        authentication = (
            {"enterprise": True, "project": settings.GOOGLE_CLOUD_PROJECT,
             "location": settings.GOOGLE_CLOUD_LOCATION}
            if settings.GEMINI_USE_CLOUD else
            {"api_key": settings.GEMINI_API_KEY, "enterprise": False}
        )
        with genai.Client(
            **authentication,
            http_options=types.HttpOptions(
                api_version="v1beta1" if settings.GEMINI_USE_CLOUD else "v1beta",
                timeout=max(1, int(self.timeout * 1000)),
                # This adapter owns retries so the SDK cannot multiply attempts.
                retry_options=types.HttpRetryOptions(attempts=0),
            ),
        ) as sdk:
            async with sdk.aio as client:
                result = await self._request(client, request)
        usage = getattr(result, 'usage', None)
        self.last_usage = usage.model_dump(mode='json') if hasattr(usage, 'model_dump') else None
        return self._text(result, structured=schema is not None)

    async def _request(self, client, request):
        for attempt in range(settings.GEMINI_MAX_RETRIES + 1):
            response = None
            try:
                return await client.interactions.create(**request)
            except (interaction_errors.APIConnectionError, httpx.TimeoutException,
                    httpx.NetworkError, httpx.RemoteProtocolError):
                failure = GeminiError("Gemini network request failed", retryable=True)
            except interaction_errors.APIResponseValidationError:
                raise GeminiError("Gemini returned an invalid response") from None
            except interaction_errors.APIError as error:
                # Never expose the SDK error body: it may contain request data.
                response = getattr(error, "response", None)
                status = error.status_code
                failure = GeminiError(
                    self._api_error_message(response, status),
                    retryable=status in TRANSIENT_STATUS,
                )
            except (ValidationError, json.JSONDecodeError):
                raise GeminiError("Gemini SDK rejected the request or response") from None
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
    def _api_error_message(response, status):
        messages = {
            "API_KEY_INVALID": "Gemini API key is invalid. Replace GEMINI_API_KEY on the server.",
            "API_KEY_SERVICE_BLOCKED": "The Gemini API key does not allow access to the Gemini API.",
            "SERVICE_DISABLED": "Enable the Gemini API in the key's Google project.",
            "BILLING_DISABLED": "Gemini billing is disabled for the configured Google project.",
        }
        if response is not None:
            try:
                payload = response.json()
                # Google may wrap Interactions errors in a one-element array.
                errors = payload if isinstance(payload, list) else [payload]
                for item in errors:
                    for detail in item.get("error", {}).get("details", []):
                        if detail.get("reason") in messages:
                            return messages[detail["reason"]]
            except (ValueError, AttributeError, TypeError):
                pass
        return f"Gemini HTTP {status}" if status is not None else "Gemini API request failed"

    @staticmethod
    def _text(result, *, structured):
        if getattr(result, "status", None) != "completed":
            # Safety blocks and truncated output are not availability failures.
            raise GeminiError("Gemini did not return a complete answer")
        # The SDK convenience property includes final model text, not thoughts.
        text = getattr(result, "output_text", None)
        if not isinstance(text, str):
            raise GeminiError("Gemini returned invalid answer text")
        text = text.strip()
        if not text:
            raise GeminiError("Gemini returned empty answer text")
        if structured:
            try:
                json.loads(text)
            except ValueError:
                raise GeminiError("Gemini returned invalid structured answer JSON") from None
        # Existing grounded generation validates schema, evidence and citations.
        return text
