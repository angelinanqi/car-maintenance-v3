"""Local text generation. Gemini remains an ingestion-only dependency."""
import json
import logging
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from math import ceil
from threading import Lock, BoundedSemaphore, Event
from time import perf_counter

import httpx

from rag.config import settings
from shared.observability import observed

logger = logging.getLogger(__name__)
_inference_lock = Lock()
_inference_slots = BoundedSemaphore(settings.RAG_MAX_REQUESTS)
_request_slots = BoundedSemaphore(settings.RAG_MAX_REQUESTS)
_budget = ContextVar('rag_request_budget', default=None)


class GenerationError(RuntimeError):
    """A local inference failure safe to report without request contents."""


def remaining_seconds(limit=None):
    state = _budget.get()
    remaining = max(0.0, state['deadline'] - perf_counter()) if state else float('inf')
    if state and state['cancelled'].is_set():
        remaining = 0.0
    return min(remaining, limit) if limit is not None else remaining


def check_budget():
    if remaining_seconds() <= 0:
        raise GenerationError('The request deadline has elapsed')


def acquire_with_budget(lock, timeout):
    deadline = perf_counter() + remaining_seconds(timeout)
    while True:
        check_budget()
        remaining = deadline - perf_counter()
        if remaining <= 0:
            return False
        if lock.acquire(timeout=min(0.05, remaining)):
            return True


@contextmanager
def request_budget(timeout=None):
    parent = _budget.get()
    state = {'deadline': perf_counter() + (settings.RAG_REQUEST_TIMEOUT if timeout is None else timeout),
             'cancelled': Event()}
    if parent:
        state['deadline'] = min(state['deadline'], parent['deadline'])
        if parent['cancelled'].is_set():
            state['cancelled'].set()
    token = _budget.set(state)
    try:
        yield
    finally:
        # asyncio cancellation cannot kill a native model call. Its worker sees
        # this flag before starting another batch, lock wait, or HTTP request.
        state['cancelled'].set()
        _budget.reset(token)


@contextmanager
def inference_guard(lock):
    check_budget()
    if not acquire_with_budget(lock, settings.RAG_REQUEST_TIMEOUT):
        raise GenerationError('Inference wait exceeded the request deadline')
    try:
        check_budget()
        yield
    finally:
        lock.release()


def request_deadline(fn):
    @wraps(fn)
    async def wrapped(*args, **kwargs):
        with request_budget():
            async with asyncio.timeout(remaining_seconds()):
                return await fn(*args, **kwargs)
    return wrapped


def bounded_request(fn):
    @wraps(fn)
    async def wrapped(query, *args, **kwargs):
        from shared.safety import immediate_emergency
        # Immediate safety guidance must remain available even when inference is busy.
        if immediate_emergency(query):
            return await fn(query, *args, **kwargs)
        if not _request_slots.acquire(blocking=False):
            raise GenerationError('The chatbot is busy; please retry shortly')
        try:
            return await request_deadline(fn)(query, *args, **kwargs)
        finally:
            _request_slots.release()
    return wrapped


