"""Revision-bound, private document review checklists and source navigation."""
import json
import re
from collections import defaultdict
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5
from zipfile import BadZipFile

from fastapi import HTTPException
from pydantic import Field

from backend import db
from backend.services.source_assets import extraction
from shared.models import InputModel
from shared.document_structure import escape_literal_headings, reconcile_headings
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


def add_text_pages(blocks, metadata):
    """Match complete extracted paragraphs, never pages from nearby media.

    Repeated paragraphs need an exact, unique match of their surrounding source
    text too. Unmatched or ambiguous content retains the manual page control.
    """
    def normalized(value):
        return " ".join(re.sub(r"(?m)^[ \t]*#{1,6}[ \t]+", "", value).split())

    paragraphs = []
    for index, block in enumerate(blocks):
        if block["kind"] == "text":
            paragraphs.extend((normalized(part), index) for part in re.split(r"\n\s*\n", block["text"])
                              if part.strip())
        else:
            # A match must not cross a table or illustration omitted from prose.
            paragraphs.append(("\x00", index))
    corpus = " ".join(value for value, _ in paragraphs)
    starts, ends = {}, {}
    by_first_word = defaultdict(list)
    offset = 0
    for value, index in paragraphs:
        starts[offset] = index
        ends[offset + len(value)] = index
        if value:
            by_first_word[value.split(" ", 1)[0]].append(offset)
        offset += len(value) + 1
    pages = defaultdict(set)
    for data in metadata:
        if not isinstance(data, list):
            continue
        records = []
        for item in data:
            if (isinstance(item, dict) and item.get("type") == "text"
                    and isinstance(item.get("text"), str) and item["text"].strip()
                    and type(item.get("page_idx")) is int and item["page_idx"] >= 0):
                records.append((normalized(item["text"]), item["page_idx"] + 1))
            else:
                records.append(("\x00", None))
        # Check both source-side and Markdown-side uniqueness. A paragraph
        # removed by a correction must not inherit another occurrence's page.
        for before, after in ((0, 0), (1, 0), (0, 1), (1, 1)):
            contexts = defaultdict(list)
            for index, (value, page) in enumerate(records):
                if page is None or index < before or index + after >= len(records):
                    continue
                context = records[index - before:index + after + 1]
                if any(number is None for _, number in context):
                    continue
                key = " ".join(text for text, _ in context)
                prefix = sum(len(text) + 1 for text, _ in context[:before])
                contexts[key].append((prefix, len(value), page))
            for key, matches in contexts.items():
                if len(matches) != 1:
                    continue
                positions = []
                for candidate in by_first_word[key.split(" ", 1)[0]]:
                    if candidate + len(key) in ends and corpus.startswith(key, candidate):
                        positions.append(candidate)
                        if len(positions) > 1:
                            break
                if len(positions) != 1:
                    continue
                position = positions[0]
                prefix, length, page = matches[0]
                left, right = position + prefix, position + prefix + length
                if (position not in starts or position + len(key) not in ends
                        or left not in starts or right not in ends):
                    continue
                for index in range(starts[left], ends[right] + 1):
                    if blocks[index]["kind"] == "text":
                        pages[index].add(page)
    for index, block in enumerate(blocks):
        if block["kind"] == "text":
            block["pages"] = sorted(pages[index])


def add_heading_pages(blocks, text, original, metadata, outline):
    """Replay the validated structure transform to locate repeated/added headings.

    Replaying also supports archives prepared before heading pages were saved.
    Corrected text must still match exactly before these coordinates are used.
    """
    if len(metadata) != 1 or not isinstance(metadata[0], list):
        return
    records = metadata[0]
    page_count = max((item["page_idx"] + 1 for item in records if isinstance(item, dict)
                      and type(item.get("page_idx")) is int and item["page_idx"] >= 0), default=0)
    original, _ = escape_literal_headings(original, records)
    derived, report = reconcile_headings(original, records, outline, page_count)
    if derived != text or report["status"] != "applied":
        return
    headings = list(HEADING_PATTERN.finditer(text))
    pages = report["heading_pages"]
    if len(headings) != len(pages):
        return
    by_offset = {heading.start(): page for heading, page in zip(headings, pages)}
    for block in blocks:
        if block["kind"] == "text" and block["start_offset"] in by_offset:
            block["pages"] = sorted(set(block["pages"] + [by_offset[block["start_offset"]]]))


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
            blocks = build_blocks(text, manifest["elements"], source_type=document["source_type"],
                                  assets=set(files))
            if document["source_type"] == "pdf":
                metadata = [json.loads(archive.read(name)) for name in files
                            if name.startswith("metadata/") and name.endswith("_content_list.json")]
                add_text_pages(blocks, metadata)
                if "metadata/structure-review.json" in files:
                    structure = json.loads(archive.read("metadata/structure-review.json"))
                    if structure.get("status") == "applied":
                        add_heading_pages(blocks, text, archive.read("document.md").decode("utf-8-sig"),
                                          metadata, structure["outline"])
            return blocks
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
