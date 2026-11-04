"""Enable existing vehicle content and import source-checked maintenance schedules.

Preview: python -m scripts.prepare_admin_demo
Apply:   python -m scripts.prepare_admin_demo --apply

No accounts, personal vehicles, service history, or sample intervals are created.
Existing schedules and administrator edits are preserved. Source revisions must
match the checked manifest; failed/unindexed sources produce drafts only.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException

from backend import db, settings
from backend.models import ReviewConfirmation
from backend.routes.admin import ScheduleInput, ScheduleReview, create_schedule, publish_schedule
from backend.routes.documents import publish_document

MANIFEST = Path(__file__).with_name('data') / 'admin_maintenance_intervals.json'
TABLES = ('vehicle_manufacturers', 'vehicle_models', 'knowledge_vehicles',
          'maintenance_items', 'manufacturer_schedules', 'documents',
          'document_vehicles', 'guide_categories')


def ready(document):
    return bool(document.get('status') == 'processed' and document.get('chunk_count', 0) > 0
                and document.get('indexed_revision') == document.get('source_revision')
                and document.get('indexed_revision') and not document.get('superseded_by_id'))


def schedule_plan(data, manifest):
    vehicles = {row['code']: row for row in data['knowledge_vehicles']}
    documents = {row['id']: row for row in data['documents']}
    items = {row['title']: row for row in data['maintenance_items']}
    associations = {(row['vehicle_id'], row['document_id']) for row in data['document_vehicles']}
    plans, skipped = [], []
    for spec in manifest['vehicles']:
        code = spec['vehicle_code']
        vehicle, document = vehicles.get(code), documents.get(spec['source_document_id'])
        if not vehicle or not document:
            skipped.append({'vehicle': code, 'reason': 'Checked vehicle or document is missing.'})
            continue
        if document['source_revision'] != spec['source_revision']:
            skipped.append({'vehicle': code, 'reason': 'Source revision changed; review its intervals again.'})
            continue
        if (vehicle['id'], document['id']) not in associations:
            skipped.append({'vehicle': code, 'reason': 'The checked source is not assigned to this vehicle.'})
            continue
        identity = str(uuid5(NAMESPACE_URL, 'roadie:reviewed-schedule:' + code + ':' + spec['source_revision']))
        existing = [row for row in data['manufacturer_schedules'] if row['vehicle_id'] == vehicle['id']]
        if existing:
            # A rerun must never recreate, replace or republish an edited/retired schedule.
            skipped.append({'vehicle': code, 'reason': 'Existing schedule preserved.',
                            'schedule_ids': [row['id'] for row in existing]})
            continue
        entries = []
        for checked in spec['entries']:
            item = items.get(checked['item_title'])
            if not item or not item['active']:
                raise ValueError(f"{code}: active service task missing: {checked['item_title']}")
            rule = {key: value for key, value in checked.items() if key not in ('item_title', 'page')}
            rule.update(sourceDocumentId=document['id'], sourceRevision=document['source_revision'],
                        sourcePage=checked['page'])
            entries.append({'itemId': item['id'], 'action': item['action'], 'rule': rule})
        request = ScheduleInput.model_validate(dict(
            id=identity, vehicle_id=vehicle['id'], entries=entries,
            admin_note=('Source-checked normal-use subset imported for the demo. '
                        'Review additional tasks against the exact vehicle equipment and severe-use table. '
                        'Unlisted intervals remain unset. Conditional and irregular rules need service-history/equipment checks.'),
            work_context={'document_id': document['id'], 'source_revision': document['source_revision'],
                          'page': spec['entries'][0]['page']},
        ))
        plans.append({'vehicle': code, 'request': request, 'publishable': ready(document)})
    return plans, skipped


def prepare(*, apply=False):
    data = {table: db.all_rows(table) for table in TABLES}
    manifest = json.loads(MANIFEST.read_text())
    plans, skipped = schedule_plan(data, manifest)
    linked = {row['document_id'] for row in data['document_vehicles']}
    documents = [row for row in data['documents'] if row['id'] in linked
                 and not row.get('published') and ready(row) and not row.get('replacement_for_id')]
    print(json.dumps({
        'vehicles': len(data['knowledge_vehicles']),
        'vehicle_scopes_to_enable': sum(not row['published'] for row in data['knowledge_vehicles']),
        'ready_documents_to_publish': [row['name'] for row in documents],
        'schedules_to_import': [{'vehicle': plan['vehicle'], 'entries': len(plan['request'].entries),
                                 'status': 'published' if plan['publishable'] else 'draft (source not ready)'} for plan in plans],
        'skipped': skipped,
        'sources_needing_review': [{'name': row['name'], 'status': row['status'], 'error': row.get('error')}
                                   for row in data['documents'] if row['id'] in linked and not ready(row)],
        'categories': [{'name': row['name'], 'published': row['published'],
                        'chatbot_enabled': row.get('knowledge_published'), 'archived': row.get('archived')}
                       for row in data['guide_categories']],
    }, indent=2), flush=True)
    if not apply:
        print('Preview only. Use --apply to save these changes.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = settings.OUTPUT_DIR / 'admin-demo'
    destination.mkdir(parents=True, exist_ok=True)
    backup = destination / f'before-{stamp}.json'
    backup.write_text(json.dumps(data, indent=2))
    print(f'Catalogue/content backup: {backup}', flush=True)
    report = {'enabled': [], 'published_documents': [], 'schedules': [],
              'needs_review': skipped + [
                  {'document': row['name'], 'reason': row.get('error') or 'Source is not ready.'}
                  for row in data['documents'] if row['id'] in linked and not ready(row)]}
    for table in ('vehicle_manufacturers', 'vehicle_models', 'knowledge_vehicles'):
        for row in data[table]:
            changes = {'active': True} if not row['active'] else {}
            if table == 'knowledge_vehicles' and not row['published']:
                changes['published'] = True
            if changes:
                db.update(table, row['id'], changes)
                report['enabled'].append({'table': table, 'id': row['id'], 'name': row['name']})
    for row in data['guide_categories']:
        if row['published'] and not row.get('archived') and not row.get('knowledge_published'):
            db.update('guide_categories', row['id'], {'knowledge_published': True})
            report['enabled'].append({'table': 'guide_categories', 'id': row['id'], 'name': row['name']})
    for row in documents:
        try:
            publish_document(UUID(row['id']), ReviewConfirmation(confirm_review=True))
            report['published_documents'].append(row['name'])
            print('Published document:', row['name'], flush=True)
        except HTTPException as error:
            report['needs_review'].append({'document': row['name'], 'reason': error.detail})
    for plan in plans:
        request = plan['request']
        saved = create_schedule(request)
        print('Saved schedule:', plan['vehicle'], len(saved['entries']), 'tasks', flush=True)
        if plan['publishable']:
            try:
                saved = publish_schedule(UUID(saved['id']), ScheduleReview(
                    confirm_review=True, expected_updated_at=saved['updated_at']))
            except HTTPException as error:
                report['needs_review'].append({'vehicle': plan['vehicle'], 'reason': error.detail})
        report['schedules'].append({'vehicle': plan['vehicle'], 'id': saved['id'],
                                    'status': saved['status'], 'entry_count': len(saved['entries'])})
        (destination / f'result-{stamp}.json').write_text(json.dumps(report, indent=2))
    (destination / f'result-{stamp}.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    prepare(apply=parser.parse_args().apply)
