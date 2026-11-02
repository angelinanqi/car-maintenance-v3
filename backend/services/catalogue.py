"""Catalogue views shared by the admin and mobile APIs."""
from backend import db
from backend.services import manuals


def catalogue():
    vehicles = db.all_rows("knowledge_vehicles")
    docs = manuals.published_manuals()
    associations = db.all_rows("document_vehicles")
    schedules = db.all_rows("manufacturer_schedules", status="published")
    for vehicle in vehicles:
        vehicle["manual_available"] = any(manuals.applicable(document, vehicle['id'], associations) for document in docs)
        vehicle["manufacturer_schedule_available"] = any(s["vehicle_id"] == vehicle["id"] for s in schedules)
    return {"manufacturers": db.all_rows("vehicle_manufacturers"), "models": db.all_rows("vehicle_models"), "vehicles": vehicles}


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
