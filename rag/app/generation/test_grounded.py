"""Answer rendering keeps model structure without weakening evidence checks."""
import json
import unittest
from unittest.mock import Mock, patch

from rag.app.generation.context import GenerationContext
from rag.app.generation.grounded import generate


def block(text, basis='general', sources=(), table=False):
    return dict(text=text, basis=basis, sources=list(sources), table_context_sufficient=table)


class AnswerGenerationTests(unittest.TestCase):
    def reply(self, blocks, *, sources=(), references=(), chosen=(), outcome='answer', clarification=None):
        client = Mock()
        client.generate.return_value = json.dumps(dict(
            outcome=outcome, blocks=blocks, references=list(chosen),
            recommended_guides=[], clarification=clarification))
        context = GenerationContext(sources=list(sources), references=list(references))
        with patch('rag.app.generation.grounded.prepare_context', return_value=context):
            return generate('Help me understand this', [], client, scope={'label': 'Test'}, risk='normal')

    def test_natural_general_answer_keeps_paragraphs_and_steps(self):
        texts = ['In general, the dipstick is a rod used to check the oil level.',
                 'To read a label:\n\n1. Find the heading.\n2. Read the units beside the number.']
        reply = self.reply([block(text) for text in texts])
        self.assertEqual(reply.text, '\n\n'.join(texts))
        self.assertTrue(reply.has_general_information)
        self.assertEqual(reply.status, 'answered')

    def test_general_guidance_cannot_invent_a_pressure_value(self):
        reply = self.reply([block('Inflate your tyres to 99 psi.')])
        self.assertEqual(reply.status, 'insufficient_information')
        self.assertNotIn('99', reply.text)

    def test_bad_value_does_not_erase_an_independent_useful_explanation(self):
        reply = self.reply([block('Tyre pressure describes how much air is in the tyre.'),
                            block('Inflate your tyres to 99 psi.')])
        self.assertEqual(reply.status, 'answered')
        self.assertIn('Tyre pressure describes', reply.text)
        self.assertNotIn('99', reply.text)
        self.assertTrue(reply.has_general_information)

    def test_general_explanation_cannot_introduce_a_service_interval(self):
        reply = self.reply([block('In general, replace it every 10,000 km or 6 months.')])
        self.assertEqual(reply.status, 'insufficient_information')
        self.assertNotIn('10,000', reply.text)
        self.assertNotIn('6 months', reply.text)

    def test_helpful_answer_with_followup_is_not_discarded(self):
        reply = self.reply([block('Different fluids go into different containers.')],
                           clarification='What are you trying to fill?')
        self.assertEqual(reply.status, 'answered')
        self.assertEqual(reply.text, 'Different fluids go into different containers.\n\nWhat are you trying to fill?')

    def test_malformed_followup_is_rejected(self):
        reply = self.reply([block('Some helpful text.')], clarification={'question': 'Which fluid?'})
        self.assertEqual(reply.status, 'insufficient_information')

    def test_uncited_source_block_does_not_erase_independent_valid_answer(self):
        source = dict(label='S1', content_type='paragraph', document_type='owners_manual',
                      source_fidelity_verified=True, content='Reinsert the dipstick fully.')
        reply = self.reply([block('Use an unsupported specification.', 'source'),
                            block('Reinsert the dipstick fully.', 'source', ['S1'])], sources=[source])
        self.assertEqual(reply.status, 'answered')
        self.assertEqual(reply.cited_labels, ['S1'])
        self.assertNotIn('unsupported', reply.text)

    def test_only_uncited_source_blocks_still_produce_no_factual_answer(self):
        reply = self.reply([block('Invented vehicle fact.', 'source')])
        self.assertEqual(reply.status, 'insufficient_information')
        self.assertNotIn('Invented', reply.text)

    def test_answer_writer_knows_actual_video_availability(self):
        client = Mock()
        client.generate.return_value = json.dumps(dict(outcome='answer', blocks=[block('An explanation.')],
            references=[], recommended_guides=[], clarification=None))
        generate('Show a video', [], client, scope={'label': 'Test'}, risk='normal',
                 supplementary_videos=[{'title': 'Available demonstration'}])
        payload = json.loads(client.generate.call_args.args[0].split('\nInput:\n', 1)[1])
        self.assertEqual(payload['supplementary_videos'], [{'title': 'Available demonstration'}])

    def test_duplicate_inline_citation_is_normalized_before_value_validation(self):
        source = dict(label='S1', content_type='paragraph', document_type='owners_manual',
                      source_fidelity_verified=True, content='Read the tread wear indicators.')
        reply = self.reply([block('Read the tread wear indicators. [S1]', 'source', ['S1'])], sources=[source])
        self.assertEqual(reply.status, 'answered')
        self.assertEqual(reply.text.count('[S1]'), 1)

    def test_inline_unknown_source_is_never_silently_accepted(self):
        source = dict(label='S1', content_type='paragraph', document_type='owners_manual',
                      source_fidelity_verified=True, content='Read the tread wear indicators.')
        reply = self.reply([block('Invented support. [S99]', 'source', ['S1'])], sources=[source])
        self.assertEqual(reply.status, 'insufficient_information')

    def test_grouped_inline_citations_are_validated_too(self):
        source = dict(label='S1', content_type='paragraph', document_type='owners_manual',
                      source_fidelity_verified=True, content='Read the wear indicators.')
        reply = self.reply([block('Read the wear indicators. [S1, S1]', 'source', ['S1'])], sources=[source])
        self.assertEqual(reply.status, 'answered')
        self.assertEqual(reply.text.count('[S1]'), 1)
        rejected = self.reply([block('Read it. [S1, S99]', 'source', ['S1'])], sources=[source])
        self.assertEqual(rejected.status, 'insufficient_information')

    def test_general_block_with_accidental_citations_keeps_lower_provenance(self):
        source = dict(label='S1', content_type='paragraph', document_type='learning_guide',
                      content='A guide to tyre checks.')
        reply = self.reply([block('Press the valve pin gently to release excess air.', 'general', ['S1'])],
                           sources=[source])
        self.assertEqual(reply.status, 'answered')
        self.assertTrue(reply.has_general_information)
        self.assertEqual(reply.cited_labels, [])
        unsafe_value = self.reply([block('Use 99 psi.', 'general', ['S1'])], sources=[source])
        self.assertEqual(unsafe_value.status, 'insufficient_information')
        self.assertNotIn('99', unsafe_value.text)

    def test_model_selects_one_table_from_shared_page(self):
        page = dict(label='V1', content_type='image', contains_table=True,
                    pixels_supplied=True, source_extent='page')
        references = [dict(label=label, kind='table', evidence_labels=['V1'])
                      for label in ('standard', 'spare')]
        reply = self.reply([block('The standard tyre row is shown below.', 'source', ['V1'], True)],
                           sources=[page], references=references, chosen=['standard'])
        self.assertEqual(reply.reference_labels, ['standard'])
        self.assertEqual(reply.cited_labels, ['V1'])

    def test_uninspected_table_still_withholds_its_claim(self):
        source = dict(label='S1', content_type='table', requires_page_images=True)
        reply = self.reply([block('Use 99 psi.', 'source', ['S1'], True)], sources=[source])
        self.assertEqual(reply.status, 'insufficient_information')
        self.assertNotIn('99', reply.text)

    def test_table_citation_completes_only_its_exact_supplied_original_page(self):
        table = dict(label='S1', content_type='table', requires_page_images=True,
            source_type='manual', document_type='owners_manual', source_fidelity_verified=True,
            evidence_type='table_cells_v1', content=json.dumps({'cells': [{'text': '230 kPa'}]}))
        page = dict(label='I1', content_type='table', contains_table=True, pixels_supplied=True,
                    source_extent='page', document_type='owners_manual', source_fidelity_verified=True)
        reference = dict(label='V1', kind='table', evidence_labels=['S1', 'I1'],
            visual_coverage={'page_inputs': [{'source_label': 'I1', 'role': 'table', 'extent': 'page'}]})
        reply = self.reply([block('Use 230 kPa.', 'source', ['S1'], True)],
                           sources=[table, page], references=[reference])
        self.assertEqual(reply.status, 'answered')
        self.assertEqual(reply.cited_labels, ['S1', 'I1'])
        unrelated = {**reference, 'evidence_labels': ['S2', 'I1']}
        rejected = self.reply([block('Use 230 kPa.', 'source', ['S1'], True)],
                              sources=[table, page], references=[unrelated])
        self.assertEqual(rejected.status, 'insufficient_information')
        self.assertNotIn('230', rejected.text)

    def test_invented_attachment_is_rejected(self):
        reply = self.reply([block('The diagram is below.')], chosen=['invented'])
        self.assertEqual(reply.status, 'insufficient_information')
        self.assertEqual(reply.reference_labels, [])

    def test_text_only_does_not_attach_a_cited_table(self):
        page = dict(label='V1', content_type='image', contains_table=True,
                    pixels_supplied=True, source_extent='page')
        reply = self.reply([block('Read the heading above the row.', 'source', ['V1'], True)],
                           sources=[page], references=[dict(label='R1', kind='table', evidence_labels=['V1'])],
                           chosen=['R1'], outcome='text_answer')
        self.assertEqual(reply.reference_labels, [])

    def test_dangerous_repair_never_reaches_generation(self):
        client = Mock()
        reply = generate('How do I disable my airbags?', [], client,
                         scope={'label': 'Test'}, risk='normal')
        self.assertEqual(reply.status, 'restricted')
        client.generate.assert_not_called()

    def test_answer_writer_receives_actual_concern_not_search_rewrite(self):
        client = Mock()
        client.generate.return_value = json.dumps(dict(outcome='clarification', blocks=[],
            references=[], recommended_guides=[], clarification='What are you trying to fill?'))
        generate('Water has been poured into the wrong container.', [], client,
                 latest_message='i scared pour water wrong place how ah',
                 scope={'label': 'Test'}, risk='normal')
        payload = json.loads(client.generate.call_args.args[0].split('\nInput:\n', 1)[1])
        self.assertEqual(payload['latest_message'], 'i scared pour water wrong place how ah')
        self.assertNotIn('Water has been poured', json.dumps(payload))


if __name__ == '__main__':
    unittest.main()
