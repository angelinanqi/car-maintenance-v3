"""HTTP boundaries used by the Android app; no live accounts or AI calls."""
import re
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from backend.main import app
from backend import auth, db
from backend.routes import mobile, nearby


IDENTIFIER = '11111111-1111-4111-8111-111111111111'
USER = {'id': IDENTIFIER, 'role': 'user'}


class MobileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Do not enter lifespan: document workers must never run in these tests.
        cls.client = TestClient(app)
        cls.paths = app.openapi()['paths']

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def tearDown(self):
        app.dependency_overrides.clear()
        nearby._requests.clear()

    def test_every_personal_endpoint_rejects_guests_before_accessing_storage(self):
        count = 0
        with patch.object(db, 'client', side_effect=AssertionError('Unexpected database access')):
            for template, methods in self.paths.items():
                if not (template.startswith(('/mobile/me', '/chat/', '/accounts/')) or template == '/chat'):
                    continue
                path = re.sub(r'\{[^}]+\}', IDENTIFIER, template)
                for method in methods:
                    with self.subTest(method=method, path=template):
                        response = self.client.request(method, path, json={})
                        self.assertEqual(response.status_code, 401, response.text)
                        self.assertEqual(response.headers['cache-control'], 'no-store')
                        self.assertEqual(response.headers['www-authenticate'], 'Bearer')
                        self.assertTrue(response.headers.get('x-request-id'))
                        count += 1
        self.assertGreaterEqual(count, 30)

    def test_all_mobile_operations_have_matching_backend_routes(self):
        operations = {
            '/config': ['get'], '/guides': ['get'], '/guides/{guide_id}': ['get'],
            '/categories': ['get'], '/manuals': ['get'], '/documents/{document_id}/download': ['get'],
            '/emergency/playbooks': ['get'], '/emergency/playbooks/{playbook_id}': ['get'],
            '/emergency/contacts': ['get'], '/emergency/nearby': ['post'],
            '/accounts/me': ['get'], '/mobile/chat-starters': ['get'],
            '/mobile/vehicle-catalogue': ['get'], '/mobile/maintenance-items': ['get'],
            '/mobile/me': ['get'], '/mobile/me/active-vehicle': ['put'],
            '/mobile/me/vehicles/{record_id}': ['put', 'delete'],
            '/mobile/me/tasks/{record_id}': ['put', 'delete'],
            '/mobile/me/records/{record_id}': ['put', 'delete'],
            '/mobile/me/progress/{guide_id}': ['put'], '/mobile/me/learning': ['get'],
            '/mobile/me/recaps/{category_id}': ['put'], '/mobile/me/incidents': ['get'],
            '/mobile/me/incidents/{record_id}': ['put'], '/mobile/me/companion': ['get'],
            '/mobile/me/service-plans/preview': ['post'], '/mobile/me/service-plans': ['post'],
            '/mobile/me/service-plans/{plan_id}': ['get'],
            '/mobile/me/saved-items': ['get', 'post'],
            '/mobile/me/saved-items/{item_id}': ['patch', 'delete'],
            '/chat': ['post'], '/chat/mechanic-questions': ['post'],
            '/chat/sessions/{session_id}': ['put'],
            '/chat/sessions/{session_id}/resume': ['post'],
            '/chat/sessions/{session_id}/activity': ['put'],
        }
        for path, methods in operations.items():
            for method in methods:
                with self.subTest(path=path, method=method):
                    self.assertIn(method, self.paths.get(path, {}))

    def test_invalid_mobile_inputs_are_422_with_safe_field_messages(self):
        app.dependency_overrides[auth.require_user] = lambda: USER
        cases = [
            ('put', '/mobile/me/vehicles/car', {'catalogueId': IDENTIFIER, 'mileage': -1}),
            ('put', '/mobile/me/tasks/task', {'id': 'task', 'vehicleId': 'car', 'title': 'Oil',
                                             'scheduleSource': 'custom'}),
            ('put', '/mobile/me/records/record', {'id': 'record', 'vehicleId': 'car', 'title': 'Oil',
                'mileage': 100, 'date': '2026-01-01', 'performedBy': 'mechanic', 'cost': 1.001}),
            ('put', '/mobile/me/incidents/incident', {'id': 'incident', 'type': 'Collision',
                'occurredAt': '2026-01-01', 'updatedAt': '2026-01-01', 'photos': ['/private/photo.jpg']}),
            ('post', '/chat', {'message': 'hello', 'unexpected_private_field': 'never echo me'}),
            ('post', '/emergency/nearby', {'latitude': 1000, 'longitude': 101, 'service': 'mechanic'}),
        ]
        with patch.object(db, 'client', side_effect=AssertionError('Unexpected database access')):
            for method, path, payload in cases:
                with self.subTest(path=path):
                    response = self.client.request(method, path, json=payload)
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertNotIn('never echo me', response.text)
                    self.assertNotIn('input', response.json()['detail'][0])

    def test_guest_nearby_response_matches_mobile_contract(self):
        result = {'places': [{'id': 'place', 'name': 'Workshop', 'address': 'Kuala Lumpur',
            'phone': '+60123456789', 'maps_url': 'https://www.google.com/maps/',
            'distance_metres': 120, 'business_status': 'OPERATIONAL', 'attributions': []}]}
        with patch.object(nearby.places, 'search', new=AsyncMock(return_value=result)):
            response = self.client.post('/emergency/nearby', json={
                'latitude': 3.14, 'longitude': 101.69, 'radius_metres': 5000, 'service': 'mechanic'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)

    def test_nearby_rate_limit_includes_retry_after(self):
        with patch.object(nearby.places, 'search', new=AsyncMock(return_value={'places': []})):
            for _ in range(10):
                response = self.client.post('/emergency/nearby', json={'latitude': 3, 'longitude': 101})
                self.assertEqual(response.status_code, 200)
            response = self.client.post('/emergency/nearby', json={'latitude': 3, 'longitude': 101})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['retry-after'], '60')

    def test_progress_rejects_stale_guide_before_writing(self):
        request = mobile.ProgressInput(completed=True, guide_revision='2026-01-01T00:00:00Z')
        from fastapi import HTTPException
        with patch.object(db, 'get', return_value={
            'status': 'published', 'category_id': None, 'updated_at': '2026-02-01T00:00:00Z'}), \
             patch.object(mobile, 'owned', return_value=None), \
             patch.object(mobile.learning_progress, 'save') as save:
            with self.assertRaises(HTTPException) as caught:
                mobile.persist_progress(IDENTIFIER, request, USER)
        self.assertEqual(caught.exception.status_code, 409)
        save.assert_not_called()

    def test_incident_retry_returns_committed_revision_without_duplicate_write(self):
        request = mobile.IncidentInput(id='incident', type='Collision',
            occurredAt='2026-01-01T00:00:00Z', updatedAt='2026-01-01T00:00:00Z')
        payload = request.model_dump(mode='json', exclude={'id', 'cloudRevision', 'pendingSync'})
        with patch.object(mobile, 'owned', return_value={
            'id': 'incident', 'payload': payload, 'revision': 2}), patch.object(mobile, 'put') as put:
            result = mobile.save_incident('incident', request, USER)
        self.assertEqual(result['cloudRevision'], 2)
        put.assert_not_called()


if __name__ == '__main__':
    unittest.main()
