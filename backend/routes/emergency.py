from uuid import UUID, uuid5, NAMESPACE_URL
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import AwareDatetime
from postgrest.exceptions import APIError
from backend import auth, db
from backend.models import Playbook, PlaybookInput, Contact, ContactInput, ReviewConfirmation
from backend.locks import content_lock
from backend import settings

router = APIRouter(prefix="/emergency", tags=["Emergency"])


class PlaybookCreate(PlaybookInput):
    id: UUID


class PlaybookUpdate(PlaybookInput):
    expected_updated_at: AwareDatetime


class PlaybookReview(ReviewConfirmation):
    expected_updated_at: AwareDatetime


class ContactCreate(ContactInput):
    id: UUID


class ContactUpdate(ContactInput):
    expected_updated_at: AwareDatetime


def create_once(table, values):
    try:
        return db.insert(table, values)
    except APIError as error:
        if error.code != "23505":
            raise
        try:
            existing = db.get(table, values["id"])
        except HTTPException as missing:
            if missing.status_code != 404:
                raise
            raise error
        if any(existing.get(key) != value for key, value in values.items()):
            raise HTTPException(409, "This create request was already saved with different content. Reload the directory before continuing.") from None
        return existing


def revision_conflict(table, record_id):
    db.get(table, record_id)  # Distinguish a missing record from a stale edit.
    raise HTTPException(409, "This record changed. Your edits are kept. Reload and review the latest record before saving again.")


