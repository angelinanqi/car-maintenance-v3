"""Serialize conflicting mutations within the single backend process."""
from contextlib import contextmanager
from threading import Lock
from fastapi import HTTPException

_locks = {}
_guard = Lock()


@contextmanager
def content_lock(record_id, *, timeout=0):
    """Fail fast for mutations; reads may allow a bounded wait for other readers."""
    with _guard:
        lock = _locks.setdefault(str(record_id), Lock())
    if not lock.acquire(timeout=timeout):
        raise HTTPException(409, "This record is busy. Please retry after the current operation finishes.")
    try:
        yield
    finally:
        lock.release()
