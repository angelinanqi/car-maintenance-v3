"""Authoritative evidence and admin decisions around optional AI schedule proposals."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import re
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from backend import db
from backend.services import maintenance_assistance as maintenance, review_questions
from shared.maintenance_extraction import extract_items, suggest_matches
from shared.schedule_drafting import ScheduleDraftRequest, SourceCell, rule_issues


def for_table(state, vehicle_id, table_id):
    return [row for row in state["suggestions"] if row.get("ai_draft", {}).get("vehicle_id") == str(vehicle_id)
            and row["table_id"] == table_id]


def prepare(document, state, vehicle_id, table_id, replace_existing=False):
    vehicle = db.get("knowledge_vehicles", vehicle_id)
    if not vehicle.get("active", True):
        raise HTTPException(422, "Choose an active vehicle before drafting its schedule.")
    if not db.all_rows("document_vehicles", document_id=document["id"], vehicle_id=str(vehicle_id)):
        raise HTTPException(422, "The reference document must cover the selected vehicle.")
    if document.get("document_type") not in {"owners_manual", "maintenance_booklet", "service_manual"}:
        raise HTTPException(422, "Use an owner's manual, maintenance booklet or service manual for schedule drafting.")
    selection = next((choice for choice in state["selections"] if choice["table_id"] == table_id), None)
    table = next((table for table in state["catalogue"]["tables"] if table["table_id"] == table_id), None)
    if not selection or not table:
        raise HTTPException(422, "Confirm the table and its task-name columns before drafting.")
    existing = for_table(state, vehicle_id, table_id)
    if any(row["status"] == "accepted" for row in existing):
        raise HTTPException(409, "This table has accepted AI rows. Mark them for recheck before replacing the draft.")
    if existing and not replace_existing:
        raise HTTPException(409, "A draft already exists for this vehicle and table. Confirm replacement or continue reviewing it.")
    try:
        extracted = extract_items(state["catalogue"], {"document_id": document["id"],
            "source_revision": document["source_revision"], "tables": [selection]})
        source = table["source"]
        request = ScheduleDraftRequest(
            document_id=document["id"], source_revision=document["source_revision"],
            document_name=document["name"], document_type=document["document_type"],
            vehicle={key: str(vehicle.get(key) or "") for key in ("id", "name", "year", "engine", "variant", "powertrain")},
            table_id=table_id, title=" > ".join(source.get("section_path", []) + [table["title"]]),
            cells=[SourceCell(**{key: cell[key] for key in SourceCell.model_fields if key in cell}) for cell in source["cells"]],
            task_rows=sorted({row["row"] for row in extracted["suggestions"]}), item_columns=selection["columns"],
            context=source.get("context", []), notes=source.get("notes", []), table_uncertainty=table["uncertainty"],
        )
    except (ValueError, ValidationError) as error:
        raise HTTPException(422, "This table cannot be drafted as selected. Check its task rows and columns, or use manual entry.") from error
    if len(request.model_dump_json()) > 100000:
        raise HTTPException(413, "This complete table is too large for one AI draft. Use task-name extraction and enter its rules manually.")
    return request


def evidence_for(row, request):
    cells = {(cell.row, cell.column): cell for cell in request.cells}
    if not set(row.source_rows).issubset(request.task_rows):
        raise ValueError("Proposal uses an unselected task row")
    references = [(ref.row, ref.column) for ref in row.evidence_cells]
    if len(set(references)) != len(references) or any(ref not in cells for ref in references):
        raise ValueError("Proposal cites missing or duplicate source cells")
    evidence = [cells[ref] for ref in references]
    for source_row in row.source_rows:
        if not any(cell.column in request.item_columns and cell.row <= source_row < cell.row + cell.rowspan for cell in evidence):
            raise ValueError("Proposal does not cite its selected task label")
    if any(index >= len(request.notes) for index in row.note_indices):
        raise ValueError("Proposal cites a missing note")
    if any(index >= len(request.context) for index in row.context_indices):
        raise ValueError("Proposal cites missing context")
    return {
        "cells": [cell.model_dump() for cell in evidence],
        "notes": [request.notes[index] for index in row.note_indices],
        "context": [request.context[index] for index in row.context_indices],
    }


def numeric_issues(rule, evidence):
    if rule is None:
        return []
    text = " ".join([cell["text"] for cell in evidence["cells"]] + evidence["notes"] + evidence["context"])
    text = re.sub(r"\b\d{1,3}(?:,\d{3})+\b", lambda match: match[0].replace(",", ""), text)
    numbers = {float(value) for value in re.findall(r"\d+(?:\.\d+)?", text)}
    km = [value for value in [rule.distanceKm, *rule.distanceMilestones] if value]
    months = [value for value in [rule.months, *rule.monthMilestones] if value]
    issues = []
    multiplier = bool(re.search(r"(?:[x×]\s*1[ ,]?000|thousand|['’]000)", text, re.I))
    for value in km:
        if value not in numbers and not (multiplier and value / 1000 in numbers):
            issues.append(f"Verify {value} km against the original; its value or conversion is not explicit in the cited evidence.")
    for value in months:
        if value not in numbers and not (re.search(r"\byears?\b", text, re.I) and value / 12 in numbers):
            issues.append(f"Verify {value} months against the original; its value or conversion is not explicit in the cited evidence.")
    return issues


def proposals(state, request, result):
    if not result.rows:
        message = " ".join(result.warnings) or "The table did not contain enough evidence for a schedule draft."
        raise HTTPException(422, message[:1500])
    items = db.all_rows("maintenance_items", active=True)
    table = next(table for table in state["catalogue"]["tables"] if table["table_id"] == request.table_id)
    generated_at = datetime.now(timezone.utc).isoformat()
    generation_id = str(uuid4())
    rows = []
    identities = defaultdict(list)
    try:
        for row in result.rows:
            evidence = evidence_for(row, request)
            uncertainty = list(dict.fromkeys([*row.uncertainty, *numeric_issues(row.rule, evidence)]))
            literal = " ".join([cell["text"] for cell in evidence["cells"]] + evidence["notes"] + evidence["context"])
            complex_timing = (
                bool(re.search(r"\b(first|initial)\s+(service|inspection|replacement|at|after|\d)", literal, re.I)
                     and re.search(r"\b(then|thereafter|subsequent|every)\b", literal, re.I))
                or bool(re.search(r"\bnormal\b", literal, re.I) and re.search(r"\bsevere\b", literal, re.I))
                or bool(re.search(r"\bmiles?\b", literal, re.I) and not re.search(r"\bkm\b", literal, re.I))
            )
            manual = row.manual_entry_required or complex_timing
            if manual:
                uncertainty.append("This operation needs manual entry; separate timing or unsupported units must not be flattened into one rule.")
            candidates = suggest_matches(row.name, [item for item in items if row.action is None or item["action"] == row.action])
            exact = next((match["item_id"] for match in candidates if match["method"] == "exact_text"), None)
            suggestion = {
                "suggestion_id": f"{request.table_id}:ai-{uuid4().hex}", "table_id": request.table_id,
                "document_id": str(request.document_id), "source_revision": str(request.source_revision),
                "suggested_name": row.name, "edited_name": row.name, "original_text": "\n".join(cell["text"] for cell in evidence["cells"]),
                "mapped_item_id": exact, "status": "suggested", "pages": table["pages"],
                "uncertainty": uncertainty, "catalogue_matches": candidates,
                "ai_draft": {
                    "vehicle_id": request.vehicle["id"], "generation_id": generation_id, "generated_at": generated_at,
                    "provider": result.provider, "model": result.model, "prompt_version": 1,
                    "warnings": result.warnings, "evidence": evidence, "source_rows": row.source_rows,
                    "action": row.action, "rule": row.rule.model_dump() if row.rule and not manual else None,
                    "source_page": table["pages"][0] if table["pages"] else None,
                    "manual_entry_required": manual, "reviewed_at": None,
                },
            }
            rows.append(suggestion)
            identities[(row.name.casefold(), row.action)].append(suggestion)
    except ValueError:
        raise HTTPException(503, "The AI response cited evidence outside the selected task rows or table. No draft was saved; retry or use manual entry.") from None
    for duplicates in identities.values():
        if len(duplicates) > 1:
            for row in duplicates:
                row["ai_draft"].update(manual_entry_required=True, rule=None)
                row["uncertainty"].append("Several rules were proposed for the same operation. Enter this task manually after checking all conditions.")
    covered = {index for row in rows for index in row["ai_draft"]["source_rows"]}
    omitted = sorted(set(request.task_rows) - covered)
    if omitted:
        warning = "No AI proposal was produced for table rows " + ", ".join(str(index + 1) for index in omitted) + ". Check those rows manually."
        for row in rows:
            row["ai_draft"]["warnings"] = [*row["ai_draft"]["warnings"], warning]
    return rows


def save_generated(state, request, result, user_id):
    rows = proposals(state, request, result)
    replaced = {row["suggestion_id"] for row in for_table(state, request.vehicle["id"], request.table_id)}
    kept = [row for row in state["suggestions"] if row["suggestion_id"] not in replaced]
    if len(kept) + len(rows) > 10000:
        raise HTTPException(422, "This document has too many suggestions. Review a smaller source document.")
    return maintenance.save(state, {"suggestions": [*kept, *rows]}, user_id)


def review_row(document, state, suggestion_id, request, user_id):
    rows = deepcopy(state["suggestions"])
    row = next((row for row in rows if row["suggestion_id"] == suggestion_id and row.get("ai_draft")), None)
    if row is None:
        raise HTTPException(404, "AI schedule row not found in this document revision.")
    draft = row["ai_draft"]
    if not db.all_rows("document_vehicles", document_id=document["id"], vehicle_id=draft["vehicle_id"]):
        raise HTTPException(409, "This document no longer covers the draft's vehicle. Check its coverage before continuing.")
    if request.mapped_item_id is not None:
        db.get("maintenance_items", request.mapped_item_id)
    if document["source_type"] == "md" and request.source_page is not None:
        raise HTTPException(422, "Markdown sources use table references, not PDF pages.")
    if request.status == "accepted":
        maintenance.validate_mapping(request.mapped_item_id)
        if not request.confirm_review:
            raise HTTPException(422, "Confirm that you checked this row and its conditions against the original.")
        if draft["manual_entry_required"]:
            raise HTTPException(422, "This timing needs manual entry. Skip this proposal and add the task manually.")
        if request.action is None or request.mapped_item_id is None:
            raise HTTPException(422, "Choose the operation and a matching service-library item before accepting.")
        item = db.get("maintenance_items", request.mapped_item_id)
        if item["action"] != request.action:
            raise HTTPException(422, "The selected item's action must match the reviewed operation.")
        issues = rule_issues(request.rule)
        if issues:
            raise HTTPException(422, " ".join(issues))
        if document["source_type"] == "pdf" and not request.source_page:
            raise HTTPException(422, "Enter the PDF page supporting this rule.")
        if any(other["suggestion_id"] != suggestion_id and other["status"] == "accepted"
               and other.get("ai_draft", {}).get("vehicle_id") == draft["vehicle_id"]
               and other.get("mapped_item_id") == str(request.mapped_item_id) for other in rows):
            raise HTTPException(422, "Another accepted AI row already uses this service task. Check for separate or conflicting timing before entering it manually.")
        review_questions.check_schedule({"vehicle_id": draft["vehicle_id"], "entries": [
            {"itemId": str(request.mapped_item_id), "rule": {"sourceDocumentId": document["id"]}}]})
    row.update(status=request.status, edited_name=request.edited_name,
               mapped_item_id=str(request.mapped_item_id) if request.mapped_item_id else None)
    draft.update(action=request.action, rule=request.rule.model_dump() if request.rule else None,
                 source_page=request.source_page,
                 reviewed_at=datetime.now(timezone.utc).isoformat() if request.status == "accepted" else None)
    return maintenance.save(state, {"suggestions": rows}, user_id)
