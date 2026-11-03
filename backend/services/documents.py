"""Private source storage and Windows OCR. Indexing belongs to the RAG service."""
from shared.observability import observed, emit, mark_outcome
from datetime import datetime, timezone
import json
import logging
from hashlib import sha256
from pathlib import Path
import shutil
from uuid import uuid4
from threading import Lock
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
import time

import httpx
from fastapi import HTTPException, UploadFile

from backend import db
from backend.locks import content_lock as document_lock
from backend import settings
from backend.services.ocr import run_ocr
from backend.services.ocr_client import ProcessingStopped
from shared.source_elements import build_elements, add_provenance, inspect_assets, FORMAT_VERSION, ELEMENT_PATTERN
from shared.document_structure import read_pdf_outline, reconcile_headings, escape_literal_headings
from shared.visual_identity import apply_reviews, VisualIdentity
from pypdf.errors import PyPdfError

logger = logging.getLogger(__name__)
ocr_lock = Lock()
preparation_lock = Lock()


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
    # The ID, path and bytes stay fixed across attempts. Upserting the same
    # source is safe even when Storage saved it but its response was lost.
    retry_connection(lambda: db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).upload(
        path, data, {"content-type": mime, "upsert": "true"},
    ))
    return path


@observed('document_upload')
def create(file, metadata):
    filename, source_type, data = validate_upload(file)
    document_id = str(uuid4())
    emit('document_received', 'received', job_id=document_id)
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
    with document_lock('schedule-sources'), document_lock(document_id):
        row = editable(document_id)
        reviewed_revision = metadata.pop("reviewed_revision", None)
        if metadata.get("source_fidelity_verified"):
            if not reviewed_revision or str(reviewed_revision) != row["source_revision"]:
                raise HTTPException(409, "The document revision changed or was not supplied. Reload and check the current document before approving it.")
            if row["status"] != "processed" or row.get("indexed_revision") != row["source_revision"] or not row.get("chunk_count"):
                raise HTTPException(409, "Wait for the current document to finish preparation and indexing before approving it.")
            from backend.services.review_questions import check_document
            check_document(document_id)
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
            for name in ("source", "replacement") for extension in ("pdf", "md")] + [
                f"documents/{document_id}/corrected-a.zip", f"documents/{document_id}/corrected-b.zip"]


def reset_processing():
    return dict(status="uploaded", source_revision=str(uuid4()), processed_at=None,
                processing_started_at=None, chunk_count=0, error=None, indexed_revision=None,
                indexed_at=None, extraction_storage_path=None, extraction_completed_at=None,
                source_fidelity_verified=False, published=False, mobile_visible=False)


def replace(document_id, file):
    filename, source_type, data = validate_upload(file)
    with document_lock('schedule-sources'), document_lock(document_id):
        row = editable(document_id)
        if db.all_rows('admin_review_questions', document_id=str(document_id)):
            raise HTTPException(409, "A saved clarification question references this original. Use Replace document to keep its source available for checking.")
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
            original_filename=filename, size_bytes=len(data), source_metadata=None,
        ))
        try:
            remove_artifacts(document_id)
            bucket.remove([item for item in set(source_paths(document_id) + [row["storage_path"]]) if item != path] + [extraction_path(document_id)])
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
        if db.all_rows('admin_review_questions', document_id=str(document_id)):
            raise HTTPException(409, "Saved clarification questions reference this document. Keep the original so their sources can still be checked.")
        if referencing_schedules(document_id):
            raise HTTPException(409, "A maintenance schedule references this source PDF. Preserve it for source traceability.")
        if (db.all_rows("documents", replacement_for_id=str(document_id))
                or db.all_rows("documents", superseded_by_id=str(document_id))):
            raise HTTPException(409, "Document revision history references this source. Remove an unpublished staged replacement first, or retain the original for traceability.")
        db.update("documents", document_id, dict(status="failed", error="Deletion in progress; retry deletion if interrupted.", chunk_count=0, processed_at=None, mobile_visible=False, published=False, indexed_revision=None, indexed_at=None))
        remove_artifacts(document_id)
        db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove(list(set(source_paths(document_id) + [row["storage_path"], extraction_path(document_id)])))
        db.delete("documents", document_id)


def record_failure(document_id, error):
    mark_outcome('failed')
    emit('document_job', 'failed', level='ERROR', job_id=str(document_id), error_type=type(error).__name__)
    logger.exception("Document operation failed: %s", document_id)
    try:
        db.update("documents", document_id, dict(status="failed", error=str(error)[:2000], processed_at=None, chunk_count=0, published=False, mobile_visible=False, indexed_revision=None, indexed_at=None))
    except Exception:
        logger.exception("Could not persist failure state for document %s", document_id)


