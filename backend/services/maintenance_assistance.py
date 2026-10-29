"""Admin review state over existing extraction bundles and optional AI proposals."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import NAMESPACE_URL, uuid5
from zipfile import BadZipFile

from fastapi import HTTPException
from backend import db
from backend.services.source_assets import extraction
from shared.maintenance_extraction import VERSION, build_catalogue, extract_items, suggest_matches

TABLE = 'maintenance_assistance'


def current_document(document_id, revision, *, allow_superseded=False):
    document = db.get('documents', document_id)
    if document['source_revision'] != str(revision):
        raise HTTPException(409, 'The document revision changed. Reload its tables before reviewing.')
    if document.get('superseded_by_id') and not allow_superseded:
        raise HTTPException(409, 'This document has been superseded. Select its replacement.')
    return document


def inventory(document):
    if not document.get('extraction_storage_path'):
        return {'assistance_version': VERSION, 'document_id': document['id'],
                'source_revision': document['source_revision'], 'source_type': document['source_type'],
                'table_count': 0, 'tables': [], 'extraction_available': False}
    try:
        with extraction(document) as archive:
            manifest = json.loads(archive.read('elements.json'))
        if (manifest.get('document_id') != document['id']
                or manifest.get('source_revision') != document['source_revision']
                or manifest.get('source_type') != document['source_type']):
            raise HTTPException(409, 'Extraction elements do not match the selected source revision.')
        result = build_catalogue(manifest)
        result['extraction_available'] = True
        return result
    except (ValueError, KeyError, TypeError, AttributeError, BadZipFile, UnicodeError):
        raise HTTPException(422, 'The extraction cannot be read for maintenance assistance. Original documents and indexing are unchanged.') from None


def load(document):
    identity = str(uuid5(NAMESPACE_URL, 'maintenance-assistance:' + document['id'] + ':' + document['source_revision']))
    rows = db.all_rows(TABLE, id=identity)
    if rows:
        state = rows[0]
        if state['catalogue'].get('assistance_version') != VERSION or (
                not state['catalogue'].get('extraction_available') and document.get('extraction_storage_path')):
            state = db.update(TABLE, identity, {'catalogue': inventory(document), 'version': state['version'] + 1})
        return state
    return db.insert(TABLE, {'id': identity, 'document_id': document['id'],
        'source_revision': document['source_revision'], 'catalogue': inventory(document),
        'selections': [], 'suggestions': [], 'bookmarks': [], 'version': 1})


def check_version(state, expected):
    if state['version'] != expected:
        raise HTTPException(409, 'Another review changed this document. Reload before saving.')


def save(state, values, user_id):
    return db.update(TABLE, state['id'], {**values, 'version': state['version'] + 1,
        'reviewed_by': str(user_id), 'reviewed_at': datetime.now(timezone.utc).isoformat()})


def view(document, state):
    result = deepcopy(state)
    confirmed = {s['table_id'] for s in state['selections']}
    for table in result['catalogue']['tables']:
        table['review_status'] = 'confirmed' if table['table_id'] in confirmed else 'unreviewed'
    result['document_name'] = document['name']
    result['original_url'] = f"/admin/maintenance-assistance/documents/{document['id']}/original?source_revision={document['source_revision']}"
    result['source_type'] = document['source_type']
    return result


def confirm(state, selections, user_id):
    # Validate choices against authoritative cells before persisting confirmation.
    try:
        extract_items(state['catalogue'], {'document_id': state['document_id'],
            'source_revision': state['source_revision'], 'tables': selections})
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    old = {s['table_id']: s for s in state['selections']}
    unchanged = {s['table_id'] for s in selections if old.get(s['table_id']) == s}
    # Do not silently retain accepted items after changing their selected evidence.
    if any(s.get('status') == 'accepted' and s['table_id'] not in unchanged
           and not s.get('manual') for s in state['suggestions']):
        raise HTTPException(409, 'Accepted suggestions reference a changed selection. Mark them suggested or rejected before changing columns/tables.')
    kept = [s for s in state['suggestions'] if s.get('manual') or s['table_id'] in unchanged]
    return save(state, {'selections': selections, 'suggestions': kept}, user_id)


def generate(state, user_id):
    if not state['selections']:
        raise HTTPException(409, 'Confirm at least one detected table and its item columns first.')
    try:
        result = extract_items(state['catalogue'], {'document_id': state['document_id'],
            'source_revision': state['source_revision'], 'tables': state['selections']},
            db.all_rows('maintenance_items', active=True))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    existing = {s['suggestion_id']: s for s in state['suggestions'] if not s.get('ai_draft')}
    suggestions = []
    for suggestion in result['suggestions']:
        previous = existing.get(suggestion['suggestion_id'])
        if previous and all(previous[k] == suggestion[k] for k in ('original_text', 'columns')):
            for field in ('status', 'edited_name', 'mapped_item_id'):
                if field in previous:
                    suggestion[field] = previous[field]
        suggestions.append(suggestion)
    suggestions.extend(s for s in state['suggestions'] if s.get('manual') or s.get('ai_draft'))
    return save(state, {'suggestions': suggestions}, user_id)


def validate_mapping(item_id):
    if item_id is not None and not db.get('maintenance_items', item_id)['active']:
        raise HTTPException(422, 'Select an active standard maintenance item.')


def matches(name):
    return suggest_matches(name, db.all_rows('maintenance_items', active=True))
