import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.routes import admin


class AdminIntervalTests(unittest.TestCase):
    def values(self):
        return {'vehicle_id': 'car', 'entries': [
            {'itemId': identity, 'action': 'replace', 'rule': {
                'type': 'recurring', 'distanceKm': 10000, 'months': 6,
                'sourceDocumentId': 'manual', 'sourceRevision': 'revision', 'sourcePage': 12,
            }} for identity in ('oil', 'filter')]}

    def rows(self, table, **filters):
        if table == 'maintenance_items':
            return [{'id': identity, 'title': identity, 'action': 'replace', 'active': True}
                    for identity in ('oil', 'filter')]
        if table == 'document_vehicles':
            return [{'vehicle_id': 'car', 'document_id': 'manual'}]
        self.fail(f'Unexpected table: {table}')

    def document(self, table, identity):
        return {'source_type': 'pdf', 'source_revision': 'revision'} if table == 'documents' else {'id': identity}

    def test_shared_source_is_read_once_per_validation_and_reloaded_on_next_request(self):
        with patch.object(admin.db, 'get', side_effect=self.document) as get, \
                patch.object(admin.db, 'all_rows', side_effect=self.rows) as rows, \
                patch.object(admin.review_questions, 'check_schedule'):
            for _ in range(2):
                admin.validate_schedule(self.values(), publishing=True)
        self.assertEqual(sum(call.args[0] == 'documents' for call in get.call_args_list), 2)
        self.assertEqual(sum(call.args[0] == 'maintenance_items' for call in rows.call_args_list), 2)
        self.assertEqual(sum(call.args[0] == 'document_vehicles' for call in rows.call_args_list), 2)

    def test_revision_and_association_checks_are_preserved(self):
        with patch.object(admin.db, 'get', side_effect=self.document), \
                patch.object(admin.db, 'all_rows', side_effect=self.rows):
            values = self.values()
            values['entries'][1]['rule']['sourceRevision'] = 'outdated'
            with self.assertRaises(HTTPException) as error:
                admin.validate_schedule(values)
            self.assertEqual(error.exception.status_code, 409)
        def unlinked(table, **filters):
            return [] if table == 'document_vehicles' else self.rows(table, **filters)
        with patch.object(admin.db, 'get', side_effect=self.document), \
                patch.object(admin.db, 'all_rows', side_effect=unlinked):
            with self.assertRaises(HTTPException) as error:
                admin.validate_schedule(self.values())
            self.assertEqual(error.exception.status_code, 422)

    def test_unavailable_items_cannot_be_published(self):
        def inactive(table, **filters):
            rows = self.rows(table, **filters)
            return [{**row, 'active': False} for row in rows] if table == 'maintenance_items' else rows
        with patch.object(admin.db, 'get', side_effect=self.document), \
                patch.object(admin.db, 'all_rows', side_effect=inactive), \
                patch.object(admin.review_questions, 'check_schedule'):
            with self.assertRaises(HTTPException) as error:
                admin.validate_schedule(self.values(), publishing=True)
            self.assertEqual(error.exception.status_code, 422)

    def test_library_excludes_superseded_schedules(self):
        with patch.object(admin.db, 'list_rows', return_value=[]) as rows:
            admin.maintenance_intervals(offset=10, limit=20)
        rows.assert_called_once_with('manufacturer_schedules', offset=10, limit=20,
                                    status=['draft', 'published'])


if __name__ == '__main__':
    unittest.main()
