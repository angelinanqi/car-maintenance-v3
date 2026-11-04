"""Bounded read waits must preserve exclusive mutation protection."""
from uuid import uuid4
import unittest

from fastapi import HTTPException

from backend.locks import content_lock


class ContentLockTests(unittest.TestCase):
    def test_mutations_still_fail_when_the_record_is_busy(self):
        record_id = uuid4()
        with content_lock(record_id):
            with self.assertRaises(HTTPException) as error:
                with content_lock(record_id):
                    self.fail('A concurrent mutation acquired the lock.')
        self.assertEqual(error.exception.status_code, 409)

    def test_read_wait_is_bounded_and_does_not_release_the_holder(self):
        record_id = uuid4()
        with content_lock(record_id):
            with self.assertRaises(HTTPException) as error:
                with content_lock(record_id, timeout=0.01):
                    self.fail('A timed-out reader acquired the lock.')
            self.assertEqual(error.exception.status_code, 409)
            with self.assertRaises(HTTPException):
                with content_lock(record_id):
                    self.fail('The timed-out reader released another holder.')
        with content_lock(record_id):
            pass

    def test_exception_releases_the_lock(self):
        record_id = uuid4()
        with self.assertRaises(ValueError):
            with content_lock(record_id, timeout=0.01):
                raise ValueError('Failed read')
        with content_lock(record_id):
            pass


if __name__ == '__main__':
    unittest.main()
