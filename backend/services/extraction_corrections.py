"""Admin corrections over prepared evidence, without modifying the source or rerunning OCR."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from bs4 import BeautifulSoup
from fastapi import HTTPException
from pydantic import Field

from backend import db, settings
from backend.services import document_review, documents
from backend.services.source_assets import extraction
from shared.models import InputModel
from shared.source_elements import ELEMENT_PATTERN, build_elements, combine_continuations, plain, sanitize_table, table_cells

HISTORY = "metadata/extraction-corrections.json"
ORIGINAL = "metadata/original-extraction.md"


class CorrectionInput(InputModel):
    source_revision: UUID
    element_id: str = Field(min_length=1, max_length=100)
    replacement: str = Field(min_length=1, max_length=200000)
    reason: str = Field(min_length=1, max_length=1000)
    confirm_source: bool = False


class ConfirmCorrectionsInput(InputModel):
    source_revision: UUID


def read_bundle(document):
    with extraction(document) as archive:
        return {entry.filename: archive.read(entry) for entry in archive.infolist() if not entry.is_dir()}


def processing_text(files):
    manifest = json.loads(files["manifest.json"])
    name = manifest.get("markdown", "document.md")
    if name not in {"document.md", "metadata/processing.md"}:
        raise HTTPException(422, "The prepared document has an unsupported text format. Prepare it again.")
    return files[name].decode("utf-8-sig")


def history(files):
    return json.loads(files[HISTORY]) if HISTORY in files else []


def checked_table(value):
    """Accept one bounded table; never silently remove unsafe user markup."""
    soup = BeautifulSoup(value, "html.parser")
    tables = soup.find_all("table")
    if len(tables) != 1 or any(str(node).strip() and node != tables[0] for node in soup.contents):
        raise HTTPException(422, "Enter one table without content outside it.")
    for tag in soup.find_all(True):
        if tag.name not in {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "br", "p", "strong", "b", "em", "i", "sup", "sub"}:
            raise HTTPException(422, "Use table cells and text formatting only; links, images and scripts are not allowed.")
        if any(key not in {"rowspan", "colspan"} or tag.name not in {"td", "th"} for key in tag.attrs):
            raise HTTPException(422, "Only row and column spans are allowed as table attributes.")
        children = {"table": {"caption", "thead", "tbody", "tfoot", "tr"},
                    "thead": {"tr"}, "tbody": {"tr"}, "tfoot": {"tr"}, "tr": {"td", "th"}}.get(tag.name)
        if children is not None and any(
                child.name not in children if child.name else bool(str(child).strip()) for child in tag.children):
            raise HTTPException(422, "Keep table text inside cells or a caption, with each cell inside a row.")
        for key in ("rowspan", "colspan"):
            try:
                span = int(tag.get(key, 1))
            except (TypeError, ValueError):
                span = 0
            if not 1 <= span <= 100:
                raise HTTPException(422, "Table row and column spans must be between 1 and 100.")
    raw_cells = soup.find_all(["td", "th"])
    if not raw_cells or len(raw_cells) > 2000 or len(soup.find_all("tr")) > 1000:
        raise HTTPException(422, "A corrected table must contain between 1 and 2000 cells and at most 1000 rows.")
    if sum(int(cell.get("rowspan", 1)) * int(cell.get("colspan", 1)) for cell in raw_cells) > 20000:
        raise HTTPException(422, "The corrected table is too large.")
    clean = sanitize_table(value)
    _, valid = table_cells(clean)
    if not valid:
        raise HTTPException(422, "The table has gaps, overlapping cells or invalid spans. Check its rows and columns.")
    return clean


def rebuild_elements(old, text, document, previous_text):
    fresh = build_elements(text)
    previous_prose = " ".join(plain(previous_text).split())
    corrected_prose = " ".join(plain(text).split())
    originals = [part for record in old["elements"] for part in record.get("parts", [record])]
    originals.sort(key=lambda record: record["source_offset"])
    if len(fresh["elements"]) != len(originals):
        raise HTTPException(422, "Keep the existing tables and illustrations. Correct one entry at a time.")
    # Element order cannot change in this editor. Copy source coordinates and image
    # identities only from the corresponding original; derive search text afresh.
    retained = ("pages", "bounding_boxes", "source_records", "provenance_available",
                "logical_table_id", "is_continuation", "continuation_pages", "visual_asset_path",
                "asset_sha256", "asset_available", "identity_review", "generated_identity")
    for new, previous in zip(fresh["elements"], originals):
        if new["kind"] != previous["kind"] or (new["kind"] == "image" and new["original_html"] != previous["original_html"]):
            raise HTTPException(422, "Keep the existing illustrations and table order.")
        for key in retained:
            if key in previous:
                new[key] = deepcopy(previous[key])
        # Some extractor footnotes/captions are not serialized in Markdown.
        if previous.get("extractor_notes"):
            notes = []
            for note in previous["extractor_notes"]:
                value = " ".join(plain(note).split())
                if value not in previous_prose or value in corrected_prose:
                    notes.append(note)
            new["extractor_notes"] = notes
            new["notes"] = list(dict.fromkeys(new["notes"] + notes))
        if not new["caption"] and previous.get("caption_origin") == "extractor_caption":
            new["caption"] = previous["caption"]
            new["caption_origin"] = "extractor_caption"
        new.update(document_id=document["id"], source_revision=document["source_revision"],
                   original_source=document["storage_path"])
        new["description"] = "\n".join([new["description"], new["caption"], *new["notes"]])[:1600]
    combine_continuations(fresh)
    return {**old, **fresh, "document_id": document["id"], "source_revision": document["source_revision"]}


def commit(document, files, *, defer_indexing=False):
    """Upload into the inactive slot, then atomically select a fresh index revision."""
    revision = str(uuid4())
    package = json.loads(files["manifest.json"])
    package["source_revision"] = revision
    elements = json.loads(files["elements.json"])
    elements["source_revision"] = revision
    for element in elements["elements"]:
        element["source_revision"] = revision
        for part in element.get("parts", []):
            part["source_revision"] = revision
    files = {**files, "manifest.json": json.dumps(package).encode(),
             "elements.json": json.dumps(elements, ensure_ascii=False).encode()}
    if sum(len(value) for value in files.values()) > settings.EXTRACTION_MAX_BYTES:
        raise HTTPException(413, "The corrected extraction exceeds the configured size limit.")
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    data = output.getvalue()
    if len(data) > settings.EXTRACTION_MAX_BYTES:
        raise HTTPException(413, "The corrected extraction exceeds the configured size limit.")
    slot = "corrected-b.zip" if document["extraction_storage_path"].endswith("corrected-a.zip") else "corrected-a.zip"
    path = f"documents/{document['id']}/{slot}"
    db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).upload(path, data, {"content-type": "application/zip", "upsert": "true"})
    return db.update("documents", document["id"], {
        **documents.reset_processing(), "source_revision": revision,
        "status": "awaiting_confirmation" if defer_indexing else "awaiting_index",
        "extraction_storage_path": path, "extraction_completed_at": documents.now(),
    })


def save(document_id, request, reviewer):
    with documents.document_lock("schedule-sources"), documents.document_lock(document_id):
        row = document_review.current_document(document_id, request.source_revision)
        if row.get("published") or row.get("superseded_by_id"):
            raise HTTPException(409, "Take this document offline or stage a replacement before correcting its extraction.")
        if row["status"] == "processed" and row.get("indexed_revision") != row["source_revision"]:
            raise HTTPException(409, "The indexed document revision is inconsistent. Reload or prepare the document again.")
        if not request.confirm_source:
            raise HTTPException(422, "Confirm that the correction matches the original document.")
        files = read_bundle(row)
        text = processing_text(files)
        manifest = json.loads(files["elements.json"])
        blocks = document_review.build_blocks(text, manifest["elements"], source_type=row["source_type"], assets=set(files))
        block = next((block for block in blocks if block["element_id"] == request.element_id), None)
        if not block or block["kind"] not in {"text", "table"}:
            raise HTTPException(422, "Choose a text section or table from the current extraction.")
        replacement = request.replacement
        if block["kind"] == "table":
            replacement = checked_table(replacement)
        elif ELEMENT_PATTERN.search(replacement) or "\x00" in replacement:
            raise HTTPException(422, "Edit section text only. Tables and illustrations must remain separate entries.")
        before = text[block["start_offset"]:block["end_offset"]]
        if replacement.strip() == before.strip():
            raise HTTPException(422, "Change the extracted content before saving a correction.")
        # Separate the edited entry from adjacent headings/tables, including at EOF.
        after = "\n\n" + replacement.strip() + "\n\n"
        corrected = text[:block["start_offset"]] + after + text[block["end_offset"]:]
        elements = rebuild_elements(manifest, corrected, row, text)
        changes = history(files)
        changes.append({"element_id": block["element_id"], "kind": block["kind"], "title": block["title"],
                        "source_revision": row["source_revision"], "before": before.strip(), "after": replacement.strip(),
                        "reason": request.reason, "reviewed_by": str(reviewer["user"]["id"]), "reviewed_at": documents.now(),
                        "before_sha256": sha256(text.encode()).hexdigest(), "after_sha256": sha256(corrected.encode()).hexdigest()})
        files.setdefault(ORIGINAL, files["document.md"])
        files.setdefault("metadata/original-elements.json", files["elements.json"])
        if "metadata/processing.md" in files:
            files.setdefault("metadata/original-processing.md", files["metadata/processing.md"])
        package = json.loads(files["manifest.json"])
        package["markdown"] = "document.md"
        files.update({"manifest.json": json.dumps(package).encode(), "document.md": corrected.encode(),
                      "elements.json": json.dumps(elements, ensure_ascii=False).encode(),
                      HISTORY: json.dumps(changes, ensure_ascii=False).encode()})
        files.pop("metadata/processing.md", None)
        return commit(row, files, defer_indexing=True)


def confirm(document_id, request):
    """Release exactly the saved revision the administrator has confirmed."""
    with documents.document_lock("schedule-sources"), documents.document_lock(document_id):
        row = document_review.current_document(document_id, request.source_revision)
        if row.get("published") or row.get("superseded_by_id"):
            raise HTTPException(409, "This document is no longer available for corrections.")
        if row["status"] in {"awaiting_index", "processed"}:
            return row  # A repeated confirmation must not start another rebuild.
        return db.update("documents", document_id, {"status": "awaiting_index", "error": None})
