"""Shared catalogue and human-verified maintenance data."""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, field_validator, model_validator

from backend import auth, db, settings
from backend.locks import content_lock
from backend.models import InputModel, ReviewConfirmation
from backend.services import manuals

router = APIRouter(prefix="/admin", tags=["Admin MVP"], dependencies=[Depends(auth.require_admin)])
mobile_router = APIRouter(prefix="/mobile", tags=["Mobile shared catalogue"])


class ChatStartersInput(InputModel):
    questions: list[str] = Field(max_length=20)

    @field_validator("questions")
    @classmethod
    def valid_questions(cls, values):
        values = [value.strip() for value in values]
        if any(not value or len(value) > 300 for value in values):
            raise ValueError("Each starter question must contain 1 to 300 characters.")
        if len(values) != len(set(values)):
            raise ValueError("Starter questions must be unique.")
        return values


@router.get("/chat-starters")
@mobile_router.get("/chat-starters")
def chat_starters():
    return {"questions": db.get("chat_settings", "default")["starter_questions"]}


@router.put("/chat-starters")
def save_chat_starters(request: ChatStartersInput):
    row = db.update("chat_settings", "default", {"starter_questions": request.questions})
    return {"questions": row["starter_questions"]}


class ManufacturerInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class ModelInput(ManufacturerInput):
    manufacturer_id: UUID


