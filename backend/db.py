"""Server-only Supabase access. No credentials are exposed to the browser."""
from functools import lru_cache
from math import ceil

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
            httpx_client=httpx.Client(http2=True, timeout=settings.SUPABASE_TIMEOUT),
        ),
    )


def get(table, record_id):
    rows = client().table(table).select("*").eq("id", str(record_id)).execute().data
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
    return query.range(offset, offset + limit - 1).execute().data


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
