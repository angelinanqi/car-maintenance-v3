"""Serialize conflicting mutations within the single backend process."""
from contextlib import contextmanager
from threading import Lock
from fastapi import HTTPException

_locks = {}
_guard = Lock()


@contextmanager
def content_lock(record_id):
    with _guard:
        lock = _locks.setdefault(str(record_id), Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "This record is busy. Please retry after the current operation finishes.")
    try:
        yield
    finally:
        lock.release()
