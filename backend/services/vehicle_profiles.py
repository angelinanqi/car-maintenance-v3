"""Load the active personal vehicle from Supabase for each chat turn."""
from backend import db
from backend.models import PersonalVehicleProfile


def active_vehicle(user):
    if user.get('role') == 'admin':
        return None
    from backend.routes.mobile import owned
    current = db.get('app_users', user['id']).get('active_vehicle_id')
    return owned('user_vehicles', user['id'], current) if current else None


def load(user):
    vehicle = active_vehicle(user)
    if vehicle is None:
        return None
    catalogue = db.get('knowledge_vehicles', vehicle['catalogue_id'])
    model = db.get('vehicle_models', catalogue['model_id']) if catalogue.get('model_id') else None
    manufacturer = db.get('vehicle_manufacturers', model['manufacturer_id']) if model else None
    # Explicit fields keep account credentials and unrelated personal records out
    # of the AI request. Missing catalogue details remain unknown, not invented.
    profile = PersonalVehicleProfile(
        vehicle_id=vehicle['id'], catalogue_id=vehicle['catalogue_id'],
        name=vehicle['name'] or catalogue['name'], plate_number=vehicle['plate_number'],
        mileage_km=vehicle['mileage'], catalogue_name=catalogue['name'],
        manufacturer=manufacturer['name'] if manufacturer else None,
        model=model['name'] if model else None,
        year=catalogue['year'], engine=catalogue['engine'], variant=catalogue['variant'],
        powertrain=catalogue['powertrain'], updated_at=vehicle['updated_at'],
    )
    return profile.model_dump(mode='json')
