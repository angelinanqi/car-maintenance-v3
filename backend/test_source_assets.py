"""Regression coverage for manual fallback links in mixed retrieval scopes."""
import unittest
from unittest.mock import patch

from backend.services.source_assets import resolve_manual_sources


class ManualBrowseTests(unittest.TestCase):
    def test_browse_skips_indexed_guides_and_keeps_manual_downloads(self):
        scope = {'document_metadata': {
            'protocol_rev': {'document_id': 'protocol', 'index_revision': 'rev',
                             'source_type': 'emergency_protocol'},
            'guide_rev': {'document_id': 'guide', 'index_revision': 'rev',
                          'source_type': 'learning_guide'},
            'manual_rev': {'document_id': 'manual', 'index_revision': 'rev'},
        }}
        document = {'name': 'Manual', 'source_revision': 'rev',
                    'published': True, 'mobile_visible': True}
        with patch('backend.services.source_assets.source_document', return_value=document) as lookup:
            sources, links = resolve_manual_sources(
                [], scope, 'session', {'role': 'user'}, browse=True)
        lookup.assert_called_once_with('manual', scope['document_metadata']['manual_rev'])
        self.assertEqual(sources, [])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['source_endpoint'],
                         '/chat/sessions/session/sources/manual/rev/original')

    def test_guide_only_scope_preserves_citations_without_manual_lookup(self):
        scope = {'document_metadata': {'protocol_rev': {
            'document_id': 'protocol', 'index_revision': 'rev',
            'source_type': 'emergency_protocol'}}}
        citation = {'source_type': 'emergency_protocol', 'source_id': 'protocol'}
        with patch('backend.services.source_assets.source_document') as lookup:
            sources, links = resolve_manual_sources(
                [citation], scope, 'session', {'role': 'user'}, browse=True)
        lookup.assert_not_called()
        self.assertEqual(sources, [citation])
        self.assertEqual(links, [])
