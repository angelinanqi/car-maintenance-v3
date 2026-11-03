"""Private, revision-checked handoff for the Pass 3 RAG indexer."""
import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field, model_validator

from backend import db, settings
from backend.locks import content_lock
from backend.models import Document
from shared.models import InputModel
from backend.services.documents import now


def require_rag_service(request: Request):
    if not settings.RAG_SERVICE_TOKEN:
        raise HTTPException(503, "RAG service authentication is not configured.")
    supplied = request.headers.get("authorization", "")
    scheme, _, token = supplied.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token.encode(), settings.RAG_SERVICE_TOKEN.encode()):
        raise HTTPException(401, "Invalid service credentials.")


router = APIRouter(prefix="/internal/indexing", tags=["RAG integration"], dependencies=[Depends(require_rag_service)])


@router.get('/guides')
def list_guide_handoffs(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    from backend.services.guide_indexing import handoff, index_rows
    indexes = index_rows()
    categories = {row['id'] for row in db.all_rows('guide_categories', published=True)}
    return [handoff(guide, indexes.get(guide['id']), category_published=(
        not guide.get('category_id') or guide['category_id'] in categories))
        for guide in db.list_rows('guides', offset=offset, limit=limit)]


@router.get('/guides/{guide_id}/extraction')
def guide_extraction(guide_id: UUID, source_revision: UUID):
    from backend.services.guide_indexing import prepare
    data = prepare(db.get('guides', guide_id), source_revision)
    return Response(data, media_type='application/zip', headers={'X-Content-Type-Options': 'nosniff'})


class IndexResult(InputModel):
    source_revision: UUID
    status: Literal["indexed", "failed"]
    chunk_count: int = Field(default=0, ge=0, le=2147483647)
    error: str | None = Field(default=None, max_length=2000)
    warnings: list[str] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def check_result(self):
        if self.status == "indexed" and (self.chunk_count < 1 or self.error):
            raise ValueError("Successful indexing requires a positive chunk count and no error")
        if self.status == "failed" and not self.error:
            raise ValueError("Failed indexing requires an error message")
        return self


@router.post('/guides/{guide_id}/result')
def confirm_guide_indexing(guide_id: UUID, result: IndexResult):
    return confirm_content_indexing(guide_id, result)


@router.get('/emergency')
def list_emergency_handoffs(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    from backend.services.guide_indexing import handoff, index_rows
    indexes = index_rows(emergency=True)
    return [handoff(row, indexes.get(row['id']), emergency=True)
            for row in db.list_rows('emergency_playbooks', offset=offset, limit=limit)]


@router.get('/emergency/{playbook_id}/extraction')
def emergency_extraction(playbook_id: UUID, source_revision: UUID):
    from backend.services.guide_indexing import prepare
    return Response(prepare(db.get('emergency_playbooks', playbook_id), source_revision, emergency=True),
                    media_type='application/zip', headers={'X-Content-Type-Options': 'nosniff'})


@router.post('/emergency/{playbook_id}/result')
def confirm_emergency_indexing(playbook_id: UUID, result: IndexResult):
    return confirm_content_indexing(playbook_id, result, emergency=True)


def confirm_content_indexing(guide_id, result, *, emergency=False):
    from backend.services.guide_indexing import source_revision, current
    from backend.services.guide_indexing import content_revision, eligible
    table = 'emergency_indexes' if emergency else 'guide_indexes'
    with content_lock(('playbook:' if emergency else 'guide:') + str(guide_id)):
        guide = db.get('emergency_playbooks' if emergency else 'guides', guide_id)
        rows = db.all_rows(table, id=str(guide_id))
        index = rows[0] if rows else None
        if not eligible(guide, emergency) or str(result.source_revision) != source_revision(guide, index, emergency=emergency):
            raise HTTPException(409, 'Stale guide indexing result.')
        if current(guide, index, emergency=emergency):
            if result.status != 'indexed' or result.chunk_count != index['chunk_count']:
                raise HTTPException(409, 'This guide revision is already indexed.')
            return {'status': 'processed'}
        matching = bool(index and index.get('content_hash') == content_revision(guide, emergency)
                        and index['source_revision'] == str(result.source_revision))
        if result.status == 'indexed' and not (matching and index.get('extraction_storage_path')):
            raise HTTPException(409, 'Prepare this guide before confirming indexing.')
        values = dict(id=str(guide_id), content_hash=content_revision(guide, emergency), source_revision=str(result.source_revision),
                      status='processed' if result.status == 'indexed' else 'failed', error=result.error,
                      chunk_count=result.chunk_count, indexed_at=now() if result.status == 'indexed' else None)
        if not matching:
            values.update(extraction_storage_path=None, media=[], videos=[], warnings=[])
        if result.warnings:
            values['warnings'] = list(dict.fromkeys([*(index.get('warnings', []) if matching else []), *result.warnings]))
        db.client().table(table).upsert(values).execute()
        if not matching and index and index.get('extraction_storage_path'):
            db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove([index['extraction_storage_path']])
        return {'status': values['status']}


@router.get("/documents", response_model=list[Document])
def list_handoffs(pending_only: bool = True, offset: int = Query(0, ge=0),
                  limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    # pending_only=false is also the reconciliation catalogue for remote deletions/replacements.
    return db.list_rows("documents", offset=offset, limit=limit,
                        **({"status": "awaiting_index"} if pending_only else {}))


@router.get("/documents/{document_id}/extraction")
def get_extraction(document_id: UUID, source_revision: UUID):
    with content_lock(document_id):
        row = db.get("documents", document_id)
        if str(source_revision) != row["source_revision"] or row["status"] not in {"awaiting_index", "processed"}:
            raise HTTPException(409, "This extraction revision is no longer available.")
        if not row.get("extraction_storage_path"):
            raise HTTPException(409, "Process this document before requesting its extraction.")
        data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(row["extraction_storage_path"])
    return Response(data, media_type="application/zip", headers={"X-Content-Type-Options": "nosniff"})


@router.post("/documents/{document_id}/result", response_model=Document)
def confirm_indexing(document_id: UUID, result: IndexResult):
    with content_lock(document_id):
        row = db.get("documents", document_id)
        if str(result.source_revision) != row["source_revision"] or row["status"] not in {"awaiting_index", "processed"}:
            raise HTTPException(409, "Stale indexing result. Fetch the current document revision.")
        if not row.get("extraction_storage_path"):
            raise HTTPException(409, "The document has no completed extraction.")
        if row["status"] == "processed":
            # Successful acknowledgements are idempotent; a late failure cannot undo success.
            if result.status != "indexed" or row["chunk_count"] != result.chunk_count:
                raise HTTPException(409, "This revision already has a successful indexing confirmation.")
            return row
        if result.status == "failed":
            return db.update("documents", document_id, {"error": result.error})
        timestamp = now()
        return db.update("documents", document_id, dict(status="processed", error=None,
            chunk_count=result.chunk_count, indexed_revision=str(result.source_revision), indexed_at=timestamp,
            processed_at=timestamp))
