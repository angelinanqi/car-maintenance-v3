"""Shared personal task views and read-only maintenance evidence for chat."""
from datetime import date
from uuid import NAMESPACE_URL, uuid5

from backend import db, settings
from shared.models import PersonalMaintenanceContext
from backend.services.maintenance import status


def task_view(row, schedules, items):
    item = items.get(row.get('item_id'))
    schedule = schedules.get(row['vehicle_id'], {})
    entry = next((e for e in schedule.get('entries', [])
                  if e['itemId'] == row.get('item_id')), None) if item else None
    return {'id': row['id'], 'vehicleId': row['vehicle_id'], 'title': item['title'] if item else row['title'],
            'category': item['category'] if item else row['category'], 'itemId': row.get('item_id'),
            'action': item['action'] if item else row['action'], 'isCustom': item is None,
            'scheduleSource': row['schedule_source'], 'customRule': row.get('custom_rule'),
            'manufacturerRule': entry['rule'] if entry else None, 'lessonIds': item.get('lessonIds', []) if item else [],
            'manufacturerRevision': schedule.get('revision')}


def record_view(row):
    return {'id': row['id'], 'vehicleId': row['vehicle_id'], 'taskId': row.get('task_id'),
            'title': row['title'], 'category': row['category'], 'mileage': row['mileage'],
            'date': row['performed_at'], 'notes': row['notes'], 'cost': row.get('cost'),
            'workshopName': row.get('workshop_name', ''), 'performedBy': row.get('performed_by')}


def personal_schedules(vehicles):
    published = {s['vehicle_id']: s for s in db.all_rows('manufacturer_schedules', status='published')}
    return {v['id']: published[v['catalogue_id']] for v in vehicles if v['catalogue_id'] in published}


def load_tasks(owner, vehicles, items, *, persist_missing=False):
    schedules = personal_schedules(vehicles)
    tasks = []
    for vehicle in vehicles:
        current = db.all_rows('user_tasks', user_id=owner, vehicle_id=vehicle['id'])
        for entry in schedules.get(vehicle['id'], {}).get('entries', []):
            if any(t.get('item_id') == entry['itemId'] for t in current):
                continue
            item = items[entry['itemId']]
            row = {'id': 'm:' + str(uuid5(NAMESPACE_URL, f"{owner}/{vehicle['id']}/{item['id']}")),
                   'user_id': owner, 'vehicle_id': vehicle['id'], 'item_id': item['id'],
                   'title': None, 'category': None, 'action': None,
                   'schedule_source': 'manufacturer', 'custom_rule': None}
            if persist_missing:
                row = db.client().table('user_tasks').upsert(row, on_conflict='user_id,id').execute().data[0]
            current.append(row)
        tasks.extend(task_view(row, schedules, items) for row in current)
    return tasks


def load(user, profile):
    """Never trust client vehicle IDs, infer history, or write tasks during chat."""
    if profile is None:
        return None
    owner, vehicle_id = user['id'], profile['vehicle_id']
    # Query both ownership and vehicle; record IDs are only unique per account.
    vehicles = db.all_rows('user_vehicles', user_id=owner, id=vehicle_id)
    if not vehicles or vehicles[0]['catalogue_id'] != profile['catalogue_id']:
        from fastapi import HTTPException
        raise HTTPException(409, 'The active vehicle changed. Please retry your question.')
    vehicle = vehicles[0]
    items = {item['id']: item for item in db.all_rows('maintenance_items')}
    tasks = load_tasks(owner, vehicles, items)
    records = sorted(db.all_rows('service_records', user_id=owner, vehicle_id=vehicle_id),
                     key=lambda r: (r['performed_at'], r['mileage'], r['id']), reverse=True)
    today = date.today()
    views = [record_view(record) for record in records]

    def saved(record):
        # Notes, costs, receipts and unrelated personal data never reach the model.
        return {'title': record['title'], 'date': record['performed_at'], 'mileage_km': record['mileage']}

    summaries = []
    for task in tasks:
        last = next((record for record in records if record.get('task_id') == task['id']), None)
        summaries.append({'task_id': task['id'], 'title': task['title'], 'category': task['category'],
                          'action': task['action'], 'schedule_source': task['scheduleSource'],
                          'status': status(task, views, vehicle['mileage'], today,
                                           due_soon_km=settings.DUE_SOON_KM,
                                           due_soon_days=settings.DUE_SOON_DAYS),
                          'latest_service': saved(last) if last else None})
    priority = {'Due / Overdue': 0, 'Due soon': 1, 'Information required': 2, 'Upcoming': 3}
    summaries.sort(key=lambda task: (priority.get(task['status']['label'], 4), task['title'], task['task_id']))
    # Preserve standalone history without guessing which maintenance task it belongs to.
    task_ids = {task['id'] for task in tasks}
    standalone = {}
    for record in records:
        if record.get('task_id') not in task_ids:
            standalone.setdefault(record['title'].strip().casefold(), saved(record))
    return PersonalMaintenanceContext(
        vehicle_id=vehicle_id, catalogue_id=vehicle['catalogue_id'], as_of=today,
        total_tasks=len(summaries), tasks=summaries[:50],
        total_standalone_services=len(standalone), standalone_services=list(standalone.values())[:50],
    ).model_dump(mode='json')
