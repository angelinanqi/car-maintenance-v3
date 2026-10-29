"""Private, revision-bound tests over one document using the production RAG path."""
import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
from uuid import UUID

from fastapi import HTTPException
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from backend import db, settings
from backend.locks import content_lock
from backend.services import rag_client
from backend.services.documents import now
from backend.services.source_assets import extraction, element
from shared.document_testing import DocumentTestRequest
from shared.models import InputModel
from shared.source_elements import sanitize_table
from typing import Literal

QUESTIONS = "document_test_questions"
RUNS = "document_test_runs"
logger = logging.getLogger(__name__)


class QuestionInput(InputModel):
    question: str = Field(min_length=1, max_length=4000)
    expected: str = Field(default="", max_length=2000)
    scope_type: Literal["vehicle", "category"]
    scope_id: UUID
    active: bool = True


class QuestionEdit(QuestionInput):
    version: int = Field(ge=1)


class RunInput(InputModel):
    run_id: UUID
    source_revision: UUID
    question_version: int = Field(ge=1)


class ReviewInput(InputModel):
    version: int = Field(ge=1)
    decision: Literal["not_reviewed", "passed", "needs_fixing"]
    note: str = Field(default="", max_length=2000)


def ready(document):
    return (document["status"] == "processed" and document.get("indexed_revision") == document["source_revision"]
            and document.get("chunk_count", 0) > 0 and bool(document.get("extraction_storage_path"))
            and not document.get("superseded_by_id"))


def contexts(document_id):
    choices = []
    for kind, links, table in (("vehicle", "document_vehicles", "knowledge_vehicles"),
                               ("category", "document_categories", "guide_categories")):
        for link in db.all_rows(links, document_id=str(document_id)):
            context = db.get(table, link[kind + "_id"])
            if kind == "vehicle" and not context.get("active", True):
                continue
            label = " · ".join(str(context[key]) for key in ("name", "year", "engine", "variant") if context.get(key))
            choices.append({"scope_type": kind, "scope_id": context["id"], "label": label})
    return sorted(choices, key=lambda choice: (choice["scope_type"], choice["label"]))


def preview_scope(document, kind, scope_id, scope_data=None):
    links = "document_vehicles" if kind == "vehicle" else "document_categories"
    table = "knowledge_vehicles" if kind == "vehicle" else "guide_categories"
    if scope_data is None:
        document_links = db.all_rows(links, document_id=document["id"])
        context = None
    else:
        document_links = scope_data[links].get(document["id"], [])
        context = scope_data[table].get(str(scope_id))
    if not any(link[kind + "_id"] == str(scope_id) for link in document_links):
        raise HTTPException(409, "This document no longer covers the selected test context. Update the saved question.")
    if scope_data is None:
        context = db.get(table, scope_id)
    if not context:
        raise HTTPException(409, "The selected test context is no longer available.")
    if kind == "vehicle" and not context.get("active", True):
        raise HTTPException(409, "Select an active vehicle for this test.")
    vehicles = ({row["id"]: row for row in db.all_rows("knowledge_vehicles")}
                if scope_data is None else scope_data["knowledge_vehicles"])
    vehicle_links = (db.all_rows("document_vehicles", document_id=document["id"])
                     if scope_data is None else scope_data["document_vehicles"].get(document["id"], []))
    applicable = [vehicles[link["vehicle_id"]] for link in vehicle_links
                  if link["vehicle_id"] in vehicles]
    name = f"{document['id']}_{document['indexed_revision']}"
    metadata = {"document_id": document["id"], "document_title": document["name"],
        "document_type": document.get("document_type", "other_reference"),
        "vehicle_independent": document.get("vehicle_independent", False),
        "source_fidelity_verified": document.get("source_fidelity_verified", False),
        "year": document.get("year", ""), "engine": document.get("engine", ""), "variant": document.get("variant", ""),
        "applicable_vehicles": sorted(applicable, key=lambda vehicle: vehicle["id"]),
        "index_revision": document.get("indexed_revision"), "indexed_chunk_count": document.get("chunk_count", 0)}
    return {"scope_type": kind, "scope_id": str(scope_id), "label": context["name"],
        "vehicle": context if kind == "vehicle" else None, "document_ids": [name], "document_metadata": {name: metadata},
        "content_sources": [], "video_ids": [], "published": False,
        "vehicle_codes": sorted(vehicle["code"] for vehicle in vehicles.values() if vehicle.get("code"))}


