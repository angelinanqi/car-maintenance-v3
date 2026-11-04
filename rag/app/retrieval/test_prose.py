"""Prevent source-subject loss and cross-column context contamination."""
import unittest
from unittest.mock import patch

from rag.app.generation.context import content, prepare_context
from rag.app.retrieval.prose import preceding_context, select_prose
from rag.app.retrieval.search import RetrievalResult


def block(text, x=350, y=100, width=290, page=0, heading=False):
    return dict(type='text', text=text, bbox=[x, y, x + width, y + 25],
                page_idx=page, **({'text_level': 2} if heading else {}))


def record(identity, text, rank=1):
    return RetrievalResult(rank, identity, 0, text, dict(document_name='manual',
        content_type='paragraph', source_content=text, section_path=['CAUTION']))


class ProseTests(unittest.TestCase):
    def test_warning_recovers_subject_without_other_column_or_page(self):
        rows = [block('Wrong brake instruction.', x=30, y=20),
                block('Washer fluid level check', y=20, heading=True),
                block('Use clean washer fluid.', y=60),
                block('WARNING', x=365, y=100, width=100, heading=True),
                block('Dirty fluid can block your vision.', y=140),
                block('Earlier page instruction.', y=30, page=1)]
        result = preceding_context('Dirty fluid can block your vision.', rows)
        self.assertIn('Washer fluid level check', result['text'])
        self.assertIn('WARNING', result['text'])
        self.assertNotIn('brake', result['text'])
        self.assertNotIn('Earlier page', result['text'])
        self.assertEqual(result['pdf_page'], 1)

    def test_complete_multi_block_match_and_real_heading_boundary(self):
        rows = [block('Other topic.', y=10),
                block('Transmission fluid', y=40, heading=True),
                block('CAUTION', y=80, width=100, heading=True),
                block('If the fluid is dirty, change it.', y=120),
                block('Have the system inspected.', y=160)]
        result = preceding_context('If the fluid is dirty, change it.\n\nHave the system inspected.', rows)
        self.assertEqual(result['text'], 'Transmission fluid\n\nCAUTION')
        self.assertIsNone(preceding_context('If the fluid is dirty, change it. Invented addition.', rows))

    def test_repeated_passages_and_missing_geometry_do_not_acquire_context(self):
        self.assertIsNone(preceding_context('Repeated warning.', [
            block('Repeated warning.', page=0), block('Repeated warning.', page=1)]))
        self.assertIsNone(preceding_context('Warning.', [dict(type='text', text='Warning.', page_idx=0)]))

    def test_joint_reranking_preserves_evidence_and_deduplicates(self):
        a, b = record('manual', 'Manual instructions.'), record('guide', 'Guide explanation.', 2)
        duplicate = record('duplicate', 'Manual instructions.', 3)
        contextual = dict(text='Transmission fluid.', pdf_page=2)
        a.metadata['preceding_source_context'] = contextual
        seen = []

        def rerank(question, rows):
            seen.extend(rows)
            return list(reversed(rows))

        with patch('rag.app.retrieval.prose.settings.RAG_RERANK', True), \
                patch('rag.app.retrieval.hybrid.rerank', side_effect=rerank):
            result = select_prose('Question', [a, b, duplicate], 1)
        self.assertEqual(result[0].chunk_id, 'guide')
        self.assertEqual(result[0].text, b.text)
        self.assertEqual(len(seen), 2)
        self.assertIn('Transmission fluid.', seen[0].text)
        packed = prepare_context([a], [])
        self.assertIn('Transmission fluid.', packed.sources[0]['content'])
        self.assertEqual(a.metadata['source_content'], 'Manual instructions.')

    def test_reranker_failure_keeps_available_evidence(self):
        diagnostics = {}
        with patch('rag.app.retrieval.prose.settings.RAG_RERANK', True), \
                patch('rag.app.retrieval.hybrid.rerank', side_effect=RuntimeError('offline')):
            result = select_prose('Question', [record('a', 'A'), record('b', 'B', 2)],
                                  1, diagnostics=diagnostics)
        self.assertEqual(result[0].chunk_id, 'a')
        self.assertEqual(diagnostics['text_reranking'], 'unavailable')

    def test_each_explicit_question_keeps_its_best_evidence(self):
        records = [record('dirty', 'Dirty fluid.'), record('other', 'Other fluid.'),
                   record('tank', 'Shared tank.')]

        def rerank(question, rows):
            return [rows[2], rows[0], rows[1]] if question == 'Separate tanks?' else rows

        with patch('rag.app.retrieval.prose.settings.RAG_RERANK', True), \
                patch('rag.app.retrieval.hybrid.rerank', side_effect=rerank):
            ranked = select_prose('Separate tanks? Dirty fluid?', records, 2)
        self.assertEqual([r.chunk_id for r in ranked], ['dirty', 'tank'])

    def test_short_headings_do_not_hide_a_preceding_subject(self):
        rows = [block('For recommended transmission fluid, see the manual.', y=10)]
        rows += [block(text, y=50+i*35, heading=heading, width=100 if heading else 290)
                 for i, (text, heading) in enumerate([
                     ('Insert dipstick.', False), ('Wipe spilt fluid.', False),
                     ('CAUTION', True), ('If dirty, change the fluid.', False),
                     ('Have the system checked.', False), ('WARNING', True),
                     ('The fluid may be hot.', False)])]
        result = preceding_context('The fluid may be hot.', rows)
        self.assertIn('transmission fluid', result['text'])


if __name__ == '__main__':
    unittest.main()
