"""Server-only Supabase access. No credentials are exposed to the browser."""
from functools import lru_cache
from math import ceil
import time

import httpx
from fastapi import HTTPException
from supabase import create_client
from supabase.client import ClientOptions

from backend import settings


@lru_cache
def client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503, "Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY on the backend.")
    return create_client(
        settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY,
        options=ClientOptions(
            auto_refresh_token=False, persist_session=False,
            postgrest_client_timeout=settings.SUPABASE_TIMEOUT,
            storage_client_timeout=ceil(settings.SUPABASE_TIMEOUT),
            # Isolate concurrent uploads, Auth checks and database reads instead
            # of sharing HTTP/2 streams that can all fail on one connection reset.
            httpx_client=httpx.Client(http2=False, timeout=settings.SUPABASE_TIMEOUT),
        ),
    )


def read_rows(query):
    # Retrying a read is safe when a pooled connection closes unexpectedly.
    # Writes stay explicit: a lost response does not establish whether they ran.
    for attempt in range(3):
        try:
            return query.execute().data
        except httpx.TransportError:
            if attempt == 2:
                raise
            time.sleep(0.2 * (attempt + 1))


def get(table, record_id):
    rows = read_rows(client().table(table).select("*").eq("id", str(record_id)))
    if not rows:
        raise HTTPException(404, "Record not found.")
    return rows[0]


def list_rows(table, *, offset=0, limit=None, order_by=("created_at", "id"), **filters):
    limit = limit or settings.API_PAGE_SIZE
    query = client().table(table).select("*")
    for field in order_by:
        query = query.order(field)
    for field, value in filters.items():
        query = query.in_(field, value) if isinstance(value, list) else query.eq(field, value)
    return read_rows(query.range(offset, offset + limit - 1))


def all_rows(table, **filters):
    rows = []
    while True:
        page = list_rows(table, offset=len(rows), **filters)
        rows.extend(page)
        if len(page) < settings.API_PAGE_SIZE:
            return rows


def insert(table, values):
    return client().table(table).insert(values).execute().data[0]


def update(table, record_id, values):
    rows = client().table(table).update(values).eq("id", str(record_id)).execute().data
    if not rows:
        raise HTTPException(404, "Record not found.")
    return rows[0]


def delete(table, record_id):
    get(table, record_id)
    client().table(table).delete().eq("id", str(record_id)).execute()


def bucket(name):
    return client().storage.from_(name)