class ItemInput(InputModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = ""
    description: str = ""
    action: Literal["inspect", "replace", "service"]
    active: bool = True


class Rule(InputModel):
    type: Literal["recurring", "milestone", "informational"] = "recurring"
    distanceKm: int | None = Field(default=None, gt=0)
    months: int | None = Field(default=None, gt=0)
    distanceMilestones: list[int] = Field(default_factory=list)
    monthMilestones: list[int] = Field(default_factory=list)
    vehicleStartDate: date | None = None
    conditions: str = ""
    notes: str = ""
    sourceDocumentId: UUID | None = None
    sourcePage: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def check_structure(self):
        for values in (self.distanceMilestones, self.monthMilestones):
            if any(value <= 0 for value in values) or values != sorted(set(values)):
                raise ValueError("Milestones must be unique positive numbers in ascending order")
        if self.type != "recurring" and (self.distanceKm or self.months):
            raise ValueError("Only recurring rules may contain intervals")
        if self.type != "milestone" and (self.distanceMilestones or self.monthMilestones):
            raise ValueError("Only milestone rules may contain milestones")
        return self


class ScheduleEntry(InputModel):
    itemId: UUID | None = None
    action: Literal["inspect", "replace", "service"] = "replace"
    rule: Rule = Field(default_factory=Rule)


class ScheduleInput(InputModel):
    vehicle_id: UUID
    entries: list[ScheduleEntry] = Field(default_factory=list)


def validate_schedule(values, publishing=False):
    vehicle_id = values["vehicle_id"]
    db.get("knowledge_vehicles", vehicle_id)
    items = set()
    for entry in values["entries"]:
        item_id = entry["itemId"]
        if item_id:
            item = db.get("maintenance_items", item_id)
            if item_id in items:
                raise HTTPException(422, "A schedule cannot contain duplicate maintenance items.")
            items.add(item_id)
            if item["action"] != entry["action"]:
                raise HTTPException(422, "The rule action must match the standard item's action.")
            if publishing and not item["active"]:
                raise HTTPException(422, "Published schedules require active maintenance items.")
        rule = entry["rule"]
        document_id = rule["sourceDocumentId"]
        if document_id:
            document = db.get("documents", document_id)
            if document["source_type"] != "pdf":
                raise HTTPException(422, "Schedule page references require an original PDF.")
            if not db.all_rows("document_vehicles", document_id=document_id, vehicle_id=vehicle_id):
                raise HTTPException(422, "The source document must be associated with the selected vehicle.")
        if not publishing:
            continue
        if not item_id or not document_id or not rule["sourcePage"]:
            raise HTTPException(422, "Every published rule needs an item, source PDF and page.")
        if rule["type"] == "recurring" and not (rule["distanceKm"] or rule["months"]):
            raise HTTPException(422, "Recurring rules require a distance or time interval.")
        if rule["type"] == "milestone" and not (rule["distanceMilestones"] or rule["monthMilestones"]):
            raise HTTPException(422, "Milestone rules require explicit service milestones.")
        if rule["type"] == "informational" and not (rule["conditions"] or rule["notes"]):
            raise HTTPException(422, "Informational rules require conditions or guidance.")
    if publishing and not values["entries"]:
        raise HTTPException(422, "Add at least one verified schedule rule before publishing.")


@router.get("/catalogue")
def catalogue():
    vehicles = db.all_rows("knowledge_vehicles")
    docs = manuals.published_manuals()
    associations = db.all_rows("document_vehicles")
    schedules = db.all_rows("manufacturer_schedules", status="published")
    for vehicle in vehicles:
        vehicle["manual_available"] = any(manuals.applicable(document, vehicle['id'], associations) for document in docs)
        vehicle["manufacturer_schedule_available"] = any(s["vehicle_id"] == vehicle["id"] for s in schedules)
    return {"manufacturers": db.all_rows("vehicle_manufacturers"), "models": db.all_rows("vehicle_models"), "vehicles": vehicles}


@router.post("/manufacturers", status_code=201)
def create_manufacturer(request: ManufacturerInput):
    return db.insert("vehicle_manufacturers", request.model_dump(mode="json"))


@router.patch("/manufacturers/{record_id}")
def edit_manufacturer(record_id: UUID, request: ManufacturerInput):
    return db.update("vehicle_manufacturers", record_id, request.model_dump(mode="json"))


@router.post("/models", status_code=201)
def create_model(request: ModelInput):
    db.get("vehicle_manufacturers", request.manufacturer_id)
    return db.insert("vehicle_models", request.model_dump(mode="json"))


@router.patch("/models/{record_id}")
def edit_model(record_id: UUID, request: ModelInput):
    old = db.get("vehicle_models", record_id)
    if old["manufacturer_id"] != str(request.manufacturer_id):
        raise HTTPException(409, "Create a new model to change its manufacturer; existing vehicle identities must remain stable.")
    return db.update("vehicle_models", record_id, request.model_dump(mode="json"))


@router.get("/maintenance-items")
def items(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("maintenance_items", offset=offset, limit=limit)


@router.post("/maintenance-items", status_code=201)
def create_item(request: ItemInput):
    return db.insert("maintenance_items", request.model_dump(mode="json"))


@router.patch("/maintenance-items/{item_id}")
def edit_item(item_id: UUID, request: ItemInput):
    old = db.get("maintenance_items", item_id)
    if old["action"] != request.action:
        raise HTTPException(409, "Create a separate maintenance item to change its action. Existing rule/history identities must remain stable.")
    return db.update("maintenance_items", item_id, request.model_dump(mode="json"))


@router.get("/schedules")
def schedules(vehicle_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("manufacturer_schedules", offset=offset, limit=limit, vehicle_id=str(vehicle_id))


@router.post("/schedules", status_code=201)
def create_schedule(request: ScheduleInput):
    values = request.model_dump(mode="json")
    with content_lock("schedule-sources"), content_lock("schedule-vehicle:" + values["vehicle_id"]):
        validate_schedule(values)
        existing = db.all_rows("manufacturer_schedules", vehicle_id=values["vehicle_id"])
        values["revision"] = max((row["revision"] for row in existing), default=0) + 1
        return db.insert("manufacturer_schedules", values)


@router.patch("/schedules/{schedule_id}")
def edit_schedule(schedule_id: UUID, request: ScheduleInput):
    with content_lock("schedule-sources"), content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        if old["status"] != "draft" or old["vehicle_id"] != str(request.vehicle_id):
            raise HTTPException(409, "Create a draft revision to change a published schedule or its vehicle.")
        values = request.model_dump(mode="json")
        validate_schedule(values)
        return db.update("manufacturer_schedules", schedule_id, values)


@router.post("/schedules/{schedule_id}/validate")
def check_schedule(schedule_id: UUID):
    validate_schedule(db.get("manufacturer_schedules", schedule_id), publishing=True)
    return {"valid": True, "message": "Configuration is valid. Human source verification is still required."}


@router.post("/schedules/{schedule_id}/publish")
def publish_schedule(schedule_id: UUID, request: ReviewConfirmation):
    with content_lock("schedule-sources"), content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        if old["status"] == "superseded":
            raise HTTPException(409, "Create a new draft to revise a superseded schedule.")
        validate_schedule(old, publishing=True)
        result = db.client().rpc("publish_manufacturer_schedule", {"schedule_id": str(schedule_id)}).execute().data
        return result[0] if isinstance(result, list) else result


@router.post("/schedules/{schedule_id}/withdraw")
def withdraw_schedule(schedule_id: UUID):
    with content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        if old["status"] != "published":
            raise HTTPException(409, "Only a published schedule can be withdrawn.")
        # Keep verified revisions, personal tasks and history. The next mobile
        # snapshot no longer supplies manufacturer rules from this row.
        return db.update("manufacturer_schedules", schedule_id, {"status": "superseded"})


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_draft_schedule(schedule_id: UUID):
    with content_lock("schedule:" + str(schedule_id)):
        if db.get("manufacturer_schedules", schedule_id)["status"] != "draft":
            raise HTTPException(409, "Only draft schedules can be deleted. Withdraw a published schedule to keep its history.")
        db.delete("manufacturer_schedules", schedule_id)


@mobile_router.get("/vehicle-catalogue")
def mobile_catalogue(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    data = catalogue()
    manufacturers = {r["id"]: r for r in data["manufacturers"] if r["active"]}
    models = {r["id"]: r for r in data["models"] if r["active"] and r["manufacturer_id"] in manufacturers}
    result = []
    for row in data["vehicles"]:
        model = models.get(row.get("model_id"))
        if not model or not row["active"] or not row["year"].isdigit():
            continue
        result.append({"id": row["id"], "manufacturer": manufacturers[model["manufacturer_id"]]["name"],
            "model": model["name"], "year": int(row["year"]), "variant": row["variant"],
            "engine": row["engine"], "powertrain": row["powertrain"]})
    return result[offset:offset + limit]


@mobile_router.get("/maintenance-items")
def mobile_items(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    links = item_lessons()
    rows = db.list_rows("maintenance_items", offset=offset, limit=limit, active=True)
    return [{**row, "lessonIds": links.get(row['id'], [])} for row in rows]


def item_lessons():
    guides = db.all_rows("guides", status="published")
    categories = {r["id"] for r in db.all_rows("guide_categories", published=True)}
    links = {}
    for guide in guides:
        if guide['category_id'] and guide['category_id'] not in categories:
            continue
        for item_id in guide.get('maintenance_item_ids', []):
            links.setdefault(item_id, []).append(guide['id'])
    return links