@observed('document_queued', job_arg='document_id')
def queue(document_id, force=False):
    with document_lock(document_id):
        row = editable(document_id)
        if row["status"] == "awaiting_confirmation":
            raise HTTPException(409, "Finish correcting the document, then confirm changes to rebuild its index.")
        indexed = row.get("indexed_revision") and row.get("indexed_revision") == row.get("source_revision")
        if not force and (row["status"] == "awaiting_index" or (row["status"] == "processed" and indexed)):
            return row, False
        if row.get("published"):
            raise HTTPException(409, "Unpublish before reprocessing, or stage a replacement to keep the current source available.")
        if row.get("extraction_storage_path"):
            from backend.services import extraction_corrections
            try:
                files = extraction_corrections.read_bundle(row)
            except (HTTPException, ValueError, KeyError, BadZipFile):
                if row["extraction_storage_path"].endswith(("corrected-a.zip", "corrected-b.zip")):
                    raise HTTPException(409, "The saved corrections could not be opened. Restore their extraction bundle before rebuilding.") from None
                files = {}  # Keep the existing repair path for ordinary OCR output.
            if extraction_corrections.HISTORY in files:
                # Rebuild from the reviewed correction, including after restart;
                # running OCR again would silently replace it with the old error.
                return extraction_corrections.commit(row, files), False
        # Keep reviewed identities across a backend restart/reprocessing. The
        # source hash is checked again before they can enter a new extraction.
        if row.get('extraction_storage_path'):
            from backend.services.source_assets import extraction
            try:
                with extraction(row) as archive:
                    if 'metadata/visual-reviews.json' in archive.namelist():
                        directory = work_directory(document_id)
                        directory.mkdir(parents=True, exist_ok=True)
                        (directory / 'visual-reviews.json').write_bytes(archive.read('metadata/visual-reviews.json'))
            except (HTTPException, ValueError, KeyError, BadZipFile):
                # An obsolete/corrupt extraction must not prevent source repair.
                logger.warning('Previous visual reviews unavailable for %s; review the new extraction', document_id)
        values = reset_processing()
        values.update(status="processing", processing_started_at=now())
        return db.update("documents", document_id, values), True


