"""Revision-checked admin endpoints for maintenance extraction review."""
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from backend import auth, db, settings
from backend.locks import content_lock
from shared.models import InputModel
from backend.services import maintenance_assistance as service, rag_client, schedule_drafting
from shared.schedule_drafting import Action, DraftRule

router = APIRouter(prefix='/admin/maintenance-assistance', tags=['Maintenance assistance'],
                   dependencies=[Depends(auth.require_admin)])
Index = Annotated[int, Field(strict=True, ge=0)]
# The schedule opens its preview and review data concurrently. Queue these reads
# briefly while preserving the document lock for lazy review initialization and
# source replacement/deletion. Stay below the admin client's 30-second deadline.
READ_LOCK_TIMEOUT = 10


class Edit(InputModel):
    source_revision: UUID
    version: int = Field(ge=1)


class TableSelection(InputModel):
    table_id: str = Field(pattern=r'^table-\d{5,}$', max_length=80)
    confirmed: Literal[True]
    columns: list[Index] = Field(min_length=1, max_length=100)
    excluded_rows: list[Index] = Field(default_factory=list, max_length=10000)


class Confirmation(Edit):
    tables: list[TableSelection] = Field(max_length=100)


class SuggestionEdit(Edit):
    status: Literal['suggested', 'accepted', 'rejected']
    edited_name: str = Field(min_length=1, max_length=500)
    mapped_item_id: UUID | None = None


class GenerateScheduleDraft(Edit):
    vehicle_id: UUID
    table_id: str = Field(pattern=r'^table-\d{5,}$', max_length=80)
    replace_existing: bool = Field(default=False, strict=True)


class ScheduleDraftEdit(SuggestionEdit):
    action: Action | None = None
    rule: DraftRule | None = None
    source_page: int | None = Field(default=None, ge=1)
    confirm_review: bool = Field(default=False, strict=True)


class Bookmark(Edit):
    title: str = Field(min_length=1, max_length=500)
    page: int | None = Field(default=None, ge=1)
    section: str = Field(default='', max_length=500)
    notes: str = Field(default='', max_length=4000)


class ManualItem(Edit):
    table_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=500)
    mapped_item_id: UUID | None = None


def context(document_id, revision, version=None):
    document = service.current_document(document_id, revision)
    state = service.load(document)
    if version is not None:
        service.check_version(state, version)
    return document, state


