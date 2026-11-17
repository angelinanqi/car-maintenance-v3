"""Local, best-effort observability. Never serialize call arguments or exception text."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import inspect
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import socket
import threading
import time
import traceback
from uuid import uuid4

_context = ContextVar('observation', default={})
_outcome = ContextVar('observation_outcome', default=None)
_lock = threading.RLock()
_active = {}
_handler = None
_service = 'unknown'
_stop = threading.Event()
_started = False
_state = 'starting'


def log_directory():
    root = Path(__file__).resolve().parents[1]
    path = Path(os.getenv('MONITOR_LOG_DIR') or root / 'output/logs/monitor')
    return path if path.is_absolute() else root / path


def enabled():
    return os.getenv('MONITOR_ENABLED', '1').lower() not in {'0', 'false', 'off'}


def emit(stage, state, *, level='INFO', **fields):
    if not enabled() or _handler is None:
        return
    minimum = logging.getLevelNamesMapping().get(os.getenv('MONITOR_LOG_LEVEL', 'INFO').upper(), logging.INFO)
    if stage != 'service' and logging.getLevelNamesMapping().get(level, logging.INFO) < minimum:
        return
    # Call sites supply only IDs, fixed labels, counts and timings. No payloads.
    event = dict(timestamp=datetime.now(timezone.utc).isoformat(), time=time.time(),
                 machine=socket.gethostname(), service=_service, pid=os.getpid(),
                 module=fields.pop('module', 'shared.observability'), stage=stage,
                 state=state, level=level, message=f'{stage}: {state}', **_context.get())
    event.update(fields)
    try:
        record = logging.LogRecord('monitor', getattr(logging, level), '', 0,
                                   json.dumps(event, ensure_ascii=True), (), None)
        _handler.handle(record)
    except Exception:
        pass  # Telemetry must never fail an application operation.


class SafeDiagnostics(logging.Handler):
    def emit(self, record):
        # Legacy messages can contain prompts, URLs and SDK response bodies.
        # Keep the module, severity and stack locations, never their values.
        fields = {'module': record.name, 'source': f'{Path(record.pathname).name}:{record.lineno}'}
        if record.exc_info and record.exc_info[1]:
            fields.update(error_type=type(record.exc_info[1]).__name__,
                          frames=[f'{Path(f.filename).name}:{f.lineno}:{f.name}'
                                  for f in traceback.extract_tb(record.exc_info[2])][-12:])
        emit('diagnostic', 'reported', level=record.levelname, **fields)


def configure(service):
    global _handler, _service, _started
    if not enabled() or _started:
        return
    _started = True
    _service = service
    try:
        directory = log_directory()
        directory.mkdir(parents=True, exist_ok=True)
        _handler = RotatingFileHandler(directory / f'{service}-{os.getpid()}.jsonl',
                                      maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    except OSError:
        _handler = None
        logging.getLogger(__name__).warning('Monitoring files unavailable; continuing without telemetry')
        return
    # Cleanup is best effort; an inaccessible old file must not disable new logs.
    for path in directory.glob('*.jsonl*'):
        try:
            if path.stat().st_mtime < time.time() - 7 * 86400:
                path.unlink(missing_ok=True)
        except OSError:
            pass
    for name in ('backend', 'rag'):
        logger = logging.getLogger(name)
        logger.addHandler(SafeDiagnostics(level=logging.getLevelNamesMapping().get(os.getenv('MONITOR_LOG_LEVEL', 'INFO').upper(), logging.INFO)))
        logger.setLevel(logging.DEBUG if os.getenv('MONITOR_LOG_LEVEL', '').upper() == 'DEBUG' else logging.INFO)
    emit('service', 'starting')

    def heartbeat():
        while not _stop.wait(5):
            with _lock:
                operations = list(_active.values())
            emit('service', _state, operations=operations)
    threading.Thread(target=heartbeat, name='monitor-heartbeat', daemon=True).start()


def ready():
    global _state
    _state = 'running'
    emit('service', 'running')


def shutdown():
    _stop.set()
    emit('service', 'stopped')


def correlation_headers():
    value = _context.get().get('request_id')
    return {'X-Client-Source': 'INTERNAL', **({'X-Request-ID': value} if value else {})}


@contextmanager
def context(**fields):
    token = _context.set({**_context.get(), **fields})
    try:
        yield
    finally:
        _context.reset(token)


def mark_outcome(state):
    outcome = _outcome.get()
    if outcome is not None:
        outcome['state'] = state


@contextmanager
def span(stage, *, module='shared.observability', **fields):
    if not enabled() or _handler is None:
        yield {}
        return
    identity = uuid4().hex
    start = time.monotonic()
    with context(**fields, span_id=identity, parent_id=_context.get().get('span_id')):
        operation = dict(_context.get(), stage=stage, module=module, started=time.time())
        with _lock:
            _active[identity] = operation
        emit(stage, 'started', module=module)
        outcome = {}
        outcome_token = _outcome.set(outcome)
        try:
            yield outcome
        except BaseException as error:
            emit(stage, 'cancelled' if isinstance(error, (KeyboardInterrupt, SystemExit)) or type(error).__name__ in {'CancelledError', 'ProcessingStopped'} else 'failed',
                 module=module, level='ERROR', error_type=type(error).__name__,
                 frames=[f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in traceback.extract_tb(error.__traceback__)][-12:],
                 duration_ms=round((time.monotonic() - start) * 1000, 1))
            raise
        else:
            state = outcome.get('state', 'completed')
            emit(stage, state, level='ERROR' if state == 'failed' else 'WARNING' if state == 'deferred' else 'INFO', module=module, duration_ms=round((time.monotonic() - start) * 1000, 1))
        finally:
            _outcome.reset(outcome_token)
            with _lock:
                _active.pop(identity, None)


def observed(stage, *, job_arg=None, job_key=None, failure_field=None, failure_values=()):
    """Instrument functions without inspecting/logging their private arguments."""
    def decorate(fn):
        signature = inspect.signature(fn)
        def fields(args, kwargs):
            if not job_arg:
                return {}
            value = signature.bind_partial(*args, **kwargs).arguments.get(job_arg)
            if job_key and isinstance(value, dict):
                value = value.get(job_key)
            return {'job_id': str(value)} if value is not None else {}
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def wrapped(*args, **kwargs):
                if not enabled() or _handler is None:
                    return await fn(*args, **kwargs)
                with span(stage, module=fn.__module__, **fields(args, kwargs)) as outcome:
                    result = await fn(*args, **kwargs)
                    if failure_field and isinstance(result, dict) and result.get(failure_field) in failure_values:
                        outcome['state'] = 'failed'
                    return result
        else:
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if not enabled() or _handler is None:
                    return fn(*args, **kwargs)
                with span(stage, module=fn.__module__, **fields(args, kwargs)):
                    return fn(*args, **kwargs)
        return wrapped
    return decorate


def safe_path(path):
    """Keep fixed endpoint names, never arbitrary IDs, filenames or query values."""
    static = set(('api backend v1 auth token logout signup recover verify user health docs config '
        'accounts me admin documents guides categories emergency playbooks contacts dashboard '
        'knowledge vehicles manufacturers models catalogue maintenance-items maintenance-intervals '
        'schedules schedule-drafts maintenance-assistance mobile tasks records incidents plans '
        'service-plans preview bookmarks notes saved-items chat sessions resume activity sources '
        'image original pages media upload process extraction review publish unpublish coverage '
        'tags removal-impact archive restore delete-impact deactivate index indexing youtube '
        'channels videos sync status questions runs tests document-test-summaries chat-starters '
        'companion-settings companion progress recap recaps nearby workshops mechanic-questions '
        'configuration scopes categories profiles schedule-draft assets internal handoffs pending '
        'index-ready index-failed confirm-corrections corrections content').split())
    parts = str(path).split('?', 1)[0].split('#', 1)[0].split('/')
    return '/'.join(part if part in static or not part else ':id' for part in parts)[:240] or '/'


def record_http_response(request, status, *, error_type=None):
    """One completed HTTP event; diagnostics must never change the response."""
    try:
        if getattr(request.state, 'http_logged', False):
            return
        request.state.http_logged = True
        source = request.headers.get('X-Client-Source', '').upper()
        source = source if source in {'WEB', 'MOBILE', 'INTERNAL'} else 'UNKNOWN'
        session = request.headers.get('X-Client-Session', '')
        session = session if re.fullmatch(r'(?:guest|auth)-[a-f0-9]{16}', session) else None
        route = request.scope.get('route')
        fields = dict(request_id=request.state.request_id, client_source=source,
                      method=request.method, route=safe_path(getattr(route, 'path', request.url.path)),
                      status_code=status, outcome='ERROR' if status >= 400 else 'SUCCESS',
                      duration_ms=round((time.monotonic() - request.state.http_started) * 1000, 1))
        if session:
            fields['client_session'] = session
        if error_type:
            fields['error_type'] = error_type
        emit('http_response', 'failed' if status >= 400 else 'returned',
             level='ERROR' if status >= 500 else 'WARNING' if status >= 400 else 'INFO', **fields)
    except Exception:
        pass


async def request_monitor(request, call_next):
    # Trust only an opaque bounded correlation ID, never a header containing data.
    incoming = request.headers.get('X-Request-ID', '')
    identity = incoming if re.fullmatch(r'[a-fA-F0-9-]{32,36}', incoming) else str(uuid4())
    request.state.request_id = identity
    request.state.http_started = time.monotonic()
    with context(request_id=identity):
        with span('http_request') as outcome:
            response = await call_next(request)
            if response.status_code >= 500:
                outcome['state'] = 'failed'
            record_http_response(request, response.status_code)
            response.headers['X-Request-ID'] = identity
            return response
