"""Archive shared topics or remove them after an administrator reviews their impact."""
from uuid import UUID

from fastapi import HTTPException
from postgrest.exceptions import APIError

from backend import db
from backend.locks import content_lock
from shared.models import InputModel
from pydantic import Field


class CategoryRemovalInput(InputModel):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{32}$")
    target_category_id: UUID | None = None


def rpc(name, values):
    try:
        return db.client().rpc(name, values).execute().data
    except APIError as error:
        if error.code in {"PT404", "PT409", "PT422"}:
            raise HTTPException(int(error.code[2:]), error.message) from None
        if error.code in {"PGRST202", "42703"}:
            raise HTTPException(503, "Category management needs a database update. Apply supabase/migrations/20261103_category_removal.sql before trying again.") from None
        raise


def removal_impact(category_id):
    return rpc("category_removal_impact", {"p_category_id": str(category_id)})


def remove(category_id, request):
    with content_lock("guide-links"), content_lock(category_id):
        rpc("remove_category", {"p_category_id": str(category_id),
            "p_expected_impact": request.fingerprint,
            "p_target_category_id": str(request.target_category_id) if request.target_category_id else None})


def archive(category_id):
    with content_lock("guide-links"), content_lock(category_id):
        db.get("guide_categories", category_id)
        return db.update("guide_categories", category_id,
            {"archived": True, "published": False, "knowledge_published": False})


def restore(category_id):
    with content_lock("guide-links"), content_lock(category_id):
        db.get("guide_categories", category_id)
        # Restoring does not silently republish content or enable chatbot sources.
        return db.update("guide_categories", category_id, {"archived": False})
