"""Explain plan evidence through fields supported by the existing mobile app.

Only decorate outgoing responses. Stored rules, snapshots and the timing engine
remain authoritative; these display strings must never feed back into them.
"""
from copy import deepcopy

from backend.services.maintenance import as_date


def readable_date(value):
    try:
        return as_date(value).strftime('%d %b %Y').lstrip('0')
    except (ValueError, TypeError):
        return str(value)


def missing_details(item):
    rule = item.get('rule')
    if not rule:
        return 'No reminder set. Add a service interval to calculate when this is due.'
    if rule.get('conditions'):
        return 'Timing depends on the schedule conditions. Review them with your mechanic.'
    if rule['type'] == 'informational':
        return 'This item has maintenance guidance rather than a fixed service interval.'
    if rule['type'] == 'milestone' and item['status']['label'] in {
        'Untracked', 'Published milestone — confirm service history',
    }:
        return 'Confirm previous services before deciding which listed service point applies.'
    if 'latest_service' not in item:
        return 'Refresh this saved plan to see which service details are missing.'
    if rule['type'] == 'recurring' and item['latest_service'] is None:
        return 'Previous service record missing — next due point unknown. Record when this item was last serviced to calculate its next service.'
    if rule['type'] == 'milestone' and rule.get('monthMilestones') and not rule.get('vehicleStartDate'):
        return 'Vehicle start date missing. Age-based service timing cannot be confirmed.'
    return 'Review the saved interval and service record. A due point could not be confirmed.'


def timing_summary(item, as_of):
    label = item['status']['label']
    if item['reason'] == 'schedule_or_history_needs_review':
        return missing_details(item)
    if label == 'Published milestones completed':
        return 'All listed service points completed. Check the manual for any further guidance.'
    details = []
    remaining = item['status'].get('remainingKm')
    if remaining is not None:
        details.append(f'{abs(remaining):,} km overdue' if remaining < 0 else
                       'Due at the recorded mileage' if remaining == 0 else
                       f'{remaining:,} km remaining')
    if item['status'].get('nextDate'):
        days = (as_date(item['status']['nextDate']) - as_date(as_of)).days
        count = abs(days)
        unit = 'day' if count == 1 else 'days'
        details.append(f'{count} {unit} overdue' if days < 0 else
                       'Due on the plan date' if days == 0 else f'{days} {unit} remaining')
    return ' · '.join(['Due now' if label == 'Due / Overdue' else label, *details])


def schedule_details(rule):
    if rule['type'] == 'recurring':
        intervals = []
        if rule.get('distanceKm'):
            intervals.append(f"{rule['distanceKm']:,} km")
        if rule.get('months'):
            intervals.append(f"{rule['months']} {'month' if rule['months'] == 1 else 'months'}")
        if intervals:
            return 'Interval: Every ' + ' or '.join(intervals) + (
                ', whichever comes first.' if len(intervals) > 1 else '.')
    if rule['type'] == 'milestone':
        points = []
        if rule.get('distanceMilestones'):
            points.append('at ' + ', '.join(f'{km:,}' for km in rule['distanceMilestones']) + ' km')
        if rule.get('monthMilestones'):
            points.append('at vehicle age ' + ', '.join(str(m) for m in rule['monthMilestones']) + ' months')
        if points:
            return 'Listed service points: ' + '; '.join(points) + '.'
    return 'Interval: No fixed service interval is available.'


def display_details(item, snapshot):
    """Structured presentation for new clients; old clients still read notes."""
    rule, timing = item.get('rule'), item['status']
    details = {'summary': timing_summary(item, snapshot['as_of']),
               'schedule': schedule_details(rule) if rule else 'No service interval saved.',
               'calculations': [], 'conditions': (rule or {}).get('conditions', ''),
               'notes': (rule or {}).get('notes', ''), 'planning_note': None,
               'source_label': 'No schedule saved', 'source_reference': None}
    if 'latest_service' not in item:
        details['history'] = 'Refresh this saved plan to load its service history.'
    elif item['latest_service'] is None:
        details['history'] = 'No previous service is linked to this item.'
    else:
        last = item['latest_service']
        details['history'] = f"{readable_date(last['date'])} at {last['mileage']:,} km."
        if rule and rule['type'] == 'recurring' and item['reason'] != 'schedule_or_history_needs_review':
            if timing.get('nextKm') is not None and rule.get('distanceKm'):
                details['calculations'].append(f"{last['mileage']:,} km + {rule['distanceKm']:,} km = {timing['nextKm']:,} km")
            if timing.get('nextDate') and rule.get('months'):
                unit = 'month' if rule['months'] == 1 else 'months'
                details['calculations'].append(f"{readable_date(last['date'])} + {rule['months']} {unit} = {readable_date(timing['nextDate'])}")
    details['timing_note'] = (
        'The vehicle start date is missing, so age-based timing still needs confirmation.'
        if rule and rule['type'] == 'milestone' and rule.get('monthMilestones') and not rule.get('vehicleStartDate')
        else None)
    if item['reason'] == 'within_discussion_window':
        window = snapshot.get('discussion_window')
        if window:
            details['planning_note'] = (f"MyRoadie flags items within {window['km']:,} km or "
                                       f"{window['days']} days. This is an app setting; the scheduled due point still applies.")
    if item['schedule_source'] == 'manufacturer' and rule:
        reference = item.get('source_name') or 'Document title unavailable'
        if rule.get('sourcePage'):
            reference += f", page {rule['sourcePage']}"
        elif rule.get('sourceTableId'):
            reference += ', reviewed source table'
        details['source_label'] = 'Manufacturer schedule'
        details['source_reference'] = reference
    elif item['schedule_source'] == 'custom' and rule:
        details['source_label'] = 'Your custom reminder'
        details['source_reference'] = 'This interval was chosen for this item in the app.'
    return details


def explanation(details):
    parts = [details['summary'], details['schedule'], 'Last recorded service: ' + details['history']]
    if details['calculations']:
        parts.append('Next service calculation:\n' + '\n'.join(details['calculations']))
    if details['timing_note']:
        parts.append(details['timing_note'])
    if details['planning_note']:
        parts.append('Planning reminder: ' + details['planning_note'])
    if details['source_label'] == 'Manufacturer schedule':
        parts.append('Source: Manufacturer schedule published in MyRoadie.\nReference: ' + details['source_reference'] + '.')
    else:
        parts.append('Source: ' + details['source_label'] + '. ' + (details['source_reference'] or ''))
    if details['notes']:
        parts.append('Schedule note: ' + details['notes'])
    return '\n\n'.join(parts)


def for_mobile(plan):
    """Use existing label/notes fields so installed apps need no rebuild."""
    result = deepcopy(plan)
    snapshot = result['snapshot']
    for items in snapshot['groups'].values():
        for item in items:
            details = display_details(item, snapshot)
            item['display'] = details
            if item.get('rule'):
                item['rule'] = {**item['rule'], 'notes': explanation(details)}
            item['status']['label'] = details['summary']
            # The current app labels any nextKm/nextDate as "Due". Do not show
            # unconfirmed milestones as definite deadlines; list them in notes.
            if item['reason'] == 'schedule_or_history_needs_review':
                item['status']['nextKm'] = None
                item['status']['nextDate'] = None
    return result