@observed('extraction_packaging', job_arg='row', job_key='id')
def package_extraction(row, markdown, directory, *, describe_visuals=False, include_source_pages=False, stop=None):
    archive = directory / "extraction.zip"
    manifest = {"format_version": FORMAT_VERSION, "document_id": row["id"], "source_revision": row["source_revision"],
                "markdown": "document.md", "original_filename": row["original_filename"], "source_type": row["source_type"]}
    original = markdown.read_text(encoding='utf-8-sig')
    from shared.article_snapshot import decode
    article, original, assets = decode(original)
    if article:
        # Keep the uploaded snapshot intact; prepare only local derived files.
        markdown = directory / 'article' / 'document.md'
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(original, encoding='utf-8')
        for relative, data in assets.items():
            target = markdown.parent / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    if row.get('source_metadata'):
        from shared.website_metadata import validate_metadata
        article = validate_metadata(row['source_metadata'])
        pdf_path = directory / f"{row['id']}.pdf"
        if row['source_type'] != 'pdf' or sha256(pdf_path.read_bytes()).hexdigest() != article['pdf_sha256']:
            raise ValueError('Website provenance does not match the source PDF')
        article['content_sha256'] = sha256(original.encode('utf-8')).hexdigest()
    processing = original
    provenance = markdown.parent / 'metadata'
    metadata = []
    heading_lists = []
    if provenance.is_dir():
        for path in sorted(provenance.glob('*.json')):
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
                metadata.append(value)
                if (path.name.endswith('_content_list.json') and isinstance(value, list)
                        and all(isinstance(entry, dict) for entry in value)):
                    heading_lists.append(value)
            except (ValueError, UnicodeError):
                pass  # retain raw metadata; unknown formats do not establish provenance
    structure = None
    if row['source_type'] == 'pdf':
        structure = {'status': 'skipped', 'reason': 'Expected one supported OCR content list'}
        if len(heading_lists) == 1:
            processing, literal_escapes = escape_literal_headings(original, heading_lists[0])
            try:
                outline, page_count = read_pdf_outline(directory / f"{row['id']}.pdf")
                processing, structure = reconcile_headings(processing, heading_lists[0], outline, page_count)
            except (OSError, ValueError, PyPdfError) as error:
                logger.warning('PDF structure unavailable for %s: %s', row['id'], error)
                structure = {'status': 'skipped', 'reason': 'PDF outline could not be read'}
            structure['literal_heading_escapes'] = literal_escapes
        if processing != original:
            manifest['markdown'] = 'metadata/processing.md'
    with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))
        elements = build_elements(processing)
        if article:
            elements['article'] = article
            bundle.writestr('metadata/article.json', json.dumps(article, ensure_ascii=False))
        if processing != original:
            original_matches = list(ELEMENT_PATTERN.finditer(original))
            processing_matches = list(ELEMENT_PATTERN.finditer(processing))
            if ([match.group() for match in original_matches]
                    != [match.group() for match in processing_matches]):
                raise ValueError('Structure preparation changed source elements')
            for record, match in zip(elements['elements'], original_matches):
                record['original_source_offset'] = match.start()
        elements.update(document_id=row['id'], source_revision=row['source_revision'], source_type=row['source_type'])
        source_path = directory / f"{row['id']}.{row['source_type']}"
        if source_path.is_file():
            elements['source_sha256'] = sha256(source_path.read_bytes()).hexdigest()
        for record in elements['elements']:
            record.update(document_id=row['id'], source_revision=row['source_revision'], original_source=row['storage_path'])
        add_provenance(elements, metadata)
        audit = inspect_assets(elements, markdown.parent)
        if audit['missing']:
            raise ValueError('Extraction references missing image files. Upload the original PDF with its illustrations: '
                             + ', '.join(audit['missing'][:3]))
        for value in metadata:
            if not isinstance(value, dict):
                continue
            generated = {(item.get('element_id'), item['asset_sha256']): item
                         for item in value.get('generated_visual_identities', [])
                         if item.get('identity') and item.get('model')}
            for record in elements['elements']:
                item = generated.get((record['element_id'], record.get('asset_sha256')))
                if item and ((item.get('source_sha256') and item['source_sha256'] != elements.get('source_sha256'))
                             or (item.get('context_page') and record.get('pages') != [item['context_page']])):
                    continue
                if record['kind'] == 'image' and item:
                    record['generated_identity'] = {
                        **VisualIdentity.model_validate(item['identity']).model_dump(),
                        'model': item['model'], 'asset_sha256': item['asset_sha256'],
                        'prompt_sha256': item.get('prompt_sha256'),
                        'source_sha256': item.get('source_sha256'),
                        'context_page': item.get('context_page'),
                        'context_page_sha256': item.get('context_page_sha256'),
                    }
        # The candidate uses original pages with deterministic source regions.
        # Local repackaging tools can still opt out when comparing configurations.
        if include_source_pages and row['source_type'] == 'pdf' and source_path.is_file():
            from backend.services.visual_descriptions import prepare_source_pages
            prepare_source_pages(elements, source_path, markdown.parent, directory, stop=stop)
        if describe_visuals and row['source_type'] == 'pdf':
            from backend.services.visual_descriptions import describe_pdf
            elements['visual_description_report'] = describe_pdf(elements, source_path, markdown.parent, directory, stop=stop)
            # Full usage/raw descriptions live in the metadata report, not twice
            # in the element manifest.
            elements['visual_description_report'] = {
                'described': len(elements['visual_description_report']['generated_visual_identities']),
                'skipped': elements['visual_description_report']['skipped']}
        review_path = directory / 'visual-reviews.json'
        if review_path.is_file():
            reviews = json.loads(review_path.read_text(encoding='utf-8'))
            source_path = directory / f"{row['id']}.{row['source_type']}"
            if reviews.get('source_sha256') == sha256(source_path.read_bytes()).hexdigest():
                apply_reviews(elements, reviews['assets'])
                bundle.writestr('metadata/visual-reviews.json', json.dumps(reviews))
        bundle.writestr('elements.json', json.dumps(elements, ensure_ascii=False))
        bundle.write(markdown, "document.md")
        if structure is not None:
            bundle.writestr('metadata/structure-review.json', json.dumps(structure, ensure_ascii=False))
        if processing != original:
            bundle.writestr('metadata/processing.md', processing.encode('utf-8'))
        provenance = markdown.parent / 'metadata'
        if provenance.is_dir():
            for path in sorted(provenance.glob('*.json')):
                if path.name in {'structure-review.json', 'visual-reviews.json'}:
                    continue  # Repackaging produces its own derived structure report.
                bundle.write(path, 'metadata/' + path.name)
        images = markdown.parent / "images"
        if images.is_dir():
            from shared.source_elements import element_parts
            asset_elements = list(elements['elements'])
            for item in elements['elements']:
                if item.get('parts'):
                    asset_elements.extend(element_parts(item))
            retained = {item.get('asset_path') for item in asset_elements}
            retained.update(item.get('visual_asset_path') for item in asset_elements)
            retained.update(item['asset_path'] for item in elements.get('page_assets', []))
            for path in sorted(images.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    relative = "images/" + path.relative_to(images).as_posix()
                    # Only source-referenced assets belong in the delivery bundle.
                    # Raw MinerU intermediates stay in the original extraction cache.
                    if relative not in retained:
                        continue
                    bundle.write(path, relative)
    if archive.stat().st_size > settings.EXTRACTION_MAX_BYTES:
        raise ValueError("OCR output exceeds EXTRACTION_MAX_BYTES. Split the document or increase the configured limit.")
    return archive


def preparation_checkpoint(row):
    """A revision-bound, durable handoff from OCR to the preparation worker."""
    path = work_directory(row['id']) / 'pending-preparation.json'
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(saved, dict) or any(saved.get(key) != row[key] for key in (
            'source_revision', 'storage_path', 'source_type')):
        return None
    return saved


@observed('document_queue_attempt', job_arg='document_id')
def process(document_id, *, stop=None, stage='ocr'):
    # Each stage has one worker. Slow preparation never holds the OCR lock.
    if stage not in {'ocr', 'preparation'}:
        raise ValueError('Unknown document processing stage')
    try:
        with (ocr_lock if stage == 'ocr' else preparation_lock), document_lock(document_id):
            row = db.get("documents", document_id)
            if row["status"] != "processing" or (stop and stop.is_set()):
                return
            directory = work_directory(document_id)
            if (directory / 'pending-extraction.json').is_file():
                return  # Completed extraction handoffs have their own recovery loop.
            ready = preparation_checkpoint(row)
            if stage == 'preparation':
                if ready:
                    prepare_document(row, ready, stop=stop)
                return
            if ready:
                return
            source = directory / f"{document_id}.{row['source_type']}"
            bucket = db.bucket(settings.SUPABASE_DOCUMENT_BUCKET)
            data = bucket.download(row["storage_path"])
            review_path = directory / 'visual-reviews.json'
            reviews = json.loads(review_path.read_text(encoding='utf-8')) if review_path.is_file() else None
            # Preserve the existing MinerU cache only when its source bytes still match.
            if not source.is_file() or source.read_bytes() != data:
                remove_artifacts(document_id)
                directory.mkdir(parents=True, exist_ok=True)
                staged_source = source.with_suffix(source.suffix + '.tmp')
                staged_source.write_bytes(data)
                staged_source.replace(source)
            directory.mkdir(parents=True, exist_ok=True)
            if reviews and reviews.get('source_sha256') == sha256(data).hexdigest():
                review_path.write_text(json.dumps(reviews), encoding='utf-8')
            markdown = run_ocr(source, directory / "ocr", stop=stop) if row["source_type"] == "pdf" else source
            if not markdown.read_text(encoding="utf-8-sig").strip():
                raise ValueError("Extraction produced no text.")
            checkpoint = directory / 'pending-preparation.tmp'
            checkpoint.write_text(json.dumps({
                **{key: row[key] for key in ('source_revision', 'storage_path', 'source_type')},
                'source_sha256': sha256(data).hexdigest(),
            }), encoding='utf-8')
            checkpoint.replace(directory / 'pending-preparation.json')
            emit('document_preparation', 'queued', job_id=str(document_id))
            logger.info('Document %s: OCR complete; queued for preparation', document_id)
    except ProcessingStopped:
        mark_outcome('deferred')
        emit('document_job', 'deferred', level='WARNING', job_id=str(document_id))
        pass  # Keep the durable queue entry and task checkpoint for restart.
    except httpx.TransportError:
        mark_outcome('deferred')
        emit('document_job', 'deferred', level='WARNING', job_id=str(document_id))
        logger.warning("Document %s remains queued after a connection failure", document_id)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 429 or error.response.status_code >= 500:
            mark_outcome('deferred')
            emit('document_job', 'deferred', level='WARNING', job_id=str(document_id))
            logger.warning("Document %s remains queued after HTTP %s", document_id, error.response.status_code)
        else:
            record_failure(document_id, error)
    except HTTPException as error:
        if error.status_code != 409:
            record_failure(document_id, error)
        else:
            mark_outcome('deferred')
        # A queue/review request may still own this document's mutation lock.
        # Leave its saved processing request for the next worker pass.
    except Exception as error:
        record_failure(document_id, error)


@observed('document_preparation', job_arg='row', job_key='id')
def prepare_document(row, ready, *, stop=None):
    document_id = row['id']
    directory = work_directory(document_id)
    source = directory / f"{document_id}.{row['source_type']}"
    if sha256(source.read_bytes()).hexdigest() != ready.get('source_sha256'):
        raise ValueError('Prepared source no longer matches the OCR handoff')
    markdown = (directory / 'ocr' / str(document_id) / f'{document_id}.md'
                if row['source_type'] == 'pdf' else source)
    logger.info('Document %s: preparing pages and illustrations', document_id)
    package_extraction(row, markdown, directory, describe_visuals=True,
                       include_source_pages=True, stop=stop)
    if stop and stop.is_set():
        raise ProcessingStopped()
    # Persist the upload handoff before clearing the preparation handoff.
    checkpoint = directory / 'pending-extraction.tmp'
    checkpoint.write_text(json.dumps({
        'source_revision': row['source_revision'], 'completed_at': now(),
    }), encoding='utf-8')
    checkpoint.replace(directory / 'pending-extraction.json')
    (directory / 'pending-preparation.json').unlink(missing_ok=True)
    try:
        finish_extraction(document_id)
    except httpx.TransportError:
        logger.warning('Extraction saved locally for %s; upload/status save will retry automatically', document_id)


def retry_connection(operation):
    # Only use for reads, fixed-path source upserts and revision-checked handoffs.
    for attempt in range(3):
        try:
            return operation()
        except httpx.TransportError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


@observed('extraction_handoff', job_arg='document_id')
def finish_extraction(document_id):
    """Resume a completed extraction without OCR, including after a lost response."""
    directory = work_directory(document_id)
    pending = directory / "pending-extraction.json"
    checkpoint = json.loads(pending.read_text(encoding="utf-8"))
    row = db.get("documents", document_id)
    if row["source_revision"] != checkpoint["source_revision"] or row["status"] != "processing":
        # Never rewind an acknowledged index or publish an obsolete revision.
        pending.unlink(missing_ok=True)
        return
    archive = directory / "extraction.zip"
    with ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        if (manifest.get("document_id") != str(document_id)
                or manifest.get("source_revision") != checkpoint["source_revision"]):
            raise ValueError("Saved extraction does not match the pending document revision")
    path = extraction_path(document_id)
    data = archive.read_bytes()
    retry_connection(lambda: db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).upload(
        path, data, {"content-type": "application/zip", "upsert": "true"}))
    values = dict(status="awaiting_index", error=None, extraction_storage_path=path,
                  extraction_completed_at=checkpoint["completed_at"], processed_at=None,
                  chunk_count=0, indexed_revision=None, indexed_at=None)
    # If a response is lost, repeating this PATCH cannot undo an index acknowledgement.
    retry_connection(lambda: db.client().table("documents").update(values)
        .eq("id", str(document_id)).eq("source_revision", checkpoint["source_revision"])
        .eq("status", "processing").execute())
    pending.unlink(missing_ok=True)
    emit('document_index', 'queued', job_id=str(document_id))


