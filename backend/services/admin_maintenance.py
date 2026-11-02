"""Safe retries and version checks for shared maintenance administration."""
from datetime import datetime
from fastapi import HTTPException
from postgrest.exceptions import APIError
from backend import db


def existing_create(table, record_id, values):
    if record_id is None:
        return None
    rows = db.all_rows(table, id=str(record_id))
    if not rows:
        return None
    row = rows[0]
    if any(row.get(key) != value for key, value in values.items()):
        raise HTTPException(409, 'This create request was already saved with different content. Your entries are kept. Reload the saved record before continuing.')
    return row


def create_once(table, record_id, values):
    previous = existing_create(table, record_id, values)
    if previous:
        return previous
    payload = {**values, **({'id': str(record_id)} if record_id else {})}
    try:
        return db.insert(table, payload)
    except APIError as error:
        if error.code != '23505':
            raise
        previous = existing_create(table, record_id, values)
        if previous:
            return previous
        raise HTTPException(409, 'A record with this identity already exists. Your entries are kept. Refresh the list and open the existing record.') from None


def check_revision(row, expected):
    if expected is None or datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) != expected:
        raise HTTPException(409, 'This schedule changed. Your edits are kept. Reload and review the latest saved version before continuing.')


def change_schedule(row, expected, values=None, *, delete=False):
    check_revision(row, expected)
    query = db.client().table('manufacturer_schedules')
    query = query.delete() if delete else query.update(values)
    rows = (query.eq('id', row['id']).eq('updated_at', row['updated_at'])
            .eq('status', row['status']).execute().data)
    if not rows:
        raise HTTPException(409, 'This schedule changed. Your edits are kept. Reload and review the latest saved version before continuing.')
    return rows[0]
