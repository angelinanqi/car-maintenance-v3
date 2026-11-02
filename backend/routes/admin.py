"""Shared catalogue and human-verified maintenance data."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, Field, field_validator

from backend import auth, db, settings
from backend.locks import content_lock
from backend.models import ReviewConfirmation, Rule
from shared.models import MechanicQuestionDraft
from shared.models import InputModel
from backend.services import catalogue as catalogue_service
from backend.services import review_questions
from backend.services.admin_maintenance import create_once, existing_create, check_revision, change_schedule

router = APIRouter(prefix="/admin", tags=["Admin MVP"], dependencies=[Depends(auth.require_admin)])
mobile_router = APIRouter(prefix="/mobile", tags=["Mobile shared catalogue"])


class ChatStartersInput(InputModel):
    expected_updated_at: AwareDatetime
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
    row = db.get("chat_settings", "default")
    return {"questions": row["starter_questions"], 'updated_at': row['updated_at']}


def update_chat_settings(expected, values):
    from datetime import datetime
    with content_lock('chat-settings'):
        row = db.get('chat_settings', 'default')
        # Reconcile a lost acknowledgement without overwriting a newer edit.
        if all(row.get(key) == value for key, value in values.items()):
            return row
        if datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) != expected:
            raise HTTPException(409, 'Chatbot settings changed. Your edits are kept. Reload the saved version and review before saving again.')
        rows = (db.client().table('chat_settings').update(values).eq('id', 'default')
                .eq('updated_at', row['updated_at']).execute().data)
        if not rows:
            raise HTTPException(409, 'Chatbot settings changed while saving. Your edits are kept. Reload the saved version before retrying.')
        return rows[0]


@router.put("/chat-starters")
def save_chat_starters(request: ChatStartersInput):
    row = update_chat_settings(request.expected_updated_at, {"starter_questions": request.questions})
    return {"questions": row["starter_questions"], 'updated_at': row['updated_at']}


class CompanionSettingsInput(InputModel):
    expected_updated_at: AwareDatetime
    mechanic_template: MechanicQuestionDraft | None = None
    mechanic_details: list[str] = Field(default_factory=list, max_length=12)

    @field_validator('mechanic_details')
    @classmethod
    def valid_details(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError('Preparation notes must contain 1 to 500 characters.')
        return [value.strip() for value in values]


@router.get('/companion-settings')
def companion_settings():
    row = db.get('chat_settings', 'default')
    return {'mechanic_template': row.get('mechanic_template'), 'mechanic_details': row.get('mechanic_details', []), 'updated_at': row['updated_at']}


@router.put('/companion-settings')
def save_companion_settings(request: CompanionSettingsInput):
    return update_chat_settings(request.expected_updated_at, request.model_dump(mode='json', exclude={'expected_updated_at'}))


class ManufacturerInput(InputModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class ModelInput(ManufacturerInput):
    manufacturer_id: UUID


class ItemInput(InputModel):
    id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(default='', max_length=200)
    description: str = ""
    action: Literal["inspect", "replace", "service"]
    active: bool = True


class ScheduleEntry(InputModel):
    itemId: UUID | None = None
    action: Literal["inspect", "replace", "service"] = "replace"
    rule: Rule = Field(default_factory=Rule)


class WorkContext(InputModel):
    document_id: UUID | None = None
    source_revision: UUID | None = None
    page: int = Field(default=1, ge=1)


class ScheduleInput(InputModel):
    id: UUID | None = None
    expected_updated_at: AwareDatetime | None = None
    vehicle_id: UUID
    entries: list[ScheduleEntry] = Field(default_factory=list)
    admin_note: str = Field(default="", max_length=4000)
    work_context: WorkContext = Field(default_factory=WorkContext)


class ScheduleReview(ReviewConfirmation):
    expected_updated_at: AwareDatetime


class ScheduleRevision(InputModel):
    expected_updated_at: AwareDatetime


def validate_schedule(values, publishing=False):
    vehicle_id = values["vehicle_id"]
    db.get("knowledge_vehicles", vehicle_id)
    if publishing:
        review_questions.check_schedule(values)
    items = set()
    for index, entry in enumerate(values["entries"], 1):
        item_id = entry["itemId"]
        task = f"Task {index}"
        if item_id:
            item = db.get("maintenance_items", item_id)
            task += f" ({item['title']})"
            if item_id in items:
                raise HTTPException(422, "A schedule cannot contain duplicate maintenance items.")
            items.add(item_id)
            if item["action"] != entry["action"]:
                raise HTTPException(422, "The rule action must match the standard item's action.")
            if publishing and not item["active"]:
                raise HTTPException(422, "Published schedules require active maintenance items.")
        rule = entry["rule"]
        document_id = rule["sourceDocumentId"]
        markdown_source = False
        if document_id:
            document = db.get("documents", document_id)
            markdown_source = document['source_type'] == 'md'
            if rule.get('sourceRevision') and rule['sourceRevision'] != document['source_revision']:
                raise HTTPException(409, 'The schedule source revision changed. Review and import its current source again.')
            if not db.all_rows("document_vehicles", document_id=document_id, vehicle_id=vehicle_id):
                raise HTTPException(422, "The source document must be associated with the selected vehicle.")
            if rule.get('sourceTableId'):
                if not rule.get('sourceRevision'):
                    raise HTTPException(422, 'A table reference requires its document revision.')
                reviews = db.all_rows('maintenance_assistance', document_id=document_id, source_revision=rule['sourceRevision'])
                review = reviews[0] if reviews else None
                allowed = ({s['table_id'] for s in review['selections']} | {b['table_id'] for b in review['bookmarks']}) if review else set()
                if rule['sourceTableId'] not in allowed:
                    raise HTTPException(422, 'Confirm the source table or create its manual bookmark before saving.')
                if rule.get('sourceSuggestionId'):
                    suggestion = next((s for s in review['suggestions'] if s['suggestion_id'] == rule['sourceSuggestionId']), None)
                    if (not suggestion or suggestion['table_id'] != rule['sourceTableId']
                            or suggestion['status'] != 'accepted' or suggestion.get('mapped_item_id') != item_id):
                        raise HTTPException(422, 'The source suggestion must be accepted and mapped to the selected maintenance item.')
                    draft = suggestion.get('ai_draft')
                    if draft and (draft['vehicle_id'] != vehicle_id or draft.get('manual_entry_required')
                                  or not draft.get('reviewed_at')):
                        raise HTTPException(422, 'AI schedule rows must be reviewed for this vehicle before they can be used.')
            if markdown_source and (rule.get('sourcePage') or not (rule.get('sourceRevision') and rule.get('sourceTableId'))):
                raise HTTPException(422, 'Markdown rules require a reviewed table/bookmark and revision, without a PDF page.')
        if not publishing:
            continue
        if not item_id:
            raise HTTPException(422, f"{task}: choose a maintenance item before publishing.")
        if not document_id:
            raise HTTPException(422, f"{task}: choose the reference document before publishing.")
        if not markdown_source and not rule["sourcePage"]:
            raise HTTPException(422, f"{task}: enter the page in the PDF manual before publishing.")
        if rule["type"] == "recurring" and not (rule["distanceKm"] or rule["months"]):
            raise HTTPException(422, f"{task}: enter a distance or time interval before publishing.")
        if rule["type"] == "milestone" and not (rule["distanceMilestones"] or rule["monthMilestones"]):
            raise HTTPException(422, f"{task}: enter the service mileages or vehicle ages before publishing.")
        if rule["type"] == "informational" and not (rule["conditions"] or rule["notes"]):
            raise HTTPException(422, f"{task}: describe the conditions or guidance before publishing.")
    if publishing and not values["entries"]:
        raise HTTPException(422, "Add at least one verified schedule rule before publishing.")


@router.get("/catalogue")
def catalogue():
    return catalogue_service.catalogue()

@router.post("/manufacturers", status_code=201)
def create_manufacturer(request: ManufacturerInput):
    return create_once('vehicle_manufacturers', request.id, request.model_dump(mode='json', exclude={'id'}))


@router.patch("/manufacturers/{record_id}")
def edit_manufacturer(record_id: UUID, request: ManufacturerInput):
    return db.update("vehicle_manufacturers", record_id, request.model_dump(mode="json", exclude={'id'}))


@router.post("/models", status_code=201)
def create_model(request: ModelInput):
    db.get("vehicle_manufacturers", request.manufacturer_id)
    return create_once('vehicle_models', request.id, request.model_dump(mode='json', exclude={'id'}))


@router.patch("/models/{record_id}")
def edit_model(record_id: UUID, request: ModelInput):
    old = db.get("vehicle_models", record_id)
    if old["manufacturer_id"] != str(request.manufacturer_id):
        raise HTTPException(409, "Create a new model to change its manufacturer; existing vehicle identities must remain stable.")
    return db.update("vehicle_models", record_id, request.model_dump(mode="json", exclude={'id'}))


@router.get("/maintenance-items")
def items(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("maintenance_items", offset=offset, limit=limit)


@router.post("/maintenance-items", status_code=201)
def create_item(request: ItemInput):
    return create_once('maintenance_items', request.id, request.model_dump(mode='json', exclude={'id'}))


@router.patch("/maintenance-items/{item_id}")
def edit_item(item_id: UUID, request: ItemInput):
    old = db.get("maintenance_items", item_id)
    if old["action"] != request.action:
        raise HTTPException(409, "Create a separate maintenance item to change its action. Existing rule/history identities must remain stable.")
    return db.update("maintenance_items", item_id, request.model_dump(mode="json", exclude={'id'}))


@router.get("/schedule-drafts")
def schedule_drafts(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    rows = db.list_rows("manufacturer_schedules", offset=offset, limit=limit, status="draft")
    return [{key: row.get(key) for key in ("id", "vehicle_id", "revision", "updated_at", "admin_note")} for row in rows]


@router.get("/schedules")
def schedules(vehicle_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("manufacturer_schedules", offset=offset, limit=limit, vehicle_id=str(vehicle_id))


@router.post("/schedules", status_code=201)
def create_schedule(request: ScheduleInput):
    values = request.model_dump(mode="json", exclude={'id', 'expected_updated_at'})
    with content_lock("schedule-sources"), content_lock("schedule-vehicle:" + values["vehicle_id"]):
        previous = existing_create('manufacturer_schedules', request.id, values)
        if previous:
            return previous
        validate_schedule(values)
        existing = db.all_rows("manufacturer_schedules", vehicle_id=values["vehicle_id"])
        values["revision"] = max((row["revision"] for row in existing), default=0) + 1
        return create_once('manufacturer_schedules', request.id, values)


@router.patch("/schedules/{schedule_id}")
def edit_schedule(schedule_id: UUID, request: ScheduleInput):
    with content_lock("schedule-sources"), content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        if old["status"] != "draft" or old["vehicle_id"] != str(request.vehicle_id):
            raise HTTPException(409, "Create a draft revision to change a published schedule or its vehicle.")
        values = request.model_dump(mode="json", exclude={'id', 'expected_updated_at'})
        if request.expected_updated_at is not None and all(old.get(key) == value for key, value in values.items()):
            return old  # Reconcile a successful save whose response was lost.
        check_revision(old, request.expected_updated_at)
        validate_schedule(values)
        return change_schedule(old, request.expected_updated_at, values)


@router.post("/schedules/{schedule_id}/validate")
def check_schedule(schedule_id: UUID):
    validate_schedule(db.get("manufacturer_schedules", schedule_id), publishing=True)
    return {"valid": True, "message": "Configuration is valid. Human source verification is still required."}


@router.post("/schedules/{schedule_id}/publish")
def publish_schedule(schedule_id: UUID, request: ScheduleReview):
    with content_lock("schedule-sources"), content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        check_revision(old, request.expected_updated_at)
        if old["status"] == "superseded":
            raise HTTPException(409, "Create a new draft to revise a superseded schedule.")
        validate_schedule(old, publishing=True)
        result = db.client().rpc("publish_manufacturer_schedule", {
            "schedule_id": str(schedule_id), "expected_updated_at": old['updated_at']}).execute().data
        return result[0] if isinstance(result, list) else result


@router.post("/schedules/{schedule_id}/withdraw")
def withdraw_schedule(schedule_id: UUID, request: ScheduleRevision):
    with content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        if old["status"] != "published":
            raise HTTPException(409, "Only a published schedule can be withdrawn.")
        # Keep verified revisions, personal tasks and history. The next mobile
        # snapshot no longer supplies manufacturer rules from this row.
        return change_schedule(old, request.expected_updated_at, {"status": "superseded"})


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_draft_schedule(schedule_id: UUID, expected_updated_at: AwareDatetime):
    with content_lock("schedule:" + str(schedule_id)):
        old = db.get("manufacturer_schedules", schedule_id)
        if old["status"] != "draft":
            raise HTTPException(409, "Only draft schedules can be deleted. Withdraw a published schedule to keep its history.")
        change_schedule(old, expected_updated_at, delete=True)


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
    links = catalogue_service.item_lessons()
    rows = db.list_rows("maintenance_items", offset=offset, limit=limit, active=True)
    return [{**row, "lessonIds": links.get(row['id'], [])} for row in rows]
