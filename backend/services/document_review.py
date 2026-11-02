"""Revision-bound, private document review checklists and source navigation."""
import json
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5
from zipfile import BadZipFile

from fastapi import HTTPException
from pydantic import Field

from backend import db
from backend.services.source_assets import extraction
from shared.models import InputModel
from shared.source_elements import ELEMENT_PATTERN, HEADING_PATTERN, build_elements, plain, sanitize_table

TABLE = "document_review_progress"


class ReviewProgressInput(InputModel):
    source_revision: UUID
    version: int = Field(ge=0)
    decisions: dict[str, Literal["checked", "needs_clarification"]] = Field(default_factory=dict, max_length=20000)
    current_element_id: str | None = Field(default=None, max_length=100)
    source_page: int | None = Field(default=None, ge=1, le=100000)


def current_document(document_id, revision):
    row = db.get("documents", document_id)
    if row["source_revision"] != str(revision):
        raise HTTPException(409, "This document revision changed. Reload the current document before continuing your review.")
    if not row.get("extraction_storage_path") or row["status"] not in {"awaiting_index", "processed"}:
        raise HTTPException(409, "The document is not ready to check yet.")
    return row


def build_blocks(text, elements, *, source_type, assets):
    """Keep text in heading-sized sections; use exact offsets for media provenance."""
    headings = list(HEADING_PATTERN.finditer(text))
    parts = [part for record in elements for part in record.get("parts", [record])]
    by_offset = {record.get("source_offset"): record for record in parts}
    blocks = []

    def section_at(offset):
        path = []
        for heading in headings:
            if heading.start() > offset:
                break
            level = len(heading[1])
            path = [(depth, title) for depth, title in path if depth < level]
            path.append((level, heading[2].strip()))
        return [title for _, title in path]

    def add_text(start, end):
        cuts = [start] + [heading.start() for heading in headings if start < heading.start() < end] + [end]
        for left, right in zip(cuts, cuts[1:]):
            value = text[left:right].strip()
            if not value:
                continue
            path = section_at(left)
            blocks.append({"element_id": f"text-{left:05d}", "kind": "text", "text": value,
                           "start_offset": left, "end_offset": right,
                           "title": path[-1] if path else value.splitlines()[0].lstrip("# ")[:120],
                           "section_path": path, "pages": [], "issues": []})

    position = 0
    for match in ELEMENT_PATTERN.finditer(text):
        add_text(position, match.start())
        raw = match.group(0)
        kind = "image" if raw.lstrip().lower().startswith(("![", "<img")) else "table"
        record = by_offset.get(match.start(), {})
        # Never borrow a page from a neighbouring or reordered extracted element.
        if record.get("kind") != kind or record.get("original_html") != raw:
            record = {}
        path = record.get("section_path") or section_at(match.start())
        pages = [page for page in record.get("pages", []) if type(page) is int and page > 0]
        issues = []
        if source_type == "pdf" and not pages:
            issues.append("Source page unavailable; locate this content in the original.")
        if kind == "table" and not record.get("structure_valid"):
            issues.append("Table structure needs checking against the original.")
        if record.get("notes") and not record.get("association_verified"):
            issues.append("Confirm which notes and conditions belong to this content.")
        if kind == "image":
            if record.get("asset_path") not in assets:
                issues.append("The extracted illustration is unavailable; check the original.")
            uncertainty = (record.get("generated_identity") or {}).get("uncertainty")
            if uncertainty:
                issues.append(uncertainty)
        title = record.get("caption") or (path[-1] if path else "")
        blocks.append({"element_id": record.get("element_id", f"{kind}-offset-{match.start()}"),
                       "start_offset": match.start(), "end_offset": match.end(),
                       "source_element_id": record.get("element_id"), "kind": kind,
                       "title": title or ("Illustration" if kind == "image" else "Table"),
                       "text": raw if kind == "table" else record.get("caption", ""),
                       "html": sanitize_table(record.get("html", "")) if kind == "table" else "",
                       "cells": [{key: cell[key] for key in ("row", "column", "rowspan", "colspan", "header", "text")}
                                 for cell in record.get("cells", [])] if kind == "table" else [],
                       "section_path": path, "pages": sorted(set(pages)), "issues": issues,
                       "image_available": kind == "image" and record.get("asset_path") in assets,
                       "excerpt": plain(record.get("html", "")) if kind == "table" else record.get("caption", "")})
        position = match.end()
    add_text(position, len(text))
    return blocks


def blocks_for(document):
    try:
        with extraction(document) as archive:
            files = archive.namelist()
            package = json.loads(archive.read("manifest.json")) if "manifest.json" in files else {}
            markdown = package.get("markdown", "document.md")
            if markdown not in {"document.md", "metadata/processing.md"}:
                raise ValueError("Unknown processing Markdown")
            text = archive.read(markdown).decode("utf-8-sig")
            manifest = json.loads(archive.read("elements.json"))
            if not text.strip():
                raise ValueError("No readable text")
            for key, expected in (("document_id", document["id"]), ("source_revision", document["source_revision"])):
                if manifest.get(key) and manifest[key] != expected:
                    raise HTTPException(409, "The extracted content belongs to another revision. Prepare the current document again.")
            return build_blocks(text, manifest["elements"], source_type=document["source_type"],
                                assets=set(archive.namelist()))
    except (ValueError, KeyError, TypeError, UnicodeError, BadZipFile):
        raise HTTPException(422, "The prepared document could not be opened. Try preparing it again.") from None


def progress(document, reviewer_id):
    identity = str(uuid5(NAMESPACE_URL, f"document-review:{document['id']}:{document['source_revision']}:{reviewer_id}"))
    rows = db.all_rows(TABLE, id=identity)
    return rows[0] if rows else {
        "id": identity, "document_id": document["id"], "source_revision": document["source_revision"],
        "reviewer_id": str(reviewer_id), "decisions": {}, "current_element_id": None,
        "source_page": None, "version": 0,
    }


def corrections_for(document):
    with extraction(document) as archive:
        path = "metadata/extraction-corrections.json"
        return json.loads(archive.read(path)) if path in archive.namelist() else []


def correction_preview(change):
    result = {**change, "before": change["before"][:2000], "after": change["after"][:2000],
              "truncated": len(change["before"]) > 2000 or len(change["after"]) > 2000}
    if change["kind"] == "table":
        for field in ("before", "after"):
            tables = [record for record in build_elements(change[field])["elements"] if record["kind"] == "table"]
            result[field + "_html"] = tables[0]["html"] if len(tables) == 1 else ""
    return result


def save_progress(document, reviewer_id, request):
    blocks = blocks_for(document)
    ids = {block["element_id"] for block in blocks}
    if not set(request.decisions).issubset(ids) or (request.current_element_id and request.current_element_id not in ids):
        raise HTTPException(422, "Select review entries from the current document revision.")
    if document["source_type"] != "pdf" and request.source_page is not None:
        raise HTTPException(422, "This document has no PDF pages.")
    old = progress(document, reviewer_id)
    values = request.model_dump(mode="json", exclude={"version", "source_revision"})
    if old["version"] != request.version:
        # A retry after a lost response may describe the already-saved state.
        if all(old.get(key) == value for key, value in values.items()):
            return old
        raise HTTPException(409, "Your review changed in another tab. Reload saved progress before continuing.")
    if old["version"] == 0:
        return db.insert(TABLE, {**old, **values, "version": 1})
    return db.update(TABLE, old["id"], {**values, "version": old["version"] + 1})
