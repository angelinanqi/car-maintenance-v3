"""Account-owned mobile persistence."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field, field_validator, model_validator

from backend import auth, db, settings
from backend.locks import content_lock
from shared.models import InputModel
from backend.models import Rule
from backend.services.personal_records import valid_id, owned, put
from backend.services.catalogue import catalogue, item_lessons
from backend.services.maintenance import as_date, status
from backend.services.personal_maintenance import load_tasks, personal_schedules, record_view


router = APIRouter(prefix='/mobile/me', tags=['Mobile personal data'])


class VehicleInput(InputModel):
    catalogueId: UUID
    name: str = Field(default='', max_length=200)
    plateNumber: str = Field(default='', max_length=40)
    mileage: int = Field(ge=0, le=2147483647)


class ActiveVehicleInput(InputModel):
    id: str = Field(min_length=1, max_length=200)


class TaskInput(InputModel):
    id: str
    vehicleId: str
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(default='', max_length=200)
    itemId: UUID | None = None
    action: Literal['inspect', 'replace', 'service'] = 'service'
    manufacturerRule: Rule | None = None
    customRule: Rule | None = None
    scheduleSource: Literal['none', 'custom', 'manufacturer'] = 'none'
    lessonIds: list[UUID] = Field(default_factory=list)
    isCustom: bool = True

    @field_validator('id', 'vehicleId')
    @classmethod
    def valid_identifiers(cls, value):
        return valid_id(value)

    @model_validator(mode='after')
    def check_custom(self):
        if self.customRule:
            if self.customRule.type != 'recurring' or not (self.customRule.distanceKm or self.customRule.months):
                raise ValueError('Custom reminders require a recurring distance or time interval')
            if self.customRule.sourceDocumentId or self.customRule.sourcePage:
                raise ValueError('Custom reminders cannot claim manufacturer source references')
        if self.scheduleSource == 'custom' and not self.customRule:
            raise ValueError('Provide a custom rule before selecting it')
        return self


class RecordInput(InputModel):
    id: str
    vehicleId: str
    taskId: str | None = None
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(default='', max_length=200)
    mileage: int = Field(ge=0, le=2147483647)
    date: datetime
    notes: str = Field(default='', max_length=10000)
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator('id', 'vehicleId', 'taskId')
    @classmethod
    def valid_identifiers(cls, value):
        return valid_id(value) if value is not None else None


class ProgressInput(InputModel):
    completed: bool


class IncidentInput(InputModel):
    version: Literal[1] = 1
    id: str
    type: str = Field(min_length=1, max_length=100)
    location: str = Field(default='', max_length=2000)
    occurredAt: datetime
    name: str = Field(default='', max_length=200)
    plate: str = Field(default='', max_length=40)
    phone: str = Field(default='', max_length=100)
    insurer: str = Field(default='', max_length=200)
    details: str = Field(default='', max_length=20000)
    photos: list[str] = Field(default_factory=list, max_length=0)
    photoCount: int = Field(default=0, ge=0, le=6)
    updatedAt: datetime
    pendingSync: bool = True
    cloudRevision: int | None = Field(default=None, ge=1)

    @field_validator('id')
    @classmethod
    def valid_identifier(cls, value):
        return valid_id(value)


@router.get('')
def snapshot(user=Depends(auth.require_user)):
    owner = user['id']
    with content_lock('mobile:' + owner):
        vehicles = db.all_rows('user_vehicles', user_id=owner)
        active_id = db.get('app_users', owner).get('active_vehicle_id')
        if vehicles and not any(v['id'] == active_id for v in vehicles):
            active_id = vehicles[0]['id']
            db.update('app_users', owner, {'active_vehicle_id': active_id})
        data = catalogue()
        identities = {v['id']: v for v in data['vehicles']}
        models = {m['id']: m for m in data['models']}
        makers = {m['id']: m for m in data['manufacturers']}
        links = item_lessons()
        # Retain disabled items referenced by existing history/tasks.
        items = {i['id']: {**i, 'lessonIds': links.get(i['id'], [])} for i in db.all_rows('maintenance_items')}
        visible_tasks = load_tasks(owner, vehicles, items, persist_missing=True)
        records = [record_view(r) for r in db.all_rows('service_records', user_id=owner)]
        output = []
        for vehicle in vehicles:
            identity = identities[vehicle['catalogue_id']]
            model = models.get(identity.get('model_id'), {})
            maker = makers.get(model.get('manufacturer_id'), {})
            output.append({'id': vehicle['id'], 'name': vehicle['name'] or identity['name'],
                'model': ' '.join(v for v in [maker.get('name'), model.get('name'), identity['variant']] if v) or identity['name'],
                'year': int(identity['year']) if identity['year'].isdigit() else 0, 'engineSize': identity['engine'],
                'plateNumber': vehicle['plate_number'], 'mileage': vehicle['mileage'], 'carModel': identity['code'],
                'catalogueId': identity['id'], 'knowledgeScopeId': identity['id'],
                'manualAvailable': identity['manual_available'], 'manufacturerScheduleAvailable': identity['manufacturer_schedule_available']})
        mileage = {v['id']: v['mileage'] for v in vehicles}
        for task in visible_tasks:
            task['status'] = status(task, records, mileage[task['vehicleId']],
                                   due_soon_km=settings.DUE_SOON_KM, due_soon_days=settings.DUE_SOON_DAYS)
        return {'vehicles': output, 'tasks': visible_tasks, 'records': records,
                'completedLessons': [r['id'] for r in db.all_rows('learning_progress', user_id=owner, completed=True)],
                'activeVehicleId': active_id,
                'dueSoonKm': settings.DUE_SOON_KM, 'dueSoonDays': settings.DUE_SOON_DAYS}


@router.put('/active-vehicle')
def set_active(request: ActiveVehicleInput, user=Depends(auth.require_user)):
    with content_lock('mobile:' + user['id']):
        owned('user_vehicles', user['id'], request.id)
        db.update('app_users', user['id'], {'active_vehicle_id': request.id})
    return {'id': request.id}


@router.put('/vehicles/{record_id}')
def save_vehicle(record_id: str, request: VehicleInput, user=Depends(auth.require_user)):
    with content_lock('mobile:' + user['id']):
        old = owned('user_vehicles', user['id'], record_id, optional=True)
        if old and old['catalogue_id'] != str(request.catalogueId):
            raise HTTPException(409, 'Register a new vehicle to change its catalogue identity. History must stay with its vehicle.')
        if not old:
            identity = db.get('knowledge_vehicles', request.catalogueId)
            model = db.get('vehicle_models', identity['model_id']) if identity.get('model_id') else None
            maker = db.get('vehicle_manufacturers', model['manufacturer_id']) if model else None
            if (not identity['active'] or not identity['year'].isdigit() or not model or not model['active']
                    or not maker['active'] or identity['powertrain'] not in {'petrol', 'diesel'}):
                raise HTTPException(422, 'Select an active ICE vehicle from the catalogue.')
        result = put('user_vehicles', user['id'], record_id, {'catalogue_id': str(request.catalogueId),
                     'name': request.name, 'plate_number': request.plateNumber, 'mileage': request.mileage})
        if not db.get('app_users', user['id']).get('active_vehicle_id'):
            db.update('app_users', user['id'], {'active_vehicle_id': record_id})
        return {'id': result['id']}


@router.delete('/vehicles/{record_id}', status_code=204)
def remove_vehicle(record_id: str, user=Depends(auth.require_user)):
    with content_lock('mobile:' + user['id']):
        owned('user_vehicles', user['id'], record_id)
        db.client().table('user_vehicles').delete().eq('user_id', user['id']).eq('id', record_id).execute()
    return Response(status_code=204)


@router.put('/tasks/{record_id}')
def save_task(record_id: str, request: TaskInput, user=Depends(auth.require_user)):
    if request.id != record_id:
        raise HTTPException(422, 'The request and path identifiers must match.')
    with content_lock('mobile:' + user['id']):
        vehicle = owned('user_vehicles', user['id'], request.vehicleId)
        old = owned('user_tasks', user['id'], record_id, optional=True)
        item_id = str(request.itemId) if request.itemId else None
        if old and (old['vehicle_id'] != request.vehicleId or old.get('item_id') != item_id
                    or (not item_id and old['action'] != request.action)):
            raise HTTPException(409, 'Create a separate item to change its vehicle, catalogue identity or action.')
        item = db.get('maintenance_items', item_id) if item_id else None
        if item and (not old and not item['active'] or item['action'] != request.action):
            raise HTTPException(422, 'Choose an active item with the correct action.')
        if request.scheduleSource == 'manufacturer':
            entries = personal_schedules([vehicle]).get(vehicle['id'], {}).get('entries', [])
            if not item or not any(e['itemId'] == item_id for e in entries):
                raise HTTPException(422, 'No published manufacturer rule exists for this item and vehicle.')
        row = put('user_tasks', user['id'], record_id, {'vehicle_id': request.vehicleId, 'item_id': item_id,
            'title': None if item else request.title, 'category': None if item else request.category,
            'action': None if item else request.action, 'schedule_source': request.scheduleSource,
            'custom_rule': request.customRule.model_dump(mode='json') if request.customRule else None})
        return {'id': row['id']}


@router.delete('/tasks/{record_id}', status_code=204)
def remove_task(record_id: str, user=Depends(auth.require_user)):
    with content_lock('mobile:' + user['id']):
        task = owned('user_tasks', user['id'], record_id)
        vehicle = owned('user_vehicles', user['id'], task['vehicle_id'])
        if any(e['itemId'] == task.get('item_id') for e in personal_schedules([vehicle]).get(vehicle['id'], {}).get('entries', [])):
            raise HTTPException(409, 'This item is in the manufacturer schedule. Select No schedule to stop its reminders while keeping history.')
        db.client().table('user_tasks').delete().eq('user_id', user['id']).eq('id', record_id).execute()
    return Response(status_code=204)


@router.put('/records/{record_id}')
def save_record(record_id: str, request: RecordInput, user=Depends(auth.require_user)):
    if request.id != record_id or as_date(request.date.isoformat()) > datetime.now().date():
        raise HTTPException(422, 'Use matching identifiers and a service date that is not in the future.')
    with content_lock('mobile:' + user['id']):
        owned('user_vehicles', user['id'], request.vehicleId)
        old = owned('service_records', user['id'], record_id, optional=True)
        if old and (old['vehicle_id'] != request.vehicleId or old.get('task_id') != request.taskId):
            raise HTTPException(409, 'A service record cannot be moved to another vehicle or item.')
        task = owned('user_tasks', user['id'], request.taskId) if request.taskId else None
        if (task and task['vehicle_id'] != request.vehicleId) or (not task and not old):
            raise HTTPException(422, 'Select an item belonging to this vehicle.')
        if old:
            title = old['title']
        elif task.get('item_id'):
            title = db.get('maintenance_items', task['item_id'])['title']
        else:
            title = task['title']
        row = put('service_records', user['id'], record_id, {'vehicle_id': request.vehicleId, 'task_id': request.taskId,
            'title': title, 'category': request.category,
            'mileage': request.mileage, 'performed_at': request.date.date().isoformat(), 'notes': request.notes, 'cost': request.cost})
        return record_view(row)


@router.put('/progress/{guide_id}')
def save_progress(guide_id: UUID, request: ProgressInput, user=Depends(auth.require_user)):
    guide = db.get('guides', guide_id)
    if guide['status'] != 'published' or (guide['category_id'] and not db.get('guide_categories', guide['category_id'])['published']):
        raise HTTPException(404, 'Published lesson not found.')
    put('learning_progress', user['id'], str(guide_id), {'completed': request.completed})
    return {'completed': request.completed}


@router.get('/incidents')
def incidents(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000), user=Depends(auth.require_user)):
    return [{**r['payload'], 'id': r['id'], 'cloudRevision': r['revision'], 'pendingSync': False}
            for r in db.list_rows('incident_records', user_id=user['id'], offset=offset, limit=limit)]


@router.put('/incidents/{record_id}')
def save_incident(record_id: str, request: IncidentInput, user=Depends(auth.require_user)):
    if request.id != record_id:
        raise HTTPException(422, 'The request and path identifiers must match.')
    with content_lock('mobile:' + user['id']):
        old = owned('incident_records', user['id'], record_id, optional=True)
        values = request.model_dump(mode='json', exclude={'id', 'cloudRevision', 'pendingSync'})
        if old and values == old['payload']:
            return {**old['payload'], 'id': old['id'], 'cloudRevision': old['revision'], 'pendingSync': False}
        if old and request.cloudRevision != old['revision']:
            raise HTTPException(409, 'This incident changed on another device. Your local copy is kept; review the cloud copy before replacing it.')
        row = put('incident_records', user['id'], record_id, {'payload': values, 'revision': old['revision'] + 1 if old else 1})
        return {**row['payload'], 'id': row['id'], 'cloudRevision': row['revision'], 'pendingSync': False}
