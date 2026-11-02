"""Admin-only clarification notes. These records are never driver guidance."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, field_validator
from backend import auth, db, settings
from backend.locks import content_lock
from shared.models import InputModel
from backend.services.review_questions import TABLE
from backend.services.review_questions import source_history

router = APIRouter(prefix="/admin/review-questions", tags=["Admin clarification"], dependencies=[Depends(auth.require_admin)])


class QuestionInput(InputModel):
    document_id: UUID
    source_revision: UUID
    vehicle_id: UUID | None = None
    schedule_id: UUID | None = None
    item_id: UUID | None = None
    source_page: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=4000)
    excerpt: str = Field(default="", max_length=2000)

    @field_validator("title", "question")
    @classmethod
    def meaningful_text(cls, value):
        if not value.strip():
            raise ValueError("Enter the question you need to clarify.")
        return value.strip()


class Decision(InputModel):
    version: int = Field(ge=1)
    status: Literal["open", "resolved"]
    resolution: str = Field(default="", max_length=4000)


@router.get("")
def questions(document_id: UUID | None = None, vehicle_id: UUID | None = None,
              status: Literal["open", "resolved"] | None = None,
              offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    filters = {}
    if document_id:
        filters["document_id"] = list(source_history(document_id))
    if status:
        filters["status"] = status
    rows = db.all_rows(TABLE, **filters)
    if vehicle_id:
        source_ids = {identity for link in db.all_rows("document_vehicles", vehicle_id=str(vehicle_id)) for identity in source_history(link["document_id"])}
        rows = [row for row in rows if row.get("vehicle_id") == str(vehicle_id)
                or not row.get("vehicle_id") and row["document_id"] in source_ids]
    page = rows[offset:offset + limit]
    if not page:
        return []
    documents = {row["id"]: row for row in db.all_rows("documents", id=list({row["document_id"] for row in page}))}
    vehicle_ids = list({row["vehicle_id"] for row in page if row.get("vehicle_id")})
    vehicles = {row["id"]: row for row in db.all_rows("knowledge_vehicles", id=vehicle_ids)} if vehicle_ids else {}
    return [{**row, "document_name": documents.get(row["document_id"], {}).get("name", "Reference document"),
             "vehicle_name": vehicles.get(row.get("vehicle_id"), {}).get("name"),
             "source_changed": documents.get(row["document_id"], {}).get("source_revision") != row["source_revision"]} for row in page]


@router.post("", status_code=201)
def create_question(request: QuestionInput, identity=Depends(auth.require_admin)):
    with content_lock("schedule-sources"), content_lock(request.document_id):
        document = db.get("documents", request.document_id)
        if document["source_revision"] != str(request.source_revision):
            raise HTTPException(409, "The document changed. Reload before recording this question.")
        if document["source_type"] == "md" and request.source_page is not None:
            raise HTTPException(422, "Use the quoted passage to identify a section in this document.")
        if request.schedule_id:
            schedule = db.get("manufacturer_schedules", request.schedule_id)
            if schedule["vehicle_id"] != str(request.vehicle_id):
                raise HTTPException(422, "This schedule belongs to a different vehicle.")
        if request.vehicle_id:
            db.get("knowledge_vehicles", request.vehicle_id)
            if not db.all_rows("document_vehicles", document_id=str(request.document_id), vehicle_id=str(request.vehicle_id)):
                raise HTTPException(422, "Choose a reference that covers this vehicle.")
        elif request.item_id:
            raise HTTPException(422, "A service task question needs its vehicle.")
        if request.item_id:
            db.get("maintenance_items", request.item_id)
        if not request.vehicle_id:
            db.update("documents", request.document_id, {"source_fidelity_verified": False})
        return db.insert(TABLE, {**request.model_dump(mode="json"), "created_by": identity["user"]["id"]})


@router.patch("/{question_id}")
def decide_question(question_id: UUID, request: Decision):
    with content_lock("schedule-sources"), content_lock("review-question:" + str(question_id)):
        old = db.get(TABLE, question_id)
        if old["version"] != request.version:
            raise HTTPException(409, "Someone updated this question. Refresh it before saving your decision.")
        if request.status == "resolved" and not request.resolution.strip():
            raise HTTPException(422, "Record what was clarified and the reference used before resolving the question.")
        return db.update(TABLE, question_id, {"status": request.status, "resolution": request.resolution.strip(),
                         "resolved_at": datetime.now(timezone.utc).isoformat() if request.status == "resolved" else None,
                         "version": old["version"] + 1})
