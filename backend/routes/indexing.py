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


class IndexResult(InputModel):
    source_revision: UUID
    status: Literal["indexed", "failed"]
    chunk_count: int = Field(default=0, ge=0, le=2147483647)
    error: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_result(self):
        if self.status == "indexed" and (self.chunk_count < 1 or self.error):
            raise ValueError("Successful indexing requires a positive chunk count and no error")
        if self.status == "failed" and not self.error:
            raise ValueError("Failed indexing requires an error message")
        return self


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
