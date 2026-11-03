"""Manage labels on existing documents without a separate tag catalogue."""
import logging
from fastapi import HTTPException
from pydantic import Field, field_validator
from backend import db
from backend.locks import content_lock
from backend.services import documents
from shared.models import InputModel
from shared.document_tags import clean_tag, tag_key, normalize_tags

logger = logging.getLogger(__name__)


class TagChange(InputModel):
    tag: str = Field(min_length=1)
    replacement: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator('tag', 'replacement')
    @classmethod
    def valid_label(cls, value):
        if value is None:
            return value
        value = clean_tag(value)
        if not value:
            raise ValueError('Enter a non-empty tag.')
        return value


def summary():
    labels = {}
    for row in db.all_rows('documents'):
        for tag in normalize_tags(row.get('tags', [])):
            key = tag_key(tag)
            label = labels.setdefault(key, {'name': tag, 'count': 0})
            label['count'] += 1
    return sorted(labels.values(), key=lambda label: tag_key(label['name']))


def change(request):
    updated, failed = [], []
    key = tag_key(request.tag)
    with content_lock('document-tags'):
        candidates = [row for row in db.all_rows('documents')
                      if any(tag_key(tag) == key for tag in row.get('tags', []))]
        for candidate in candidates:
            identity = {'id': candidate['id'], 'name': candidate['name']}
            try:
                # Read again under the same locks used by document edits, so a
                # tag change preserves labels added after the initial listing.
                with content_lock('schedule-sources'), content_lock(candidate['id']):
                    row = documents.editable(candidate['id'])
                    if not any(tag_key(tag) == key for tag in row.get('tags', [])):
                        continue  # Already changed, e.g. a retry after a lost acknowledgement.
                    tags = [request.replacement if tag_key(tag) == key else tag
                            for tag in row.get('tags', [])
                            if tag_key(tag) != key or request.replacement is not None]
                    db.update('documents', candidate['id'], {'tags': normalize_tags(tags)})
                updated.append(identity)
            except HTTPException as error:
                failed.append({**identity, 'error': error.detail})
            except Exception:
                logger.exception('Could not confirm tag change for document %s', candidate['id'])
                failed.append({**identity, 'error': 'Could not confirm this change. Reload and retry.'})
    return {'updated': updated, 'failed': failed}
