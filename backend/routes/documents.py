import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import ValidationError, Field
from urllib.parse import quote
from zipfile import BadZipFile

from backend import auth, db
from backend.models import Document, DocumentEdit, DocumentPatch, ProcessBatch, ProcessResult, ReviewConfirmation
from backend.services import documents
from backend import settings
from backend.services.source_assets import extraction, element, image_bytes
from shared.models import InputModel
from shared.visual_identity import VisualIdentity
from shared.source_elements import ELEMENT_PATTERN, sanitize_table
from backend.services import review_questions

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
    with documents.document_lock("schedule-sources"), documents.document_lock(document_id):
        review_questions.check_document(document_id)
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


@router.get("/{document_id}/usage", dependencies=[Depends(auth.require_admin)])
def document_usage(document_id: UUID):
    return review_questions.document_usage(document_id)


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


@router.get("/{document_id}/review", dependencies=[Depends(auth.require_admin)])
def review_document(document_id: UUID, revision: UUID):
    """Show the prepared text and tables without making admins unpack an archive."""
    with documents.document_lock(document_id):
        row = db.get("documents", document_id)
        if row["source_revision"] != str(revision):
            raise HTTPException(409, "This document changed. Reload before checking it.")
        if not row.get("extraction_storage_path") or row["status"] not in {"awaiting_index", "processed"}:
            raise HTTPException(409, "The document is not ready to check yet.")
        try:
            with extraction(row) as archive:
                text = archive.read("document.md").decode("utf-8-sig")
                elements = json.loads(archive.read("elements.json"))["elements"]
                if not text.strip():
                    raise ValueError("No readable text")
        except (ValueError, KeyError, UnicodeError, BadZipFile):
            raise HTTPException(422, "The prepared document could not be opened. Try preparing it again.") from None
    tables = iter(record for record in elements if record["kind"] == "table")
    blocks = []
    position = 0
    for match in ELEMENT_PATTERN.finditer(text):
        if match.start() > position:
            blocks.append({"kind": "text", "text": text[position:match.start()]})
        original = match.group(0)
        if not original.lstrip().lower().startswith(("![", "<img")):
            table = next(tables, None)
            blocks.append({"kind": "table", "html": sanitize_table(table.get("html", "")) if table else "", "text": original})
        else:
            blocks.append({"kind": "image", "text": "Check this illustration in the original document."})
        position = match.end()
    if position < len(text):
        blocks.append({"kind": "text", "text": text[position:]})
    return {"document_id": str(document_id), "source_revision": row["source_revision"], "blocks": blocks}


class ImageReview(VisualIdentity):
    element_id: str = Field(pattern=r'^image-\d{5,}$')
    approved: bool
    title: str = Field(default='', max_length=200)


class ImageReviews(InputModel):
    source_revision: UUID
    reviews: list[ImageReview] = Field(min_length=1, max_length=1000)


@router.get('/{document_id}/visuals', dependencies=[Depends(auth.require_admin)])
def review_visuals(document_id: UUID, revision: UUID):
    with documents.document_lock(document_id):
        row = db.get('documents', document_id)
        if row['source_revision'] != str(revision):
            raise HTTPException(409, 'The source changed. Reload its images.')
        with extraction(row) as archive:
            records = json.loads(archive.read('elements.json'))['elements']
            return [{'element_id': e['element_id'], 'caption': e.get('caption', ''),
                     'section_path': e.get('section_path', []), 'pages': e.get('pages', []),
                     'review': e.get('identity_review'),
                     'generated_identity': e.get('generated_identity'),
                     'available': e.get('asset_path') in archive.namelist()}
                    for e in records if e['kind'] == 'image']


@router.get('/{document_id}/visuals/{element_id}', dependencies=[Depends(auth.require_admin)])
def review_visual_image(document_id: UUID, element_id: str, revision: UUID):
    row = db.get('documents', document_id)
    if row['source_revision'] != str(revision):
        raise HTTPException(409, 'The source changed. Reload its images.')
    with extraction(row) as archive:
        data, mime = image_bytes(archive, element(archive, element_id))
    return Response(data, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/{document_id}/visuals', response_model=Document)
def save_visual_reviews(document_id: UUID, request: ImageReviews, background: BackgroundTasks,
                        reviewer=Depends(auth.require_admin)):
    from backend.services import visual_reviews
    result = visual_reviews.save(str(document_id), request, reviewer)
    background.add_task(documents.process, str(document_id))
    return result
