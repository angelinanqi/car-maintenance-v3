"""Regression tests for lost evidence; no network/model inference required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from rag.app.generation.context import prepare_context, encoded_size
from rag.app.query import prepare_references, rank_visuals
from rag.app.retrieval.search import RetrievalResult
from shared.table_evidence import table_fragments


def record(identity, kind='paragraph', text='Useful complete instructions.', **metadata):
    return RetrievalResult(1, identity, 0.0, text, dict(document_name='manual',
        content_type=kind, source_content=text, section_path=['Oil level check'], **metadata))


class EvidenceSelectionTests(unittest.TestCase):
    def test_visual_search_uses_section_but_returns_unchanged_evidence(self):
        original = 'Generated identification (unverified): Oil Level Gauge'
        records = [record('a', 'image', original), record('b', 'image', 'Other reviewed diagram')]
        captured = []

        def rerank(query, candidates):
            captured.extend(candidates)
            return list(reversed(candidates))

        with patch('rag.app.query.settings.RAG_RERANK', True), \
                patch('rag.app.retrieval.hybrid.rerank', side_effect=rerank):
            ranked = rank_visuals('engine oil', records)
        self.assertIn('Section: Oil level check', captured[0].text)
        self.assertEqual(captured[1].text, 'Other reviewed diagram')
        self.assertEqual(ranked[1].text, original)
        self.assertEqual(ranked[1].metadata['source_content'], original)

    def test_original_shortlist_preserves_relevance_across_kinds(self):
        elements = [dict(element_id='image-00001', kind='image', association_verified=True,
            caption='', section_path=['Relevant component'], description='A diagram', pages=[],
            context=[], notes=[])]
        elements.extend(dict(element_id=f'table-{i:05}', kind='table', caption='',
            section_path=['Other section'], description='Other table', cells=[], pages=[],
            context=[], notes=[]) for i in range(2, 10))
        records = [record(str(i), e['kind'], element_id=e['element_id']) for i, e in enumerate(elements)]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sources').mkdir()
            (root / 'sources/manual.json').write_text(json.dumps(dict(format_version=2, elements=elements)))
            with patch('rag.app.query.settings.OUTPUT_DIR', root), \
                    patch('rag.app.query.settings.RAG_VISUAL_INPUTS', False):
                references = prepare_references(records)
        self.assertEqual(references[0]['element_id'], 'image-00001')
        self.assertEqual(len(references), 6)  # Illustration plus five-table bound.

    def test_visual_metadata_cannot_starve_ranked_prose(self):
        prose = record('instructions', text='Park safely. Read the gauge between its marks. ' * 8)
        references, pixels = [], []
        for i in range(1, 9):
            label = f'V{i + 8}'
            references.append(dict(label=f'V{i}', kind='image', document_name='manual',
                element_id=f'image-{i:05}', title='Illustration', description='A description',
                pixel_source_labels=[label]))
            pixels.append(dict(label=label, title='Original page', pixels_supplied=True,
                source_extent='page', content='Original evidence metadata. ' * 15))
        with patch('rag.app.generation.context.settings.RAG_CONTEXT_CHARS', 4000):
            context = prepare_context([prose], references, image_sources=pixels)
        self.assertEqual(next(s['content'] for s in context.sources if s['label'] == 'S1'), prose.text)
        self.assertNotIn('S1', context.omitted_sources)
        self.assertLessEqual(sum(encoded_size(s) for s in context.sources)
                             + sum(encoded_size(r) for r in context.references), 4000)

    def test_highest_ranked_table_is_not_starved_by_equal_candidate_shares(self):
        records, references = [], []
        for i in range(1, 6):
            element = dict(element_id=f'table-{i:05}', kind='table', structure_valid=True,
                caption='Pressure', notes=[], cells=[dict(row=0, column=0, rowspan=1,
                    colspan=1, header=True, text='kPa'), dict(row=1, column=0, rowspan=1,
                    colspan=1, header=False, text='230')])
            fragment = table_fragments(element)[0]
            records.append(record(str(i), 'table', json.dumps(fragment),
                element_id=element['element_id'], evidence_type='table_cells_v1', structure_valid=True))
            references.append(dict(label=f'V{i}', kind='table', document_name='manual',
                element_id=element['element_id'], title='Pressure', description='Pressure table',
                table_element=element, pixel_source_labels=[], requires_page_images=False))
        with patch('rag.app.generation.context.settings.RAG_CONTEXT_CHARS', 5000):
            context = prepare_context(records, references)
        first = next(source for source in context.sources if source['label'] == 'S1')
        self.assertTrue(first['table_complete'])
        self.assertIn('230', first['content'])


if __name__ == '__main__':
    unittest.main()
