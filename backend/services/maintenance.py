"""Authoritative maintenance dates and status from structured data, never AI."""
from calendar import monthrange
from datetime import date, datetime


def as_date(value):
    return date.fromisoformat(str(value)[:10])


def add_months(value, months):
    number = value.year * 12 + value.month - 1 + months
    year, month = divmod(number, 12)
    return date(year, month + 1, min(value.day, monthrange(year, month + 1)[1]))


def status(task, records, odometer, today=None, *, due_soon_km=1000, due_soon_days=30):
    today = today or datetime.now().date()
    rule = task.get('manufacturerRule') if task['scheduleSource'] == 'manufacturer' else (
        task.get('customRule') if task['scheduleSource'] == 'custom' else None)
    result = {'label': 'No schedule', 'nextKm': None, 'remainingKm': None, 'nextDate': None}
    if not rule:
        return result
    if rule['type'] == 'informational' or rule.get('conditions'):
        return {**result, 'label': 'Information required — review schedule conditions'}
    history = sorted((r for r in records if r.get('taskId') == task['id']),
                     key=lambda r: (r['date'], r['mileage'], r['id']), reverse=True)
    last = history[0] if history else None
    km = next_date = None
    missing = False
    if rule['type'] == 'recurring':
        if not last or not (rule.get('distanceKm') or rule.get('months')):
            return {**result, 'label': 'Information required'}
        if rule.get('distanceKm'):
            km = last['mileage'] + rule['distanceKm']
        if rule.get('months'):
            next_date = add_months(as_date(last['date']), rule['months'])
    elif rule['type'] == 'milestone':
        km = next((m for m in rule.get('distanceMilestones', []) if not last or m > last['mileage']), None)
        months = rule.get('monthMilestones', [])
        start = rule.get('vehicleStartDate')
        missing = bool(months and not start)
        if start:
            next_date = next((add_months(as_date(start), m) for m in months
                              if not last or add_months(as_date(start), m) > as_date(last['date'])), None)
        if km is None and next_date is None and not missing:
            return {**result, 'label': 'Published milestones completed'}
    else:
        return {**result, 'label': 'Information required'}
    remaining = km - odometer if km is not None else None
    days = (next_date - today).days if next_date else None
    due = (remaining is not None and remaining <= 0) or (days is not None and days <= 0)
    soon = (remaining is not None and remaining <= due_soon_km) or (days is not None and days <= due_soon_days)
    label = ('Published milestone — confirm service history' if rule['type'] == 'milestone' and not last else
             'Due / Overdue' if due else 'Information required' if missing else 'Due soon' if soon else 'Upcoming')
    return {'label': label, 'nextKm': km, 'remainingKm': remaining,
            'nextDate': next_date.isoformat() if next_date else None}
