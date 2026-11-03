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
    return {'X-Request-ID': value} if value else {}


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


async def request_monitor(request, call_next):
    # Trust only an opaque bounded correlation ID, never a header containing data.
    incoming = request.headers.get('X-Request-ID', '')
    identity = incoming if re.fullmatch(r'[a-fA-F0-9-]{32,36}', incoming) else str(uuid4())
    request.state.request_id = identity
    with context(request_id=identity):
        with span('http_request') as outcome:
            response = await call_next(request)
            if response.status_code >= 500:
                outcome['state'] = 'failed'
            route = request.scope.get('route')
            emit('http_response', 'failed' if response.status_code >= 500 else 'returned',
                 level='ERROR' if response.status_code >= 500 else 'INFO',
                 status_code=response.status_code, method=request.method,
                 route=getattr(route, 'path', 'unmatched'))
            response.headers['X-Request-ID'] = identity
            return response
