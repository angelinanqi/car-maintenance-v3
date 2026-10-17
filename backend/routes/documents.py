import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import ValidationError
from urllib.parse import quote

from backend import auth, db
from backend.models import Document, DocumentEdit, DocumentPatch, ProcessBatch, ProcessResult, ReviewConfirmation
from backend.services import documents
from backend import settings

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=list[Document], dependencies=[Depends(auth.require_admin)])
def list_documents(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("documents", offset=offset, limit=limit)


@router.post("", response_model=Document, status_code=201, dependencies=[Depends(auth.require_admin)])
def upload_document(file: UploadFile = File(...), name: str = Form(...), tags: str = Form("[]"), document_type: str = Form("other_reference")):
    try:
        metadata = DocumentEdit(name=name, tags=json.loads(tags), document_type=document_type)
    except (ValueError, ValidationError):
        raise HTTPException(422, "Provide a name, valid document type, and tags as a JSON string array.") from None
    return documents.create(file, metadata.model_dump())


@router.post("/process-batch", response_model=list[ProcessResult], response_model_exclude_none=True, dependencies=[Depends(auth.require_admin)])
def process_batch(request: ProcessBatch, background: BackgroundTasks):
    if len(request.ids) > settings.DOCUMENT_BATCH_LIMIT:
        raise HTTPException(422, "Too many documents in one processing batch.")
    results = []
    for document_id in dict.fromkeys(request.ids):
        try:
            row, queued = documents.queue(document_id, request.force)
            if queued:
                background.add_task(documents.process, str(document_id))
            results.append({"id": str(document_id), "status": row["status"], "queued": queued})
        except HTTPException as error:
            results.append({"id": str(document_id), "error": error.detail})
        except Exception:
            logging.getLogger(__name__).exception("Could not queue document %s", document_id)
            results.append({"id": str(document_id), "error": "Could not queue document. Check backend logs and retry."})
    return results


@router.get("/{document_id}", response_model=Document, dependencies=[Depends(auth.require_admin)])
def get_document(document_id: UUID):
    return db.get("documents", document_id)


@router.patch("/{document_id}", response_model=Document, dependencies=[Depends(auth.require_admin)])
def edit_document(document_id: UUID, metadata: DocumentPatch):
    return documents.edit(document_id, metadata.model_dump(exclude_unset=True))


@router.delete("/{document_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_document(document_id: UUID):
    documents.delete(document_id)


@router.post("/{document_id}/replace", response_model=Document, dependencies=[Depends(auth.require_admin)])
def replace_document(document_id: UUID, file: UploadFile = File(...)):
    return documents.replace(document_id, file)


@router.post("/{document_id}/stage-replacement", response_model=Document, status_code=201, dependencies=[Depends(auth.require_admin)])
def stage_replacement(document_id: UUID, file: UploadFile = File(...)):
    with documents.document_lock(document_id):
        old = documents.editable(document_id)
        if old.get("superseded_by_id"):
            raise HTTPException(409, "Stage a replacement of the current document instead of a superseded source.")
        metadata = DocumentEdit(**{key: old[key] for key in DocumentEdit.model_fields if key in old}).model_dump()
        metadata["source_fidelity_verified"] = False
        metadata["replacement_for_id"] = str(document_id)
        new = documents.create(file, metadata)
        # Preserve completed upload on an association error, with an explicit error for recovery.
        try:
            for table, field in (("document_vehicles", "vehicle_id"), ("document_categories", "category_id")):
                for link in db.all_rows(table, document_id=str(document_id)):
                    db.insert(table, {"document_id": new["id"], field: link[field]})
        except Exception:
            db.update("documents", new["id"], {"error": "Replacement uploaded but associations need review. Assign its scopes before processing."})
            raise HTTPException(503, f"Replacement {new['id']} was uploaded, but scope copying failed. Review it in the document list before retrying.") from None
        return new


@router.post("/{document_id}/publish", response_model=Document, dependencies=[Depends(auth.require_admin)])
def publish_document(document_id: UUID, request: ReviewConfirmation):
    with documents.document_lock(document_id):
        row = documents.editable(document_id)
        if row.get("superseded_by_id"):
            raise HTTPException(409, "This document has been superseded. Publish a replacement of the current revision instead.")
        if row["status"] != "processed" or not row.get("indexed_revision") or row["indexed_revision"] != row["source_revision"] or row["chunk_count"] < 1:
            raise HTTPException(409, "Wait for confirmed indexing before publishing this document.")
        if not (db.all_rows("document_vehicles", document_id=str(document_id)) or db.all_rows("document_categories", document_id=str(document_id))):
            raise HTTPException(422, "Associate this document with a vehicle or category before publication.")
        result = db.client().rpc("publish_document", {"document_id": str(document_id)}).execute().data
        return result[0] if isinstance(result, list) else result


@router.get("/{document_id}/original", dependencies=[Depends(auth.require_admin)])
def original_document(document_id: UUID):
    row = db.get("documents", document_id)
    data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(row["storage_path"])
    return Response(data, media_type="application/pdf" if row["source_type"] == "pdf" else "text/plain", headers={
        "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline",
    })


@router.post("/{document_id}/process", response_model=Document, status_code=202, dependencies=[Depends(auth.require_admin)])
def process_document(document_id: UUID, background: BackgroundTasks, force: bool = False):
    row, queued = documents.queue(document_id, force)
    if queued:
        background.add_task(documents.process, str(document_id))
    return row


@router.get("/{document_id}/download")
def download_document(document_id: UUID, request: Request):
    row = db.get("documents", document_id)
    if not (row.get("mobile_visible", False) and row.get("published", False)):
        try:
            auth.require_draft_access(request)
        except HTTPException as error:
            if error.status_code in {401, 403}:
                raise HTTPException(404, "Record not found.") from None
            raise
    data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(row["storage_path"])
    mime = "application/pdf" if row["source_type"] == "pdf" else "text/markdown"
    return Response(data, media_type=mime, headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row["original_filename"], safe=""),
    })


@router.get("/{document_id}/extraction", dependencies=[Depends(auth.require_admin)])
def download_extraction(document_id: UUID):
    with documents.document_lock(document_id):
        row = db.get("documents", document_id)
        if not row.get("extraction_storage_path") or row["status"] not in {"awaiting_index", "processed"}:
            raise HTTPException(409, "Process this document before downloading its extraction.")
        data = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).download(row["extraction_storage_path"])
    return Response(data, media_type="application/zip", headers={
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="{document_id}-extraction.zip"',
    })
