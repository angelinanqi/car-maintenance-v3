from fastapi import APIRouter, Query

from backend import db
from backend.models import Manual, Vehicle
from backend import settings

router = APIRouter(prefix="/manuals", tags=["Manuals"])


@router.get("", response_model=list[Manual])
def list_manuals(car_model: Vehicle = "general", offset: int = Query(0, ge=0),
                 limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    scopes = ["general"] if car_model == "general" else [car_model, "general"]
    return db.list_rows("documents", offset=offset, limit=limit,
                        mobile_visible=True, published=True, status="processed", car_model=scopes)
