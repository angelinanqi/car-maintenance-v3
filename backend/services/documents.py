"""Private source storage and Windows OCR. Indexing belongs to the RAG service."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
from uuid import uuid4
from threading import Lock
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import HTTPException, UploadFile

from backend import db
from backend.locks import content_lock as document_lock
from backend import settings
from backend.services.ocr import run_ocr
from backend.source_elements import build_elements, add_provenance, FORMAT_VERSION

logger = logging.getLogger(__name__)
ocr_lock = Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def work_directory(document_id):
    root = settings.DOCUMENT_WORK_DIR.resolve()
    path = (root / str(document_id)).resolve()
    if path.parent != root:
        raise ValueError("Document working directory must stay inside DOCUMENT_WORK_DIR")
    return path


def remove_artifacts(document_id):
    path = work_directory(document_id)
    if path.exists():
        shutil.rmtree(path)


def extraction_path(document_id):
    return f"documents/{document_id}/extraction.zip"


def validate_upload(file: UploadFile):
    filename = Path((file.filename or "").replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    if extension not in settings.DOCUMENT_EXTENSIONS:
        raise HTTPException(415, "Unsupported document format. Allowed: " + ", ".join(settings.DOCUMENT_EXTENSIONS))
    data = file.file.read(settings.DOCUMENT_MAX_BYTES + 1)
    if len(data) > settings.DOCUMENT_MAX_BYTES:
        raise HTTPException(413, "Document exceeds the configured upload size limit.")
    if not data:
        raise HTTPException(422, "The document is empty.")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(422, "The file is not a PDF.")
    if extension == ".md":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Markdown must use UTF-8 encoding.") from None
        if not text.strip() or "\x00" in text:
            raise HTTPException(422, "Markdown must contain readable text.")
    return filename, extension[1:], data


def storage_path(document_id, source_type):
    return f"documents/{document_id}/source.{source_type}"


def upload_source(document_id, source_type, data):
    path = storage_path(document_id, source_type)
    mime = "application/pdf" if source_type == "pdf" else "text/markdown"
    db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).upload(
        path, data, {"content-type": mime, "upsert": "true"},
    )
    return path


def create(file, metadata):
    filename, source_type, data = validate_upload(file)
    document_id = str(uuid4())
    path = upload_source(document_id, source_type, data)
    try:
        return db.insert("documents", dict(
            metadata, id=document_id, original_filename=filename,
            source_type=source_type, storage_path=path, size_bytes=len(data), source_revision=str(uuid4()),
        ))
    except Exception:
        # Compensate for a failed metadata write; never report a successful upload.
        try:
            db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove([path])
        except Exception:
            logger.exception("Could not remove source after failed document creation: %s", document_id)
        raise


def editable(document_id):
    row = db.get("documents", document_id)
    if row["status"] == "processing":
        raise HTTPException(409, "Document processing is still running.")
    return row


def edit(document_id, metadata):
    with document_lock(document_id):
        row = editable(document_id)
        if metadata.get("mobile_visible") and not row.get("published"):
            raise HTTPException(409, "Publish the indexed document before making it publicly downloadable.")
        if metadata.get("published") is False:
            metadata["mobile_visible"] = False
        if metadata.get("source_fidelity_verified") and not row.get("extraction_storage_path"):
            raise HTTPException(409, "Process and review the extracted document before verifying source fidelity.")
        # Applicability is resolved from current database metadata on every chat.
        return db.update("documents", document_id, metadata) if metadata else row


def source_paths(document_id):
    return [f"documents/{document_id}/{name}.{extension}"
            for name in ("source", "replacement") for extension in ("pdf", "md")]


def reset_processing():
    return dict(status="uploaded", source_revision=str(uuid4()), processed_at=None,
                processing_started_at=None, chunk_count=0, error=None, indexed_revision=None,
                indexed_at=None, extraction_storage_path=None, extraction_completed_at=None,
                source_fidelity_verified=False, published=False, mobile_visible=False)


def replace(document_id, file):
    filename, source_type, data = validate_upload(file)
    with document_lock('schedule-sources'), document_lock(document_id):
        row = editable(document_id)
        if referencing_schedules(document_id):
            raise HTTPException(409, "A maintenance schedule references this original. Stage a replacement to preserve its reviewed source.")
        if (row.get('superseded_by_id') or db.all_rows('documents', replacement_for_id=str(document_id))
                or db.all_rows('documents', superseded_by_id=str(document_id))):
            raise HTTPException(409, "Document revision history references this original. Stage a replacement to preserve it.")
        if row.get("published"):
            raise HTTPException(409, "Stage a replacement to preserve the current published document until the replacement is ready.")
        # Stage in the alternate slot so a failed upload cannot overwrite the active source.
        name = "source" if "/replacement." in row["storage_path"] else "replacement"
        path = f"documents/{document_id}/{name}.{source_type}"
        mime = "application/pdf" if source_type == "pdf" else "text/markdown"
        bucket = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET)
        bucket.upload(path, data, {"content-type": mime, "upsert": "true"})
        # Switch source and invalidate its old revision in one database write.
        # A failed write leaves the old source authoritative and the staged slot retryable.
        saved = db.update("documents", document_id, dict(
            reset_processing(), storage_path=path, source_type=source_type,
            original_filename=filename, size_bytes=len(data),
        ))
        try:
            remove_artifacts(document_id)
            bucket.remove([item for item in source_paths(document_id) if item != path] + [extraction_path(document_id)])
            return saved
        except Exception as error:
            # The deterministic slots remain discoverable for retry/delete after a partial failure.
            record_failure(document_id, error)
            raise


def referencing_schedules(document_id):
    return [schedule for schedule in db.all_rows('manufacturer_schedules')
            if any(entry.get('rule', {}).get('sourceDocumentId') == str(document_id)
                   for entry in schedule['entries'])]


def delete(document_id):
    with document_lock('schedule-sources'), document_lock(document_id):
        editable(document_id)
        if referencing_schedules(document_id):
            raise HTTPException(409, "A maintenance schedule references this source PDF. Preserve it for source traceability.")
        if (db.all_rows("documents", replacement_for_id=str(document_id))
                or db.all_rows("documents", superseded_by_id=str(document_id))):
            raise HTTPException(409, "Document revision history references this source. Remove an unpublished staged replacement first, or retain the original for traceability.")
        db.update("documents", document_id, dict(status="failed", error="Deletion in progress; retry deletion if interrupted.", chunk_count=0, processed_at=None, mobile_visible=False, published=False, indexed_revision=None, indexed_at=None))
        remove_artifacts(document_id)
        db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove(source_paths(document_id) + [extraction_path(document_id)])
        db.delete("documents", document_id)


def record_failure(document_id, error):
    logger.exception("Document operation failed: %s", document_id)
    try:
        db.update("documents", document_id, dict(status="failed", error=str(error)[:2000], processed_at=None, chunk_count=0, published=False, mobile_visible=False, indexed_revision=None, indexed_at=None))
    except Exception:
        logger.exception("Could not persist failure state for document %s", document_id)


def queue(document_id, force=False):
    with document_lock(document_id):
        row = editable(document_id)
        indexed = row.get("indexed_revision") and row.get("indexed_revision") == row.get("source_revision")
        if not force and (row["status"] == "awaiting_index" or (row["status"] == "processed" and indexed)):
            return row, False
        if row.get("published"):
            raise HTTPException(409, "Unpublish before reprocessing, or stage a replacement to keep the current source available.")
        values = reset_processing()
        values.update(status="processing", processing_started_at=now())
        return db.update("documents", document_id, values), True


def package_extraction(row, markdown, directory):
    archive = directory / "extraction.zip"
    manifest = {"format_version": FORMAT_VERSION, "document_id": row["id"], "source_revision": row["source_revision"],
                "markdown": "document.md", "original_filename": row["original_filename"], "source_type": row["source_type"]}
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))
        elements = build_elements(markdown.read_text(encoding='utf-8-sig'))
        elements.update(document_id=row['id'], source_revision=row['source_revision'], source_type=row['source_type'])
        for record in elements['elements']:
            record.update(document_id=row['id'], source_revision=row['source_revision'], original_source=row['storage_path'])
        provenance = markdown.parent / 'metadata'
        metadata = []
        if provenance.is_dir():
            for path in sorted(provenance.glob('*.json')):
                try:
                    metadata.append(json.loads(path.read_text(encoding='utf-8')))
                except (ValueError, UnicodeError):
                    pass  # retain raw metadata; unknown formats do not establish provenance
        add_provenance(elements, metadata)
        bundle.writestr('elements.json', json.dumps(elements, ensure_ascii=False))
        bundle.write(markdown, "document.md")
        provenance = markdown.parent / 'metadata'
        if provenance.is_dir():
            for path in sorted(provenance.glob('*.json')):
                bundle.write(path, 'metadata/' + path.name)
        images = markdown.parent / "images"
        if images.is_dir():
            for path in sorted(images.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    bundle.write(path, "images/" + path.relative_to(images).as_posix())
    if archive.stat().st_size > settings.EXTRACTION_MAX_BYTES:
        raise ValueError("OCR output exceeds EXTRACTION_MAX_BYTES. Split the document or increase the configured limit.")
    return archive


def process(document_id):
    # MinerU uses substantial GPU memory; execute one OCR job at a time.
    try:
        with ocr_lock, document_lock(document_id):
            row = db.get("documents", document_id)
            directory = work_directory(document_id)
            source = directory / f"{document_id}.{row['source_type']}"
            bucket = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET)
            data = bucket.download(row["storage_path"])
            # Preserve the existing MinerU cache only when its source bytes still match.
            if not source.is_file() or source.read_bytes() != data:
                remove_artifacts(document_id)
            directory.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data)
            markdown = run_ocr(source, directory / "ocr") if row["source_type"] == "pdf" else source
            if not markdown.read_text(encoding="utf-8-sig").strip():
                raise ValueError("Extraction produced no text.")
            archive = package_extraction(row, markdown, directory)
            path = extraction_path(document_id)
            bucket.upload(path, archive.read_bytes(), {"content-type": "application/zip", "upsert": "true"})
            db.update("documents", document_id, dict(
                status="awaiting_index", error=None, extraction_storage_path=path, extraction_completed_at=now(),
                processed_at=None, chunk_count=0, indexed_revision=None, indexed_at=None,
            ))
    except Exception as error:
        record_failure(document_id, error)


def recover_interrupted():
    # This app deliberately runs one backend process, without a distributed worker.
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        for row in db.all_rows("documents", status="processing"):
            try:
                db.update("documents", row["id"], dict(
                    status="failed", error="Processing was interrupted by a backend restart. Retry processing.",
                    processed_at=None, chunk_count=0, published=False, mobile_visible=False, indexed_revision=None, indexed_at=None,
                ))
            except Exception:
                logger.exception("Could not recover document %s", row["id"])
                raise
