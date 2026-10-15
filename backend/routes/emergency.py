from uuid import UUID, uuid5, NAMESPACE_URL
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from backend import auth, db
from backend.models import Playbook, PlaybookInput, Contact, ContactInput, ReviewConfirmation
from backend.locks import content_lock
from backend import settings

router = APIRouter(prefix="/emergency", tags=["Emergency"])


def mobile_playbook(row):
    # The Pass 1 offline reader understands ordered steps. Keep new safety metadata visible there.
    introductory_steps = []
    for field, title in (("description", "Situation"), ("safety_warnings", "Safety warnings")):
        if row.get(field):
            introductory_steps.append({"id": str(uuid5(NAMESPACE_URL, f"{row['id']}:{field}")),
                "title": title, "description": row[field], "imageUrl": ""})
    return {**row, "steps": introductory_steps + row["steps"]}


@router.get("/playbooks", response_model=list[Playbook])
def list_playbooks(request: Request, include_drafts: bool = False, offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    if include_drafts:
        auth.require_draft_access(request)
    rows = db.list_rows("emergency_playbooks", offset=offset, limit=limit, **({} if include_drafts else {"status": "published"}))
    return rows if include_drafts else [mobile_playbook(row) for row in rows]


@router.post("/playbooks", response_model=Playbook, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_playbook(request: PlaybookInput):
    return db.insert("emergency_playbooks", {**request.model_dump(mode="json", exclude={"status"}), "status": "draft", "reviewed_at": None})


@router.get("/playbooks/{playbook_id}", response_model=Playbook)
def get_playbook(playbook_id: UUID, request: Request):
    row = db.get("emergency_playbooks", playbook_id)
    if row["status"] != "published":
        try:
            auth.require_draft_access(request)
        except HTTPException as error:
            if error.status_code in {401, 403}:
                raise HTTPException(404, "Record not found.") from None
            raise
    return mobile_playbook(row)


@router.patch("/playbooks/{playbook_id}", response_model=Playbook, dependencies=[Depends(auth.require_admin)])
def edit_playbook(playbook_id: UUID, request: PlaybookInput):
    with content_lock("playbook:" + str(playbook_id)):
        old = db.get("emergency_playbooks", playbook_id)
        values = request.model_dump(mode="json", exclude={"status"})
        if request.status == "draft" or any(old.get(key) != value for key, value in values.items()):
            values.update(status="draft", reviewed_at=None)
        return db.update("emergency_playbooks", playbook_id, values)


@router.post("/playbooks/{playbook_id}/publish", response_model=Playbook, dependencies=[Depends(auth.require_admin)])
def publish_playbook(playbook_id: UUID, request: ReviewConfirmation):
    with content_lock("playbook:" + str(playbook_id)):
        row = db.get("emergency_playbooks", playbook_id)
        values = PlaybookInput(**{key: row[key] for key in ("title", "steps", "source", "scenario_key")})
        if not values.steps or not values.source or not values.scenario_key:
            raise HTTPException(422, "Add steps, a source reference, and a scenario key before publishing.")
        return db.update("emergency_playbooks", playbook_id, {"status": "published", "reviewed_at": datetime.now(timezone.utc).isoformat()})


@router.delete("/playbooks/{playbook_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_playbook(playbook_id: UUID):
    with content_lock("playbook:" + str(playbook_id)):
        db.delete("emergency_playbooks", playbook_id)


@router.get("/contacts", response_model=list[Contact])
def list_contacts(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("emergency_contacts", offset=offset, limit=limit)


@router.post("/contacts", response_model=Contact, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_contact(request: ContactInput):
    return db.insert("emergency_contacts", request.model_dump())


@router.patch("/contacts/{contact_id}", response_model=Contact, dependencies=[Depends(auth.require_admin)])
def edit_contact(contact_id: UUID, request: ContactInput):
    return db.update("emergency_contacts", contact_id, request.model_dump())


@router.delete("/contacts/{contact_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_contact(contact_id: UUID):
    db.delete("emergency_contacts", contact_id)
