from fastapi import APIRouter, Query

from backend import db
from backend.models import Manual, Vehicle
from backend import settings
from backend.services import manuals

router = APIRouter(prefix="/manuals", tags=["Manuals"])


@router.get("", response_model=list[Manual])
def list_manuals(car_model: Vehicle = "general", offset: int = Query(0, ge=0),
                 limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    # The mobile client already stores the stable catalogue code. It is a lookup
    # parameter, not a second document-to-vehicle relationship.
    vehicles = db.all_rows("knowledge_vehicles", code=car_model) if car_model != "general" else []
    vehicle_id = vehicles[0]['id'] if vehicles else None
    associations = db.all_rows("document_vehicles", vehicle_id=vehicle_id) if vehicle_id else []
    rows = [row for row in manuals.published_manuals() if manuals.applicable(row, vehicle_id, associations)]
    return rows[offset:offset + limit]
