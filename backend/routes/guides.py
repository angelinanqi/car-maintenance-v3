from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4
import logging

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from backend import auth, db
from backend.locks import content_lock
from backend.models import Guide, GuideInput, GuidePatch, GuideImage
from backend import settings

router = APIRouter(prefix="/guides", tags=["Guides"])
logger = logging.getLogger(__name__)


def validate_guide(values, guide_id=None):
    from backend.services.learning_companion import validate_exploration
    # Re-validate merged patches, including nullable optional fields.
    try:
        values = GuideInput.model_validate(values).model_dump(mode='json')
    except ValidationError:
        raise HTTPException(422, 'Guide fields do not match the required format.') from None
    validate_exploration(values)
    if guide_id and str(guide_id) in values.get("related_lesson_ids", []):
        raise HTTPException(422, "A guide cannot link to itself as a related lesson.")
    if values["category_id"]:
        category = db.get("guide_categories", values["category_id"])
        if category.get("archived") and (not guide_id or db.get("guides", guide_id)["category_id"] != values["category_id"]):
            raise HTTPException(422, "Restore this archived category before assigning a guide to it.")
        if values["status"] == "published" and not category.get("published", True):
            raise HTTPException(422, "Publish the learning category before publishing this guide.")
    for guide_id in values.get("related_lesson_ids", []):
        db.get("guides", guide_id)
    for item_id in values.get("maintenance_item_ids", []):
        db.get("maintenance_items", item_id)
    soup = BeautifulSoup(values["content"], "html.parser")
    bodies = [soup, *[BeautifulSoup(step['example_html'], 'html.parser') for step in (values.get('exploration') or {}).get('steps', [])]]
    for body in bodies:
        for media in body.find_all(["img", "iframe"]):
            source = media.get("src", "")
            if not source.startswith(("https://", "http://")):
                raise HTTPException(422, "Images and videos must use durable http(s) URLs.")
    if values["status"] == "published" and not (soup.get_text(strip=True) or soup.find(["img", "iframe"])):
        raise HTTPException(422, "Add content before publishing this guide.")
    # The editor renders using TipTap's schema; raw HTML is never injected into the UI.
    return values


@router.get("", response_model=list[Guide])
def list_guides(request: Request, include_drafts: bool = False, offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    if include_drafts:
        auth.require_draft_access(request)
    if include_drafts:
        return db.list_rows("guides", offset=offset, limit=limit, order_by=("display_order", "created_at", "id"))
    categories = {r["id"] for r in db.all_rows("guide_categories", published=True)}
    rows = db.all_rows("guides", status="published", order_by=("display_order", "created_at", "id"))
    return [row for row in rows if not row["category_id"] or row["category_id"] in categories][offset:offset + limit]


@router.post("", response_model=Guide, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_guide(request: GuideInput):
    with content_lock("guide-links"):
        values = validate_guide(request.model_dump(mode="json"))
        if values["status"] == "published":
            values["published_at"] = datetime.now(timezone.utc).isoformat()
        return db.insert("guides", values)


@router.get("/{guide_id}", response_model=Guide)
def get_guide(guide_id: UUID, request: Request):
    row = db.get("guides", guide_id)
    category_hidden = row["category_id"] and not db.get("guide_categories", row["category_id"]).get("published", True)
    if row["status"] != "published" or category_hidden:
        try:
            auth.require_draft_access(request)
        except HTTPException as error:
            if error.status_code in {401, 403}:
                raise HTTPException(404, "Record not found.") from None
            raise
    return row


@router.patch("/{guide_id}", response_model=Guide, dependencies=[Depends(auth.require_admin)])
def edit_guide(guide_id: UUID, request: GuidePatch):
    with content_lock("guide-links"), content_lock("guide:" + str(guide_id)):
        old = db.get("guides", guide_id)
        values = GuideInput(**{key: old[key] for key in GuideInput.model_fields if key in old}).model_dump(mode="json")
        values.update(request.model_dump(mode="json", exclude_unset=True))
        values = validate_guide(values, guide_id)
        values["published_at"] = (
            old["published_at"] or datetime.now(timezone.utc).isoformat()
            if values["status"] == "published" else None
        )
        return db.update("guides", guide_id, values)


@router.post("/{guide_id}/publish", response_model=Guide, dependencies=[Depends(auth.require_admin)])
def publish_guide(guide_id: UUID):
    return edit_guide(guide_id, GuidePatch(status="published"))


@router.delete("/{guide_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_guide(guide_id: UUID):
    with content_lock("guide-links"), content_lock("guide:" + str(guide_id)):
        db.get("guides", guide_id)
        if any(str(guide_id) in row.get("related_lesson_ids", []) for row in db.all_rows("guides")):
            raise HTTPException(409, "Remove related-lesson links before deleting this guide.")
        images = db.all_rows("guide_images", guide_id=str(guide_id))
        if images:
            db.bucket(settings.SUPABASE_CONTENT_BUCKET).remove([image["storage_path"] for image in images])
        db.delete("guides", guide_id)


@router.post("/{guide_id}/images", response_model=GuideImage, status_code=201, dependencies=[Depends(auth.require_admin)])
def upload_image(guide_id: UUID, file: UploadFile = File(...)):
    with content_lock("guide:" + str(guide_id)):
        db.get("guides", guide_id)
        data = file.file.read(settings.IMAGE_MAX_BYTES + 1)
        if len(data) > settings.IMAGE_MAX_BYTES:
            raise HTTPException(413, "Image exceeds the configured upload size limit.")
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
                image_format = image.format
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
            raise HTTPException(422, "Upload a valid PNG, JPEG, WebP, or GIF image.") from None
        formats = {"PNG": ("png", "image/png"), "JPEG": ("jpg", "image/jpeg"), "WEBP": ("webp", "image/webp"), "GIF": ("gif", "image/gif")}
        if image_format not in formats or formats[image_format][1] not in settings.IMAGE_CONTENT_TYPES:
            raise HTTPException(415, "This image format is not enabled.")
        extension, mime = formats[image_format]
        image_id = str(uuid4())
        path = f"guides/{guide_id}/images/{image_id}.{extension}"
        bucket = db.bucket(settings.SUPABASE_CONTENT_BUCKET)
        bucket.upload(path, data, {"content-type": mime, "upsert": "false"})
        url = bucket.get_public_url(path)
        try:
            row = db.insert("guide_images", dict(id=image_id, guide_id=str(guide_id), storage_path=path))
            return {**row, "url": url}
        except Exception:
            try:
                bucket.remove([path])
            except Exception:
                logger.exception("Failed to clean up unrecorded guide image %s", path)
            raise
