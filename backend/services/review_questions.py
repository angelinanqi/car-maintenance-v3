"""Private questions that keep uncertain guidance out of new publications."""
from fastapi import HTTPException
from backend import db

TABLE = "admin_review_questions"


def source_history(document_id):
    """Replacement ancestors are known references, not automatically compared content."""
    documents = {}
    while document_id and str(document_id) not in documents:
        document = db.get("documents", document_id)
        documents[document["id"]] = document
        document_id = document.get("replacement_for_id")
    return documents


def open_questions():
    return db.all_rows(TABLE, status="open")


def check_document(document_id):
    questions = db.all_rows(TABLE, document_id=list(source_history(document_id)), status="open")
    if any(not question.get("vehicle_id") for question in questions):
        raise HTTPException(409, "Resolve this document’s open questions before approving or publishing it.")


def check_schedule(schedule):
    sources = {entry["rule"].get("sourceDocumentId") for entry in schedule["entries"]}
    sources.discard(None)
    sources = {identity for source in sources for identity in source_history(source)}
    items = {entry.get("itemId") for entry in schedule["entries"]}
    for question in open_questions():
        if question.get("vehicle_id") == schedule["vehicle_id"]:
            if not question.get("item_id") or question["item_id"] in items:
                raise HTTPException(409, "Resolve the open questions about these service tasks before making this schedule available.")
        elif not question.get("vehicle_id") and question["document_id"] in sources:
            raise HTTPException(409, "A reference document has an open question. Resolve it before making this schedule available.")


def document_usage(document_id):
    """Known references, with related guides explicitly distinguished from citations."""
    history = source_history(document_id)
    document = history[str(document_id)]
    vehicles = {row["id"]: row for row in db.all_rows("knowledge_vehicles")}
    items = {row["id"]: row for row in db.all_rows("maintenance_items")}
    schedules = []
    item_ids = set()
    for schedule in db.all_rows("manufacturer_schedules"):
        entries = [entry for entry in schedule["entries"] if entry["rule"].get("sourceDocumentId") in history]
        if not entries:
            continue
        item_ids.update(entry["itemId"] for entry in entries if entry.get("itemId"))
        schedules.append({
            "id": schedule["id"], "vehicle_id": schedule["vehicle_id"],
            "vehicle_name": vehicles.get(schedule["vehicle_id"], {}).get("name", "Vehicle"),
            "revision": schedule["revision"], "status": schedule["status"],
            "tasks": [{"item_id": entry.get("itemId"), "title": items.get(entry.get("itemId"), {}).get("title", "Service task"),
                       "page": entry["rule"].get("sourcePage"), "source_document_name": history[entry["rule"]["sourceDocumentId"]]["name"]} for entry in entries],
        })
    guides = [{"id": guide["id"], "title": guide["title"], "status": guide["status"],
               "relationship": "shared_service_tasks"}
              for guide in db.all_rows("guides") if item_ids.intersection(guide.get("maintenance_item_ids", []))]
    return {"document_id": str(document_id), "document_name": document["name"], "schedules": schedules, "related_guides": guides}
