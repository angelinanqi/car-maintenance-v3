"""Validation and ownership checks for private mobile records."""
from fastapi import HTTPException
from backend import db


def valid_id(value):
    if not value or len(value) > 200 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-' for c in value):
        raise HTTPException(422, 'Invalid personal record identifier.')
    return value


def owned(table, user_id, record_id, *, optional=False):
    rows = db.all_rows(table, user_id=str(user_id), id=valid_id(record_id))
    if not rows and not optional:
        raise HTTPException(404, 'Record not found.')
    return rows[0] if rows else None


def put(table, user_id, record_id, values):
    return db.client().table(table).upsert(
        {**values, 'id': valid_id(record_id), 'user_id': str(user_id)}, on_conflict='user_id,id').execute().data[0]
