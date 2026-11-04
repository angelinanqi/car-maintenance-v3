"""YouTube transport regression tests; never contact the live API."""
import io
import socket
import ssl
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from rag.app.youtube import discovery


class YouTubeTransportTests(unittest.TestCase):
    def test_uses_verified_tls_with_available_ca_roots_and_private_key_header(self):
        with patch.object(discovery, 'urlopen', return_value=io.BytesIO(b'{"items": []}')) as transport:
            self.assertEqual(discovery.api_get('channels', 'secret-key', forHandle='@example'), {'items': []})
        request = transport.call_args.args[0]
        context = transport.call_args.kwargs['context']
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()['x509_ca'], 0)
        self.assertNotIn('secret-key', request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), 'secret-key')

    def test_connection_errors_are_actionable_without_exposing_secrets(self):
        cases = [
            (URLError(ssl.SSLCertVerificationError(1, 'secret-key')), 'TLS certificate verification failed'),
            (URLError(socket.gaierror(-2, 'secret-key')), 'DNS lookup failed'),
            (URLError(TimeoutError('secret-key')), 'connection timed out'),
            (TimeoutError('secret-key'), 'connection timed out'),
            (URLError('secret-key'), 'connection failed'),
            (HTTPError('https://example.com?key=secret-key', 403, 'secret-key', {}, None), 'HTTP 403'),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected), patch.object(discovery, 'urlopen', side_effect=error):
                with self.assertRaises(RuntimeError) as caught:
                    discovery.api_get('channels', 'secret-key')
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn('secret-key', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
