from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from backend import auth, db
from backend.models import Category, CategoryInput
from backend import settings

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[Category])
def list_categories(request: Request, include_drafts: bool = False, offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    if include_drafts:
        auth.require_draft_access(request)
    rows = db.all_rows("guide_categories", **({} if include_drafts else {"published": True}))
    return sorted(rows, key=lambda row: (row["display_order"], row["name"], row["id"]))[offset:offset + limit]


@router.post("", response_model=Category, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_category(request: CategoryInput):
    return db.insert("guide_categories", request.model_dump())


@router.patch("/{category_id}", response_model=Category, dependencies=[Depends(auth.require_admin)])
def edit_category(category_id: UUID, request: CategoryInput):
    return db.update("guide_categories", category_id, request.model_dump())


@router.delete("/{category_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_category(category_id: UUID):
    # The database FK rejects deletion while a guide references this category.
    db.delete("guide_categories", category_id)