def update_revision(table, record_id, expected, values):
    # The timestamp predicate and update run in one database statement, across workers.
    rows = db.client().table(table).update({**values, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", str(record_id)).eq("updated_at", expected.isoformat()).execute().data
    if not rows:
        revision_conflict(table, record_id)
    return rows[0]


def delete_revision(table, record_id, expected):
    rows = db.client().table(table).delete().eq("id", str(record_id)).eq("updated_at", expected.isoformat()).execute().data
    if not rows:
        try:
            revision_conflict(table, record_id)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            # Retrying a confirmed or uncertain deletion is safe.


def mobile_playbook(row):
    # The Pass 1 offline reader understands ordered steps. Keep new safety metadata visible there.
    introductory_steps = []
    for field, title in (("description", "Situation"), ("safety_warnings", "Safety warnings")):
        if row.get(field):
            introductory_steps.append({"id": str(uuid5(NAMESPACE_URL, f"{row['id']}:{field}")),
                "title": title, "description": row[field], "imageUrl": ""})
    steps = [{**step, 'media': [item for item in step.get('media', [])
              if item.get('kind') != 'video' or item.get('asset_id')]} for step in row['steps']]
    return {**row, "steps": introductory_steps + steps}


@router.get("/playbooks", response_model=list[Playbook])
def list_playbooks(request: Request, include_drafts: bool = False, offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    if include_drafts:
        auth.require_draft_access(request)
    rows = db.list_rows("emergency_playbooks", offset=offset, limit=limit, order_by=("display_order", "created_at", "id"), **({} if include_drafts else {"status": "published"}))
    return rows if include_drafts else [mobile_playbook(row) for row in rows]


@router.post("/playbooks", response_model=Playbook, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_playbook(request: PlaybookCreate):
    values = request.model_dump(mode='json', exclude={'status'})
    if any(step.get('media') or step.get('imageUrl') for step in values['steps']):
        from backend.services.emergency_media import validate_steps
        validate_steps(request.id, values['steps'])
    return create_once("emergency_playbooks", {**values, "status": "draft", "reviewed_at": None})


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
def edit_playbook(playbook_id: UUID, request: PlaybookUpdate):
    with content_lock("playbook:" + str(playbook_id)):
        old = db.get("emergency_playbooks", playbook_id)
        values = request.model_dump(mode="json", exclude={"status", "expected_updated_at"})
        from backend.services.emergency_media import validate_steps
        validate_steps(playbook_id, values['steps'])
        if request.status == "draft" or any(old.get(key) != value for key, value in values.items()):
            values.update(status="draft", reviewed_at=None)
        return update_revision("emergency_playbooks", playbook_id, request.expected_updated_at, values)


@router.post("/playbooks/{playbook_id}/publish", response_model=Playbook, dependencies=[Depends(auth.require_admin)])
def publish_playbook(playbook_id: UUID, request: PlaybookReview):
    with content_lock("playbook:" + str(playbook_id)):
        row = db.get("emergency_playbooks", playbook_id)
        values = PlaybookInput(**{key: row[key] for key in ("title", "steps", "source", "scenario_key")})
        if not values.steps or not values.source or not values.scenario_key:
            raise HTTPException(422, "Add steps, a source reference, and a scenario key before publishing.")
        if any(not media.reviewed for step in values.steps for media in step.media):
            raise HTTPException(422, 'Review each media description before publishing emergency steps.')
        from backend.services.emergency_media import validate_steps
        validate_steps(playbook_id, row['steps'])
        return update_revision("emergency_playbooks", playbook_id, request.expected_updated_at, {"status": "published", "reviewed_at": datetime.now(timezone.utc).isoformat()})


@router.delete("/playbooks/{playbook_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_playbook(playbook_id: UUID, expected_updated_at: AwareDatetime):
    with content_lock("playbook:" + str(playbook_id)):
        images = db.all_rows('emergency_images', playbook_id=str(playbook_id))
        assets = db.all_rows('emergency_media_assets', playbook_id=str(playbook_id))
        indexes = db.all_rows('emergency_indexes', id=str(playbook_id))
        delete_revision("emergency_playbooks", playbook_id, expected_updated_at)
        if images or assets:
            try:
                db.bucket(settings.SUPABASE_CONTENT_BUCKET).remove([image['storage_path'] for image in [*images, *assets]])
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Playbook deleted; emergency image cleanup failed')
        if indexes and indexes[0].get('extraction_storage_path'):
            db.bucket(settings.SUPABASE_DOCUMENT_BUCKET).remove([indexes[0]['extraction_storage_path']])


@router.post('/playbooks/{playbook_id}/media', status_code=201, dependencies=[Depends(auth.require_admin)])
def upload_playbook_media(playbook_id: UUID, step_id: UUID = Form(...),
                          description: str = Form(default='', max_length=4000), file: UploadFile = File(...)):
    with content_lock('playbook:' + str(playbook_id)):
        row = db.get('emergency_playbooks', playbook_id)
        if not any(step['id'] == str(step_id) for step in row['steps']):
            raise HTTPException(422, 'Save this step before uploading its media.')
        from backend.services.emergency_media import upload
        return upload(playbook_id, step_id, file, description)


@router.post('/playbooks/{playbook_id}/images', status_code=201, dependencies=[Depends(auth.require_admin)])
def upload_playbook_image(playbook_id: UUID, file: UploadFile = File(...)):
    with content_lock('playbook:' + str(playbook_id)):
        db.get('emergency_playbooks', playbook_id)
        from backend.services.content_uploads import upload_image
        return upload_image(playbook_id, file, emergency=True)


@router.get("/contacts", response_model=list[Contact])
def list_contacts(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("emergency_contacts", offset=offset, limit=limit, order_by=("display_order", "created_at", "id"))


@router.post("/contacts", response_model=Contact, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_contact(request: ContactCreate):
    return create_once("emergency_contacts", request.model_dump(mode="json"))


@router.patch("/contacts/{contact_id}", response_model=Contact, dependencies=[Depends(auth.require_admin)])
def edit_contact(contact_id: UUID, request: ContactUpdate):
    return update_revision("emergency_contacts", contact_id, request.expected_updated_at, request.model_dump(mode="json", exclude={"expected_updated_at"}))


@router.delete("/contacts/{contact_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_contact(contact_id: UUID, expected_updated_at: AwareDatetime):
    delete_revision("emergency_contacts", contact_id, expected_updated_at)
