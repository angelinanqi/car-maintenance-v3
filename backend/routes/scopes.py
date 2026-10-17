from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from backend import auth, db
from backend.models import InputModel
from backend.services import scopes
from backend.services.documents import referencing_schedules
from backend.locks import content_lock

router = APIRouter(prefix="/knowledge", tags=["Knowledge scopes"])


class VehicleInput(InputModel):
    code: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    year: str = ""
    engine: str = ""
    variant: str = ""
    published: bool = False
    model_id: UUID | None = None
    powertrain: Literal["petrol", "diesel"] = "petrol"
    active: bool = True


class Associations(InputModel):
    vehicle_ids: list[UUID] = Field(default_factory=list)
    category_ids: list[UUID] = Field(default_factory=list)


class Publication(InputModel):
    published: bool


class Videos(InputModel):
    video_ids: list[str] = Field(default_factory=list)


@router.get("/scopes")
def list_scopes():
    return scopes.catalog()


@router.get("/manage", dependencies=[Depends(auth.require_admin)])
def manage_scopes():
    return {"vehicles": db.all_rows("knowledge_vehicles"),
            "categories": db.all_rows("guide_categories"),
            "document_vehicles": db.all_rows("document_vehicles"),
            "document_categories": db.all_rows("document_categories"),
            "videos": db.all_rows("knowledge_videos")}


@router.post("/vehicles", status_code=201, dependencies=[Depends(auth.require_admin)])
def create_vehicle(request: VehicleInput):
    if request.code == 'general':
        raise HTTPException(422, "The general code is reserved for vehicle-independent manual lookup.")
    if request.model_id:
        db.get("vehicle_models", request.model_id)
        if (len(request.year) != 4 or not request.year.isascii() or not request.year.isdigit()
                or not 1900 <= int(request.year) <= 2100):
            raise HTTPException(422, "Provide a single model year between 1900 and 2100.")
    return db.insert("knowledge_vehicles", request.model_dump(mode="json"))


@router.patch("/vehicles/{vehicle_id}", dependencies=[Depends(auth.require_admin)])
def edit_vehicle(vehicle_id: UUID, request: VehicleInput):
    old = db.get("knowledge_vehicles", vehicle_id)
    if request.code != old["code"]:
        raise HTTPException(409, "The vehicle code is used by the mobile manual catalogue and must remain stable. Create a new variant for a different identity.")
    if old.get("model_id") and old["model_id"] != str(request.model_id):
        raise HTTPException(409, "Create a new variant to change its model. Existing vehicle identities must remain stable.")
    if request.model_id:
        db.get("vehicle_models", request.model_id)
        if (len(request.year) != 4 or not request.year.isascii() or not request.year.isdigit()
                or not 1900 <= int(request.year) <= 2100):
            raise HTTPException(422, "Provide a single model year between 1900 and 2100.")
    return db.update("knowledge_vehicles", vehicle_id, request.model_dump(mode="json"))


@router.delete("/vehicles/{vehicle_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_vehicle(vehicle_id: UUID):
    raise HTTPException(409, "Deactivate catalogue vehicles instead of deleting them to preserve user and source identities.")


@router.patch("/categories/{category_id}/publication", dependencies=[Depends(auth.require_admin)])
def publish_category(category_id: UUID, request: Publication):
    return db.update("guide_categories", category_id, {"knowledge_published": request.published})


@router.get("/documents/{document_id}/associations", dependencies=[Depends(auth.require_admin)])
def get_associations(document_id: UUID):
    db.get("documents", document_id)
    return {"vehicle_ids": [r["vehicle_id"] for r in db.all_rows("document_vehicles", document_id=str(document_id))],
            "category_ids": [r["category_id"] for r in db.all_rows("document_categories", document_id=str(document_id))]}


@router.put("/documents/{document_id}/associations", dependencies=[Depends(auth.require_admin)])
def set_associations(document_id: UUID, request: Associations):
    # Add before removing; a failed write is explicit and safely retryable.
    with content_lock('schedule-sources'), content_lock(document_id):
        db.get("documents", document_id)
        required_vehicles = {schedule['vehicle_id'] for schedule in referencing_schedules(document_id)}
        if not required_vehicles.issubset({str(identity) for identity in request.vehicle_ids}):
            raise HTTPException(409, "A maintenance schedule references this document for a vehicle. Keep its source association for traceability.")
        for kind, table in (("vehicle", "knowledge_vehicles"), ("category", "guide_categories")):
            for identity in getattr(request, kind + "_ids"):
                db.get(table, identity)
        for kind, table in (("vehicle", "document_vehicles"), ("category", "document_categories")):
            desired = {str(i) for i in getattr(request, kind + "_ids")}
            existing = db.all_rows(table, document_id=str(document_id))
            current = {r[kind + "_id"] for r in existing}
            for identity in desired - current:
                db.insert(table, {"document_id": str(document_id), kind + "_id": identity})
            for row in existing:
                if row[kind + "_id"] not in desired:
                    db.delete(table, row["id"])
    return get_associations(document_id)


@router.put("/{scope_type}/{scope_id}/videos", dependencies=[Depends(auth.require_admin)])
def set_videos(scope_type: Literal["vehicle", "category"], scope_id: UUID, request: Videos):
    import re
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{11}", value) for value in request.video_ids):
        raise HTTPException(422, "Use valid YouTube video identifiers.")
    scopes.resolve(scope_type, scope_id, require_available=False)
    field = scope_type + "_id"
    with content_lock(scope_id):
        existing = db.all_rows("knowledge_videos", **{field: str(scope_id)})
        current = {r["video_id"] for r in existing}
        desired = list(dict.fromkeys(request.video_ids))
        for identity in desired:
            if identity not in current:
                db.insert("knowledge_videos", {field: str(scope_id), "video_id": identity})
        for row in existing:
            if row["video_id"] not in desired:
                db.delete("knowledge_videos", row["id"])
    return {"video_ids": desired}
