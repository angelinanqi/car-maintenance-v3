"""Complete, deterministic service proposals built from authoritative task data."""
from datetime import date
import hashlib
import json

from fastapi import HTTPException
from backend import db, settings
from backend.services.maintenance import status
from backend.services.personal_maintenance import load_tasks, record_view
from backend.services.personal_records import owned
from backend.services.vehicle_profiles import active_vehicle


def calculate(vehicle, tasks, records, *, today=None, source_names=None):
    today = today or date.today()
    source_names = source_names or {}
    latest = {}
    for record in sorted(records, key=lambda row: (row['date'], row['mileage'], row['id']), reverse=True):
        latest.setdefault(record.get('taskId'), record)
    groups = {key: [] for key in ('due', 'discuss', 'check', 'upcoming')}
    for task in sorted(tasks, key=lambda item: (item['title'], item['id'])):
        timing = status(task, records, vehicle['mileage'], today,
                        due_soon_km=settings.DUE_SOON_KM, due_soon_days=settings.DUE_SOON_DAYS)
        label = timing['label']
        if label == 'Due / Overdue':
            group, reason = 'due', 'scheduled_threshold_reached'
        elif label == 'Due soon':
            group, reason = 'discuss', 'within_discussion_window'
        elif label in {'Upcoming', 'Published milestones completed'}:
            group, reason = 'upcoming', 'outside_visit_or_completed_milestones'
        else:
            group, reason = 'check', 'schedule_or_history_needs_review'
        rule = (task.get('manufacturerRule') if task['scheduleSource'] == 'manufacturer' else
                task.get('customRule') if task['scheduleSource'] == 'custom' else None)
        last = latest.get(task['id'])
        groups[group].append({'task_id': task['id'], 'item_id': task.get('itemId'), 'title': task['title'],
                              'action': task['action'], 'schedule_source': task['scheduleSource'], 'status': timing,
                              'reason': reason, 'lesson_ids': task.get('lessonIds', []), 'rule': rule,
                              'latest_service': {'date': last['date'], 'mileage': last['mileage']} if last else None,
                              'source_name': source_names.get(rule.get('sourceDocumentId'))
                              if rule and task['scheduleSource'] == 'manufacturer' else None})
    snapshot = {'rules_version': 2, 'vehicle_id': vehicle['id'], 'mileage': vehicle['mileage'],
                'as_of': today.isoformat(), 'groups': groups, 'total_tasks': len(tasks),
                'discussion_window': {'km': settings.DUE_SOON_KM, 'days': settings.DUE_SOON_DAYS}}
    # Include raw inputs as well as output: same timing may hide a changed source revision.
    evidence = {'snapshot': snapshot, 'tasks': sorted(tasks, key=lambda row: row['id']),
                'records': sorted(records, key=lambda row: row['id'])}
    fingerprint = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()
    return {'fingerprint': fingerprint, 'snapshot': snapshot, 'stale': False}


def preview(user, vehicle_id):
    vehicle = owned('user_vehicles', user['id'], vehicle_id)
    current = active_vehicle(user)
    if not current or current['id'] != vehicle_id:
        raise HTTPException(409, 'Select this vehicle before preparing its service plan.')
    items = {row['id']: row for row in db.all_rows('maintenance_items')}
    from backend.services.catalogue import item_lessons
    links = item_lessons()
    items = {identity: {**item, 'lessonIds': links.get(identity, [])} for identity, item in items.items()}
    tasks = load_tasks(user['id'], [vehicle], items)
    records = [record_view(row) for row in db.all_rows('service_records', user_id=user['id'], vehicle_id=vehicle_id)]
    records.sort(key=lambda row: row['id'])
    source_ids = {task['manufacturerRule'].get('sourceDocumentId') for task in tasks
                  if task['scheduleSource'] == 'manufacturer' and task.get('manufacturerRule')}
    source_ids.discard(None)
    sources = db.all_rows('documents', id=sorted(source_ids)) if source_ids else []
    return calculate(vehicle, tasks, records, source_names={row['id']: row['name'] for row in sources})


def save(user, vehicle_id, fingerprint):
    from backend.locks import content_lock
    with content_lock('mobile:' + user['id']):
        result = preview(user, vehicle_id)
        if result['fingerprint'] != fingerprint:
            raise HTTPException(409, 'Maintenance information changed. Review the refreshed plan before saving.')
        existing = db.all_rows('service_plans', user_id=user['id'], vehicle_id=vehicle_id, fingerprint=fingerprint)
        row = existing[0] if existing else db.insert('service_plans', {
            'user_id': user['id'], 'vehicle_id': vehicle_id, 'fingerprint': fingerprint, 'snapshot': result['snapshot']})
        return {**row, 'stale': False}


def get_plan(user, plan_id):
    row = owned('service_plans', user['id'], plan_id)
    result = preview(user, row['vehicle_id'])
    return {**row, 'stale': row['fingerprint'] != result['fingerprint']}