class GenerationClient:
    def __init__(self, *, max_output_tokens=None, timeout=None):
        self.provider = 'ollama'
        self.model = settings.OLLAMA_MODEL
        self.max_output_tokens = min(max_output_tokens or settings.OLLAMA_MAX_OUTPUT_TOKENS,
                                     settings.OLLAMA_MAX_OUTPUT_TOKENS)
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self.last_usage = None
        self.usage_history = []

    def verify_model(self):
        """Check that the configured model is installed with the expected adapter state."""
        try:
            with httpx.Client(timeout=httpx.Timeout(15, connect=5), trust_env=False) as client:
                response = client.post(settings.OLLAMA_URL + '/api/show', json={'model': self.model})
                response.raise_for_status()
                detail = response.json()
            modelfile = detail.get('modelfile', '')
            if not modelfile.strip():
                raise ValueError('Missing Ollama Modelfile')
            has_adapter = any(line.strip().upper().startswith('ADAPTER ') for line in modelfile.splitlines())
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise GenerationError(f'The configured model {self.model} could not be verified in Ollama') from None
        requires_adapter = self.model != settings.OLLAMA_BASE_MODEL
        if has_adapter != requires_adapter:
            expected = 'with' if requires_adapter else 'without'
            raise GenerationError(f'Ollama model {self.model} must be installed {expected} a LoRA adapter')
        return {'model': self.model, 'adapter_verified': has_adapter}

    @observed('ollama_call')
    def generate(self, prompt: str, *, schema: dict | None = None, images=None) -> str:
        self.last_usage = None
        self.last_partial_response = None
        check_budget()
        if images:
            raise GenerationError('Live generation accepts ingestion-produced text evidence only')
        # Reserve space for the schema and response. Never silently cut evidence.
        estimated = ceil((len(prompt.encode('utf-8')) + len(json.dumps(schema or {}))) / 2.5)
        if estimated + self.max_output_tokens + 128 > settings.OLLAMA_CONTEXT_LENGTH:
            raise GenerationError('Request exceeds the local context budget')
        request = dict(model=self.model, messages=[{'role': 'user', 'content': prompt}],
                       stream=False, keep_alive='5m', options={
                           'num_ctx': settings.OLLAMA_CONTEXT_LENGTH,
                           'num_predict': self.max_output_tokens,
                           'temperature': settings.OLLAMA_TEMPERATURE,
                           'repeat_penalty': settings.OLLAMA_REPEAT_PENALTY,
                       })
        if schema is not None:
            request['format'] = schema
        started = perf_counter()
        # One resident model and one request at a time on the 8 GB development Mac.
        if not _inference_slots.acquire(blocking=False):
            self.usage_history.append({'status': 'rejected', 'queue_ms': 0.0, 'inference_ms': 0.0})
            raise GenerationError('Local model queue is full; please retry shortly')
        acquired = False
        inference_started = None
        usage = {'status': 'failed', 'queue_ms': 0.0, 'inference_ms': 0.0}
        try:
            acquired = acquire_with_budget(_inference_lock, self.timeout)
            usage['queue_ms'] = round((perf_counter() - started) * 1000, 1)
            if not acquired:
                raise GenerationError('Local model is busy; please retry shortly')
            remaining = remaining_seconds(self.timeout - (perf_counter() - started))
            if remaining <= 0:
                raise GenerationError('Local model request timed out')
            inference_started = perf_counter()
            with httpx.Client(timeout=httpx.Timeout(remaining, connect=min(5, remaining)),
                              trust_env=False) as client:
                response = client.post(settings.OLLAMA_URL + '/api/chat', json=request)
                response.raise_for_status()
                result = response.json()
            returned_model = result.get('model')
            if (not isinstance(returned_model, str)
                    or returned_model.removesuffix(':latest') != self.model.removesuffix(':latest')):
                raise GenerationError('Ollama returned a different model from the configured model')
            usage['inference_ms'] = round((perf_counter() - inference_started) * 1000, 1)
            self.last_usage = {key: result.get(key) for key in (
                'prompt_eval_count', 'eval_count', 'load_duration', 'prompt_eval_duration',
                'eval_duration', 'total_duration', 'done_reason')}
            usage.update(self.last_usage)
            check_budget()
            if not result.get('done') or result.get('done_reason') == 'length':
                self.last_partial_response = result.get('message', {}).get('content', '')
                raise GenerationError('Local model did not finish within the output budget')
            answer = result.get('message', {}).get('content', '').strip()
            if not answer:
                raise GenerationError('Local model returned an empty answer')
            if schema is not None:
                json.loads(answer)
            usage['status'] = 'completed'
            return answer
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            logger.warning('Local model request failed', exc_info=False)
            raise GenerationError('Local model is unavailable or returned an invalid response') from None
        finally:
            if inference_started is None:
                usage['queue_ms'] = round((perf_counter() - started) * 1000, 1)
            if inference_started is not None:
                usage['inference_ms'] = round((perf_counter() - inference_started) * 1000, 1)
            self.usage_history.append(usage)
            if acquired:
                _inference_lock.release()
            _inference_slots.release()

    def review_grounding(self, *, draft, question, sources, schema, images=None, context=None):
        """Optional bounded review; its failure must not erase a validated draft."""
        try:
            prompt = ('Check this draft against the question and its cited evidence. Keep natural supported '
                      'paraphrases and the useful direct answer. Remove unsupported factual clauses and '
                      'unrequested procedures/background. Correct any source IDs that do not support a claim. '
                      'A generic guide does not prove this car has a particular feature. Manufacturer instructions '
                      'take priority. Preserve conditions, precautions, printed labels and units. Do not add '
                      'remembered facts or rewrite merely for style. Keep the JSON envelope and valid media IDs. '
                      'The application handles outcome/routing. Return only the schema fields. Input:\n' + json.dumps(
                          dict(question=question, sources=sources, draft=draft), ensure_ascii=False))
            result = self.generate(prompt, schema=schema)
            self.last_review_status = 'completed'
            return result
        except (GenerationError, ValueError):
            self.last_review_status = 'unavailable'
            logger.warning('Optional grounding review unavailable; retaining draft for deterministic validation')
            return json.dumps(draft, ensure_ascii=False)
