import json
import unittest
from uuid import NAMESPACE_URL, uuid5

from scripts.prepare_admin_demo import MANIFEST, ready, schedule_plan


class DemoPreparationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        self.data = {'knowledge_vehicles': [], 'documents': [], 'document_vehicles': [],
                     'maintenance_items': [], 'manufacturer_schedules': []}
        titles = set()
        for spec in self.manifest['vehicles']:
            identity = str(uuid5(NAMESPACE_URL, spec['vehicle_code']))
            self.data['knowledge_vehicles'].append({'id': identity, 'code': spec['vehicle_code']})
            self.data['documents'].append({'id': spec['source_document_id'],
                'source_revision': spec['source_revision'], 'indexed_revision': spec['source_revision'],
                'status': 'processed', 'chunk_count': 1})
            self.data['document_vehicles'].append({'vehicle_id': identity, 'document_id': spec['source_document_id']})
            titles.update(entry['item_title'] for entry in spec['entries'])
        for title in titles:
            action = 'replace' if title.startswith('Replace ') else 'service' if title.startswith(('Top up ', 'Rotate ', 'Check and adjust ')) else 'inspect'
            self.data['maintenance_items'].append({'id': str(uuid5(NAMESPACE_URL, title)),
                                                  'title': title, 'action': action, 'active': True})

    def test_checked_manifest_builds_valid_rules_without_duplicate_items(self):
        plans, skipped = schedule_plan(self.data, self.manifest)
        self.assertEqual(len(plans), 10)
        self.assertFalse(skipped)
        for plan in plans:
            self.assertTrue(plan['publishable'])
            entries = plan['request'].entries
            self.assertEqual(len(entries), len({entry.itemId for entry in entries}))
            self.assertTrue(all(entry.rule.sourcePage and entry.rule.sourceRevision for entry in entries))

    def test_changed_revision_is_not_transcribed_from_old_source(self):
        self.data['documents'][0]['source_revision'] = str(uuid5(NAMESPACE_URL, 'new revision'))
        plans, skipped = schedule_plan(self.data, self.manifest)
        self.assertEqual(len(plans), 9)
        self.assertIn('revision changed', skipped[0]['reason'])

    def test_failed_source_only_produces_draft(self):
        self.data['documents'][0].update(status='failed', indexed_revision=None)
        plans, _ = schedule_plan(self.data, self.manifest)
        self.assertFalse(plans[0]['publishable'])

    def test_existing_schedule_is_preserved_even_on_rerun(self):
        self.data['manufacturer_schedules'] = [{'id': 'admin-edit', 'vehicle_id': self.data['knowledge_vehicles'][0]['id']}]
        plans, skipped = schedule_plan(self.data, self.manifest)
        self.assertEqual(len(plans), 9)
        self.assertEqual(skipped[0]['schedule_ids'], ['admin-edit'])

    def test_source_needs_current_index_and_nonempty_content(self):
        source = self.data['documents'][0]
        self.assertTrue(ready(source))
        self.assertFalse(ready({**source, 'indexed_revision': 'outdated'}))
        self.assertFalse(ready({**source, 'chunk_count': 0}))
        self.assertFalse(ready({**source, 'superseded_by_id': 'replacement'}))


if __name__ == '__main__':
    unittest.main()