@router.get('/documents')
def documents(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    # Discovery is lightweight and does not download every document's archive.
    rows = db.list_rows('documents', offset=offset, limit=limit)
    return [{'document_id': d['id'], 'source_revision': d['source_revision'],
             'name': d['name'], 'source_type': d['source_type'], 'status': d['status'],
             'extraction_available': bool(d.get('extraction_storage_path')),
             'superseded_by_id': d.get('superseded_by_id')} for d in rows]


@router.get('/matches')
def matches(name: str = Query(min_length=1, max_length=500)):
    return service.matches(name)


@router.get('/documents/{document_id}')
def detail(document_id: UUID, source_revision: UUID):
    with content_lock(document_id, timeout=READ_LOCK_TIMEOUT):
        document, state = context(document_id, source_revision)
        return service.view(document, state)


@router.get('/documents/{document_id}/tables')
def tables(document_id: UUID, source_revision: UUID, q: str = Query('', max_length=200),
           classification: Literal['likely', 'possible', 'other'] | None = None,
           offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    with content_lock(document_id, timeout=READ_LOCK_TIMEOUT):
        document, state = context(document_id, source_revision)
        rows = service.view(document, state)['catalogue']['tables']
        if classification:
            rows = [t for t in rows if t['ranking']['classification'] == classification]
        if q.strip():
            term = q.strip().casefold()
            rows = [t for t in rows if term in (t['title'] + ' ' + t['source'].get('description', '')
                    + ' ' + ' '.join(c['text'] for c in t['source'].get('cells', []))).casefold()]
        return {'document_id': str(document_id), 'source_revision': str(source_revision),
                'version': state['version'], 'total': len(rows), 'tables': rows[offset:offset + limit],
                'bookmarks': state['bookmarks'], 'original_url': service.view(document, state)['original_url']}


@router.get('/documents/{document_id}/original')
def original(document_id: UUID, source_revision: UUID):
    with content_lock(document_id, timeout=READ_LOCK_TIMEOUT):
        # Historical schedules retain their immutable originals after replacement.
        document = service.current_document(document_id, source_revision, allow_superseded=True)
        data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(document['storage_path'])
    return Response(data, media_type='application/pdf' if document['source_type'] == 'pdf' else 'text/plain',
                    headers={'Content-Disposition': 'inline', 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})


@router.put('/documents/{document_id}/confirmation')
def confirm(document_id: UUID, request: Confirmation, identity=Depends(auth.require_admin)):
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        updated = service.confirm(state, [s.model_dump() for s in request.tables], identity['user']['id'])
        return service.view(document, updated)


@router.post('/documents/{document_id}/suggestions')
def generate(document_id: UUID, request: Edit, identity=Depends(auth.require_admin)):
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        return service.view(document, service.generate(state, identity['user']['id']))


@router.get('/documents/{document_id}/suggestions')
def suggestions(document_id: UUID, source_revision: UUID,
                status: Literal['suggested', 'accepted', 'rejected'] | None = None,
                offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    with content_lock(document_id, timeout=READ_LOCK_TIMEOUT):
        _, state = context(document_id, source_revision)
        rows = state['suggestions']
        if status:
            rows = [s for s in rows if s['status'] == status]
        return {'document_id': str(document_id), 'source_revision': str(source_revision),
                'version': state['version'], 'total': len(rows), 'suggestions': rows[offset:offset + limit]}


@router.post('/documents/{document_id}/schedule-draft')
async def generate_schedule_draft(document_id: UUID, request: GenerateScheduleDraft, identity=Depends(auth.require_admin)):
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        payload = schedule_drafting.prepare(document, state, request.vehicle_id, request.table_id, request.replace_existing)
    # Generation can take time. Keep the document usable, then reject stale results.
    result = await rag_client.draft_schedule(payload)
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        schedule_drafting.prepare(document, state, request.vehicle_id, request.table_id, request.replace_existing)
        updated = schedule_drafting.save_generated(state, payload, result, identity['user']['id'])
        return service.view(document, updated)


@router.patch('/documents/{document_id}/schedule-draft/{suggestion_id}')
def review_schedule_draft(document_id: UUID, suggestion_id: str, request: ScheduleDraftEdit,
                          identity=Depends(auth.require_admin)):
    with content_lock('schedule-sources'), content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        updated = schedule_drafting.review_row(document, state, suggestion_id, request, identity['user']['id'])
        return service.view(document, updated)


@router.patch('/documents/{document_id}/suggestions/{suggestion_id}')
def review(document_id: UUID, suggestion_id: str, request: SuggestionEdit, identity=Depends(auth.require_admin)):
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        item = next((s for s in state['suggestions'] if s['suggestion_id'] == suggestion_id), None)
        if item is None:
            raise HTTPException(404, 'Suggestion not found in this document revision.')
        if item.get('ai_draft'):
            raise HTTPException(422, 'Review the AI schedule row with its action, interval and source before accepting it.')
        service.validate_mapping(request.mapped_item_id)
        item.update(status=request.status, edited_name=request.edited_name,
                    mapped_item_id=str(request.mapped_item_id) if request.mapped_item_id else None)
        return service.view(document, service.save(state, {'suggestions': state['suggestions']}, identity['user']['id']))


@router.post('/documents/{document_id}/bookmarks', status_code=201)
def bookmark(document_id: UUID, request: Bookmark, identity=Depends(auth.require_admin)):
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        if document['source_type'] == 'pdf' and request.page is None:
            raise HTTPException(422, 'A manual PDF bookmark requires a page.')
        if document['source_type'] == 'md' and (request.page is not None or not request.section):
            raise HTTPException(422, 'A Markdown bookmark requires a section and no PDF page.')
        if len(state['bookmarks']) >= 500:
            raise HTTPException(422, 'This revision already has 500 manual bookmarks.')
        entry = {'table_id': 'manual-' + str(uuid4()), 'document_id': str(document_id),
                 'source_revision': str(request.source_revision), 'manual': True,
                 **request.model_dump(exclude={'source_revision', 'version'})}
        return service.view(document, service.save(state, {'bookmarks': [*state['bookmarks'], entry]}, identity['user']['id']))


@router.post('/documents/{document_id}/manual-items', status_code=201)
def manual_item(document_id: UUID, request: ManualItem, identity=Depends(auth.require_admin)):
    with content_lock(document_id):
        document, state = context(document_id, request.source_revision, request.version)
        allowed = {b['table_id'] for b in state['bookmarks']} | {s['table_id'] for s in state['selections']}
        if request.table_id not in allowed:
            raise HTTPException(422, 'Choose a manual bookmark or confirmed table from this revision.')
        if len(state['suggestions']) >= 10000:
            raise HTTPException(422, 'Too many suggestions in this revision.')
        service.validate_mapping(request.mapped_item_id)
        entry = {'suggestion_id': 'manual-' + str(uuid4()), 'manual': True,
                 'document_id': str(document_id), 'source_revision': str(request.source_revision),
                 'table_id': request.table_id, 'original_text': None, 'suggested_name': request.name,
                 'edited_name': request.name, 'status': 'suggested',
                 'mapped_item_id': str(request.mapped_item_id) if request.mapped_item_id else None,
                 'uncertainty': ['manually_entered'], 'catalogue_matches': service.matches(request.name)}
        return service.view(document, service.save(state, {'suggestions': [*state['suggestions'], entry]}, identity['user']['id']))
