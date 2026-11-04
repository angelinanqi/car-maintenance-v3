"""Concurrent schedule source reads must not conflict with one another."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import auth
from backend.locks import content_lock
from backend.routes import maintenance_assistance as routes


class ScheduleSourceConcurrencyTests(unittest.TestCase):
    def test_overlapping_source_reads_finish_after_the_first_read(self):
        for first, second in [('original', 'detail'), ('detail', 'original'),
                              ('detail', 'detail'), ('detail', 'tables'),
                              ('detail', 'suggestions')]:
            with self.subTest(first=first, second=second):
                self.check_overlapping_reads(first, second)

    def check_overlapping_reads(self, first, second):
        document_id, revision = uuid4(), uuid4()
        document = {'id': str(document_id), 'source_revision': str(revision),
                    'name': 'Service manual', 'source_type': 'pdf', 'storage_path': 'manual.pdf'}
        state = {'version': 1, 'catalogue': {'tables': []}, 'selections': [],
                 'suggestions': [], 'bookmarks': []}
        holding, attempted, release = Event(), Event(), Event()

        @contextmanager
        def observed_lock(record_id, **kwargs):
            if holding.is_set():
                attempted.set()
            with content_lock(record_id, **kwargs):
                yield

        def slow_read(result):
            if not holding.is_set():
                holding.set()
                if not release.wait(5):
                    raise AssertionError('The first source read was never released.')
            return result

        def url(endpoint):
            suffix = '' if endpoint == 'detail' else '/' + endpoint
            return f'/admin/maintenance-assistance/documents/{document_id}{suffix}?source_revision={revision}'

        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[auth.require_admin] = lambda: {}
        with (patch.object(routes, 'content_lock', observed_lock),
              patch.object(routes.service, 'current_document', return_value=document),
              patch.object(routes.service, 'load', side_effect=lambda _: slow_read(state)),
              patch.object(routes.db, 'bucket') as bucket,
              TestClient(app) as client,
              ThreadPoolExecutor(max_workers=2) as pool):
            bucket.return_value.download.side_effect = lambda _: slow_read(b'%PDF-1.4 test')
            first_request = pool.submit(client.get, url(first))
            try:
                self.assertTrue(holding.wait(5))
                second_request = pool.submit(client.get, url(second))
                self.assertTrue(attempted.wait(5))
                # A read should wait for the in-flight read, not immediately fail.
                with self.assertRaises(TimeoutError):
                    second_request.result(timeout=0.05)
            finally:
                release.set()
            self.assertEqual(first_request.result(timeout=5).status_code, 200)
            response = second_request.result(timeout=5)
            self.assertEqual(response.status_code, 200, response.text)

    def test_original_still_rejects_a_stale_revision(self):
        document_id, revision = uuid4(), uuid4()
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[auth.require_admin] = lambda: {}
        with (patch.object(routes.db, 'get', return_value={'source_revision': str(uuid4())}),
              patch.object(routes.db, 'bucket') as bucket,
              TestClient(app) as client):
            response = client.get(
                f'/admin/maintenance-assistance/documents/{document_id}/original?source_revision={revision}')
        self.assertEqual(response.status_code, 409)
        self.assertIn('revision changed', response.json()['detail'])
        bucket.assert_not_called()

    def test_long_running_operation_still_returns_busy_after_bounded_wait(self):
        document_id, revision = uuid4(), uuid4()
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[auth.require_admin] = lambda: {}
        with (content_lock(document_id),
              patch.object(routes, 'READ_LOCK_TIMEOUT', 0.01),
              patch.object(routes.service, 'current_document') as lookup,
              TestClient(app) as client):
            for suffix in ['', '/original', '/tables', '/suggestions']:
                response = client.get(
                    f'/admin/maintenance-assistance/documents/{document_id}{suffix}?source_revision={revision}')
                self.assertEqual(response.status_code, 409)
                self.assertIn('record is busy', response.json()['detail'])
        lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
