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
    rule = (
        task.get("manufacturerRule")
        if task["scheduleSource"] == "manufacturer"
        else (task.get("customRule") if task["scheduleSource"] == "custom" else None)
    )
    result = {
        "label": "No schedule",
        "nextKm": None,
        "remainingKm": None,
        "nextDate": None,
    }
    if not rule:
        return result
    if rule["type"] == "informational" or rule.get("conditions"):
        return {**result, "label": "Information required — review schedule conditions"}
    history = sorted(
        (r for r in records if r.get("taskId") == task["id"]),
        key=lambda r: (r["date"], r["mileage"], r["id"]),
        reverse=True,
    )
    last = history[0] if history else None
    if not last and rule["type"] in {"recurring", "milestone"}:
        return {**result, "label": "Untracked"}
    km = next_date = None
    missing = False
    if rule["type"] == "recurring":
        if not (rule.get("distanceKm") or rule.get("months")):
            return {**result, "label": "Information required"}
        if rule.get("distanceKm"):
            km = last["mileage"] + rule["distanceKm"]
        if rule.get("months"):
            try:
                next_date = add_months(as_date(last["date"]), rule["months"])
            except (ValueError, OverflowError):
                return {**result, "label": "Information required"}
    elif rule["type"] == "milestone":
        km = next(
            (
                m
                for m in rule.get("distanceMilestones", [])
                if m > last["mileage"]
            ),
            None,
        )
        months = rule.get("monthMilestones", [])
        start = rule.get("vehicleStartDate")
        missing = bool(months and not start)
        if months and start:
            try:
                last_date = as_date(last["date"])
                start_date = as_date(start)
                dates = (add_months(start_date, m) for m in months)
                next_date = next(
                    (milestone for milestone in dates if milestone > last_date),
                    None,
                )
            except (ValueError, OverflowError):
                return {**result, "label": "Information required"}
        if km is None and next_date is None and not missing:
            return {**result, "label": "Published milestones completed"}
    else:
        return {**result, "label": "Information required"}
    remaining = km - odometer if km is not None else None
    days = (next_date - today).days if next_date else None
    due = (remaining is not None and remaining <= 0) or (days is not None and days <= 0)
    # A confirmed threshold can make the item due on its own. Until then,
    # an unknown threshold prevents determining which service point is next.
    if missing and not due:
        return {**result, "label": "Information required"}
    soon = (remaining is not None and remaining <= due_soon_km) or (
        days is not None and days <= due_soon_days
    )
    return {
        "label": "Due / Overdue" if due else "Due soon" if soon else "Upcoming",
        "nextKm": km,
        "remainingKm": remaining,
        "nextDate": next_date.isoformat() if next_date else None,
    }