def fingerprint(scope):
    return sha256(json.dumps(scope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def question_for(document_id, question_id):
    question = db.get(QUESTIONS, question_id)
    if question["document_id"] != str(document_id):
        raise HTTPException(404, "Test question not found.")
    return question


def recent_runs(document_id):
    return db.read_rows(db.client().table(RUNS).select("*").eq("document_id", str(document_id))
                        .order("started_at", desc=True).order("id", desc=True).limit(50))


def outdated(document, question, run, signatures=None, scope_data=None):
    if not ready(document) or run["source_revision"] != document["source_revision"]:
        return "The document was changed or is awaiting indexing. Rerun after preparation finishes."
    if not question or not question["active"] or question["version"] != run["question_version"]:
        return "The saved question or its context changed. Rerun the current question."
    key = (question["scope_type"], question["scope_id"])
    try:
        if signatures is not None and key in signatures:
            current = signatures[key]
        else:
            current = fingerprint(preview_scope(document, *key, scope_data=scope_data))
            if signatures is not None:
                signatures[key] = current
        if current != run["context_fingerprint"]:
            return "Document verification, coverage or vehicle details changed. Rerun this question."
    except HTTPException:
        return "The test context is no longer available for this document."
    return ""


def expired(run):
    started = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
    return run["status"] == "running" and datetime.now(timezone.utc) - started > timedelta(seconds=settings.RAG_SERVICE_TIMEOUT + 60)


def run_view(document, question, run, signatures=None):
    reason = outdated(document, question, run, signatures)
    result = {**run, "outdated": bool(reason) or run["status"] == "stale", "outdated_reason": reason}
    if expired(run):
        result.update(status="failed", error="This test was interrupted. Its saved question is available to run again.")
    return result


def workspace(document_id, run_id=None):
    document = db.get("documents", document_id)
    questions = db.all_rows(QUESTIONS, document_id=str(document_id))
    by_id = {question["id"]: question for question in questions}
    signatures = {}
    runs = recent_runs(document_id)
    linked_run_unavailable = False
    if run_id and not any(run["id"] == str(run_id) for run in runs):
        try:
            linked = db.get(RUNS, run_id)
            if linked["document_id"] == str(document_id):
                runs.append(linked)
            else:
                linked_run_unavailable = True
        except HTTPException as error:
            if error.status_code != 404:
                raise
            linked_run_unavailable = True
    return {"document_id": str(document_id), "source_revision": document["source_revision"], "ready": ready(document),
        "source_verified": bool(document.get("source_fidelity_verified")), "contexts": contexts(document_id),
        "questions": [question for question in questions if question["active"]],
        "linked_run_unavailable": linked_run_unavailable,
        "runs": [run_view(document, by_id.get(run["question_id"]), run, signatures) for run in runs]}


def latest_questions():
    """Page active questions with only their latest run's summary metadata."""
    fields = "id,document_id,question_id,source_revision,question_version,context_fingerprint,status,decision,started_at"
    rows = []
    while True:
        query = (db.client().table(QUESTIONS)
                 .select(f"id,document_id,scope_type,scope_id,active,version,{RUNS}({fields})")
                 .eq("active", True).order("id")
                 .order("started_at", desc=True, foreign_table=RUNS).order("id", desc=True, foreign_table=RUNS)
                 .limit(1, foreign_table=RUNS).range(len(rows), len(rows) + settings.API_PAGE_SIZE - 1))
        page = db.read_rows(query)
        rows.extend(page)
        if len(page) < settings.API_PAGE_SIZE:
            return rows


def summary_scope_data():
    data = {}
    for table in ("knowledge_vehicles", "guide_categories"):
        data[table] = {row["id"]: row for row in db.all_rows(table)}
    for table in ("document_vehicles", "document_categories"):
        data[table] = {}
        for link in db.all_rows(table):
            data[table].setdefault(link["document_id"], []).append(link)
    return data


def summaries():
    """One exclusive state per active question; publication is independent."""
    documents = {document["id"]: document for document in db.all_rows("documents")}
    questions = latest_questions()
    scope_data = summary_scope_data() if any(question[RUNS] for question in questions) else None
    states = ("needs_fixing", "outdated", "failed", "not_reviewed", "never_run", "running", "passed")
    result = {identity: {"total": 0, **{state: 0 for state in states}, "targets": {}} for identity in documents}
    signatures = {}
    for question in questions:
        identity = question["document_id"]
        if not question["active"] or identity not in documents:
            continue
        summary = result[identity]
        latest = question[RUNS][0] if question[RUNS] else None
        if latest is None:
            state = "never_run"
        elif latest["status"] == "stale" or outdated(documents[identity], question, latest,
                                                      signatures.setdefault(identity, {}), scope_data):
            state = "outdated"
        elif latest["status"] == "running":
            state = "failed" if expired(latest) else "running"
        elif latest["status"] == "failed":
            state = "failed"
        else:
            state = latest["decision"]
        summary["total"] += 1
        summary[state] += 1
        summary["targets"].setdefault(state, {"question_id": question["id"], "run_id": latest["id"] if latest else None})
    return result


def save_question(document_id, request, user_id, question_id=None):
    with content_lock("document-tests:" + str(document_id)), content_lock(document_id):
        document = db.get("documents", document_id)
        if request.active:
            preview_scope(document, request.scope_type, request.scope_id)
        values = request.model_dump(mode="json", exclude={"version"})
        if question_id:
            old = question_for(document_id, question_id)
            if old["version"] != request.version:
                raise HTTPException(409, "This question changed in another tab. Reload before saving.")
            return db.update(QUESTIONS, question_id, {**values, "version": old["version"] + 1})
        if len(db.all_rows(QUESTIONS, document_id=str(document_id), active=True)) >= 100:
            raise HTTPException(422, "Archive an unused question before adding more than 100 active questions.")
        return db.insert(QUESTIONS, {**values, "document_id": str(document_id), "created_by": str(user_id)})


def prepare(document_id, question_id, request, user_id):
    with content_lock("document-tests:" + str(document_id)), content_lock(document_id):
        question = question_for(document_id, question_id)
        try:
            previous = db.get(RUNS, request.run_id)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            previous = None
        if previous:
            if (previous["document_id"] != str(document_id) or previous["question_id"] != str(question_id)
                    or previous["source_revision"] != str(request.source_revision) or previous["question_version"] != request.question_version):
                raise HTTPException(409, "This test request identifier was already used for another run.")
            return None, None, previous
        document = db.get("documents", document_id)
        if not ready(document) or document["source_revision"] != str(request.source_revision):
            raise HTTPException(409, "Wait for the current document revision to finish indexing, then reload the tests.")
        if not question["active"] or question["version"] != request.question_version:
            raise HTTPException(409, "The question changed. Reload before running it.")
        for pending in db.all_rows(RUNS, document_id=str(document_id), status="running"):
            if not expired(pending):
                raise HTTPException(409, "Another document test is still running. Wait for its result or reload saved tests.")
            db.update(RUNS, pending["id"], {"status": "failed", "finished_at": now(), "error": "This test was interrupted. Run the saved question again."})
        scope = preview_scope(document, question["scope_type"], question["scope_id"])
        run = db.insert(RUNS, {"id": str(request.run_id), "document_id": str(document_id), "question_id": str(question_id),
            "source_revision": document["source_revision"], "question_version": question["version"],
            "question_snapshot": {key: question[key] for key in ("question", "expected", "scope_type", "scope_id")},
            "context_label": scope["label"], "context_fingerprint": fingerprint(scope),
            "source_verified": bool(document.get("source_fidelity_verified")), "started_by": str(user_id)})
        return document, scope, run


def resolved_result(document, reply):
    result = reply.model_dump(mode="json")
    for reference in result["sources"] + result["attachments"] + result["evidence"]:
        if reference["document_id"] != document["id"] or reference["source_revision"] != document["source_revision"]:
            raise ValueError("Preview returned evidence outside the selected document revision")
    with extraction(document) as archive:
        evidence = result["evidence"]
        for attachment in result["attachments"]:
            if not any(item.get("element_id") == attachment["element_id"] for item in evidence):
                evidence.append({"document_id": document["id"], "source_revision": document["source_revision"],
                    "chunk_id": "", "element_id": attachment["element_id"], "kind": attachment["kind"],
                    "label": attachment.get("reference_label"), "section_path": [], "excerpt": "",
                    "eligible": False, "cited": any(source.get("element_id") == attachment["element_id"] for source in result["sources"]),
                    "exclusion": "", "selected_reference": True})
        for item in evidence:
            item["pages"] = []  # Paragraphs do not have reliable source-page mapping.
            if item["kind"] == "paragraph":
                continue
            record = element(archive, item["element_id"])
            if record["kind"] != item["kind"]:
                raise ValueError("Preview evidence kind does not match the original")
            item.update(pages=record.get("pages", []), caption=record.get("caption", ""))
            if item["kind"] == "table":
                html = sanitize_table(record.get("html", ""))
                item["html"] = html if len(html) <= 100000 else ""
            else:
                item["image_path"] = f"/documents/{document['id']}/visuals/{record['element_id']}?revision={document['source_revision']}"
    return result


async def run_test(document_id, question_id, request, user_id):
    document, scope, run = await run_in_threadpool(prepare, document_id, question_id, request, user_id)
    if document is None:
        current = await run_in_threadpool(db.get, "documents", document_id)
        question = await run_in_threadpool(question_for, document_id, question_id)
        return run_view(current, question, run)
    result, error = None, None
    try:
        reply = await rag_client.test_document(DocumentTestRequest(message=run["question_snapshot"]["question"], scope=scope))
        result = await run_in_threadpool(resolved_result, document, reply)
    except asyncio.CancelledError:
        await run_in_threadpool(db.update, RUNS, run["id"], {"status": "failed", "finished_at": now(), "error": "The test was interrupted. Run it again."})
        raise
    except HTTPException as cause:
        error = str(cause.detail)
    except Exception:
        logger.exception("Document test failed for %s", document_id)
        error = "The test could not validate its evidence. Check preparation and retry."
    return await run_in_threadpool(finish, document_id, question_id, run, result, error)


def finish(document_id, question_id, run, result, error):
    with content_lock("document-tests:" + str(document_id)):
        old = db.get(RUNS, run["id"])
        document = db.get("documents", document_id)
        question = question_for(document_id, question_id)
        if old["status"] != "running":
            return run_view(document, question, old)
        stale = outdated(document, question, run)
        failed = error or result and result["response_type"] in {"retrieval_error", "generation_error"}
        saved = db.update(RUNS, run["id"], {"status": "stale" if stale else "failed" if failed else "completed",
            "result": result, "error": error or ("The retrieval or answer service did not complete. Retry this test." if failed else None),
            "finished_at": now()})
        return run_view(document, question, saved)


def review_run(document_id, run_id, request, user_id):
    with content_lock("document-tests:" + str(document_id)), content_lock(document_id):
        document = db.get("documents", document_id)
        run = db.get(RUNS, run_id)
        if run["document_id"] != str(document_id):
            raise HTTPException(404, "Test result not found.")
        question = question_for(document_id, run["question_id"])
        if run["status"] != "completed" or outdated(document, question, run):
            raise HTTPException(409, "Rerun the current question and document before reviewing this result.")
        if run["review_version"] != request.version:
            raise HTTPException(409, "Someone reviewed this result in another tab. Reload before saving.")
        if request.decision == "needs_fixing" and not request.note:
            raise HTTPException(422, "Describe what needs fixing so the next review can follow up.")
        saved = db.update(RUNS, run_id, {"decision": request.decision, "review_note": request.note,
            "reviewed_by": str(user_id), "reviewed_at": now(), "review_version": run["review_version"] + 1})
        return run_view(document, question, saved)