def retry_pending_extractions():
    for pending in settings.DOCUMENT_WORK_DIR.glob("*/pending-extraction.json"):
        document_id = pending.parent.name
        try:
            with document_lock(document_id):
                finish_extraction(document_id)
        except HTTPException as error:
            if error.status_code == 404:
                pending.unlink(missing_ok=True)
            elif error.status_code != 409:
                logger.exception("Could not resume extraction for %s", document_id)
        except httpx.TransportError:
            logger.warning("Supabase connection unavailable; extraction %s remains queued for retry", document_id)
        except Exception:
            # Keep the checkpoint and continue other documents; no silent loss of work.
            logger.exception("Could not resume extraction for %s", document_id)


def run_queue_pass(stop, *, stage='ocr'):
    """Independent OCR and preparation workers share the persisted queue.

    Retain the same source revision and local OCR task checkpoint on restart.
    Failed documents need an explicit retry, rather than an endless retry loop.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        return
    rows = db.all_rows("documents", status="processing",
                       order_by=("processing_started_at", "id"))
    for row in rows:
        if stop.is_set():
            break
        document_id = str(row["id"])
        if (work_directory(document_id) / "pending-extraction.json").is_file():
            continue  # The handoff recovery loop owns this completed extraction.
        ready = preparation_checkpoint(row)
        if (stage == 'ocr' and ready) or (stage == 'preparation' and not ready):
            continue
        process(document_id, stop=stop, stage=stage)
