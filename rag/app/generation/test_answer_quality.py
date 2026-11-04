import json,unittest
from unittest.mock import Mock,patch
from rag.app.generation.context import GenerationContext
from rag.app.generation.grounded import generate, engine_bay_direction
from rag.app.generation.intent import Intent
from shared.safety import policy_risk,enforce_policy


def block(text, basis='general', sources=None, references=None, table=False):
    return dict(text=text,basis=basis,sources=sources or [],references=references or [],table_context_sufficient=table)

class AnswerQualityTests(unittest.TestCase):
    def test_direction_filter_distinguishes_locations_from_ordinary_left_and_right(self):
        for text in ['The battery may not have enough electrical power left.',
                     'You may have left the lights on and drained the battery.',
                     'A weak battery may click. The right next step is an inspection.']:
            self.assertFalse(engine_bay_direction(text),text)
        for text in ['The battery is on the left of the engine bay.',
                     'Find the dipstick on the right side.',
                     'The washer reservoir is in the upper-left corner.',
                     "The battery is on the passenger's side."]:
            self.assertTrue(engine_bay_direction(text),text)

    def test_starting_explanation_survives_power_left_wording(self):
        reply=self.reply([block('The battery may not have enough electrical power left to start the engine.')])
        self.assertEqual(reply.status,'answered')
        self.assertIn('power left',reply.text)
        self.assertNotIn('left/right',reply.text)

    def reply(self,blocks,*,sources=None,references=None,chosen=None,outcome='answer'):
        client=Mock();client.generate.return_value=json.dumps(dict(outcome=outcome,blocks=blocks,
            references=chosen or [],recommended_guides=[],recommended_videos=[],clarification=None))
        context=GenerationContext(sources=sources or [],references=references or [])
        with patch('rag.app.generation.grounded.prepare_context',return_value=context):
            return generate('Help me understand this',[],client,scope={'label':'Test'},risk='normal')

    def test_validated_text_and_placement_stay_together(self):
        reply=self.reply([block('**Find the part**',references=['V1']),block('Then follow the check.')],
                         references=[{'label':'V1'}],chosen=['V1'])
        self.assertEqual(reply.answer_sections[0]['reference_labels'],['V1'])
        self.assertEqual('\n\n'.join(s['text'] for s in reply.answer_sections),reply.text)

    def test_rejected_numeric_block_cannot_place_picture_or_erase_general_explanation(self):
        reply=self.reply([block('Too much pressure can affect tyre grip.'),
                          block('Inflate to 99 psi.',references=['V1'])],references=[{'label':'V1'}],chosen=['V1'])
        self.assertEqual(reply.status,'answered')
        self.assertIn('affect tyre grip',reply.text)
        self.assertNotIn('99',reply.text)
        self.assertFalse(any(s['reference_labels'] for s in reply.answer_sections))

    def test_unknown_unselected_and_duplicate_placement_ids_are_ignored(self):
        reply=self.reply([block('First.',references=['V99','V2','V1','V1']),block('Second.',references=['V1'])],
                         references=[{'label':'V1'},{'label':'V2'}],chosen=['V1'])
        self.assertEqual([s['reference_labels'] for s in reply.answer_sections],[['V1'],[]])

    def test_text_only_preserves_prose_without_picture_placement(self):
        reply=self.reply([block('Read the label.',references=['V1'])],references=[{'label':'V1'}],chosen=['V1'],outcome='text_answer')
        self.assertEqual(reply.reference_labels,[])
        self.assertEqual(reply.answer_sections[0]['reference_labels'],[])

    def test_guessed_engine_bay_side_is_withheld_without_erasing_independent_steps(self):
        reply=self.reply([block('The dipstick is on the left side of the engine compartment.'),
                          block('Park on a level surface before checking the oil.')])
        self.assertNotIn('is on the left',reply.text)
        self.assertIn('Park on a level surface',reply.text)
        self.assertIn('original illustration',reply.text)

    def test_missing_table_context_does_not_erase_separate_general_advice(self):
        source=dict(label='S1',content_type='table',content='230 kPa',requires_page_images=True)
        reply=self.reply([block('Check the pressure again after releasing a little air.'),
                          block('Use 230 kPa.','source',['S1'])],sources=[source])
        self.assertEqual(reply.status,'answered')
        self.assertIn('Check the pressure again',reply.text)
        self.assertNotIn('230',reply.text)

    def test_education_is_allowed_but_procedural_and_mixed_requests_remain_restricted(self):
        question='What is an airbag and why should I not repair it myself?'
        self.assertEqual(policy_risk(question),'normal')
        intent=Intent(question=question,route='restricted',risk='high_risk',instructional=False,
                      specification=False,vehicle_conflict=False,requested_year=None,requested_engine=None,requested_variant=None)
        self.assertEqual(enforce_policy(intent).route,'rag')
        for question in ['Explain step by step how to replace the airbag myself.',
                         'What is an airbag, and how do I remove and replace mine?',
                         'Why should I not repair the airbag? Show me how to bypass it.',
                         'Tell me how to bleed the brake hydraulic system myself.']:
            self.assertEqual(policy_risk(question),'high_risk',question)

class BoundedCorrectionTests(unittest.TestCase):
    def draft(self,blocks):
        return json.dumps(dict(outcome='answer',blocks=blocks,references=[],recommended_guides=[],recommended_videos=[],clarification=None))

    def test_uncited_identification_gets_one_correction_without_promoting_claim(self):
        from rag.app.retrieval.search import RetrievalResult
        record=RetrievalResult(1,'washer',0,'The washer cap has a windscreen spray symbol.',
                              dict(document_name='Manual',content_type='paragraph'))
        client=Mock();client.generate.side_effect=[self.draft([
            block('The washer cap has a windscreen spray symbol.','source'),
            block('Use suitable washer fluid.')]),self.draft([
            block('The washer cap has a windscreen spray symbol.','source',['S1']),
            block('Use suitable washer fluid.')])]
        diagnostics={}
        reply=generate('Where do I fill washer fluid?',[record],client,scope={'label':'Test'},risk='normal',diagnostics=diagnostics)
        self.assertEqual(client.generate.call_count,2)
        self.assertIn('windscreen spray symbol',reply.text)
        self.assertEqual(reply.cited_labels,['S1'])
        self.assertEqual(diagnostics['correction_result'],'accepted')

    def test_empty_optional_block_does_not_cause_correction(self):
        client=Mock();client.generate.return_value=self.draft([block('','source'),block('Use suitable washer fluid.')])
        reply=generate('Explain washer fluid.',[],client,scope={'label':'Test'},risk='normal')
        self.assertEqual(client.generate.call_count,1)
        self.assertEqual(reply.status,'answered')

    def test_correction_preserves_real_table_and_original_image_bindings(self):
        from rag.app.retrieval.search import RetrievalResult
        from rag.app.generation.visual import ImageInput
        from shared.table_evidence import table_fragments
        element=dict(element_id='table-00001',kind='table',structure_valid=True,caption='Cold pressure',notes=[],
            cells=[dict(row=0,column=0,rowspan=1,colspan=1,header=True,text='kPa'),
                   dict(row=1,column=0,rowspan=1,colspan=1,header=False,text='230')])
        record=RetrievalResult(1,'table',0,json.dumps(table_fragments(element)[0]),dict(
            document_name='manual',element_id=element['element_id'],content_type='table',
            evidence_type='table_cells_v1',structure_valid=True,source_type='manual',
            document_type='owners_manual',source_fidelity_verified=True))
        references=[dict(label='V1',kind='table',document_name='manual',element_id=element['element_id'],
            table_element=element,pixel_source_labels=['I1'],requires_page_images=True,
            visual_coverage={'page_inputs':[dict(source_label='I1',role='table',extent='page')]})]
        pixels=[dict(label='I1',content_type='image',content='Original page',pixels_supplied=True,
            source_extent='page',contains_table=True,source_type='manual',document_type='owners_manual',
            source_fidelity_verified=True)]
        images=[ImageInput('I1',b'original pixels','image/png')]
        client=Mock();client.generate.side_effect=[self.draft([block('Use 99 psi.')]),
            self.draft([block('Use 230 kPa.','source',['S1'],table=True)])]
        diagnostics={}
        reply=generate('What is the cold pressure?',[record],client,scope={'label':'Test'},risk='normal',
            references=references,images=images,image_sources=pixels,diagnostics=diagnostics)
        self.assertEqual(client.generate.call_count,2)
        first,second=[json.loads(c.args[0].split('\nInput:\n',1)[1]) for c in client.generate.call_args_list]
        self.assertEqual(first['sources'],second['sources'])
        self.assertEqual(first['references'],second['references'])
        self.assertEqual(second['references'][0]['evidence_labels'],['I1','S1'])
        self.assertEqual(second['references'][0]['visual_coverage']['page_inputs'][0]['source_label'],'I1')
        self.assertEqual(client.generate.call_args.kwargs['images'],images)
        self.assertEqual(references[0]['pixel_source_labels'],['I1'])
        self.assertEqual(diagnostics['correction_result'],'accepted')
        self.assertIn('230 kPa',reply.text)

    def test_one_correction_can_recover_general_guidance_without_inventing_value(self):
        client=Mock();client.generate.side_effect=[self.draft([block('Inflate to 99 psi.')]),
            self.draft([block('Release a little air and check the gauge again. Calibrate against the tyre label.')])]
        diagnostics={}
        reply=generate('What if I put too much air?',[],client,scope={'label':'Test'},risk='normal',diagnostics=diagnostics)
        self.assertEqual(reply.status,'answered')
        self.assertNotIn('99',reply.text)
        self.assertEqual(client.generate.call_count,2)
        self.assertEqual(diagnostics['correction_result'],'accepted')
        payload=json.loads(client.generate.call_args.args[0].split('\nInput:\n',1)[1])
        self.assertEqual(payload['validation_feedback'],{'reason':'unverified_values'})
        self.assertEqual(payload['sources'],[])

    def test_failed_correction_is_bounded_and_retains_independent_valid_answer(self):
        client=Mock();client.generate.return_value=self.draft([
            block('Tyre pressure affects how the car handles.'),block('Inflate to 99 psi.')])
        diagnostics={}
        reply=generate('Explain tyre pressure.',[],client,scope={'label':'Test'},risk='normal',diagnostics=diagnostics)
        self.assertEqual(client.generate.call_count,2)
        self.assertIn('affects how the car handles',reply.text)
        self.assertNotIn('99',reply.text)
        self.assertEqual(diagnostics['correction_result'],'original_retained')

    def test_correction_failure_does_not_turn_good_partial_answer_into_service_error(self):
        client=Mock();client.generate.side_effect=[self.draft([
            block('Tyre pressure affects handling.'),block('Inflate to 99 psi.')]),RuntimeError('provider unavailable')]
        reply=generate('Explain tyre pressure.',[],client,scope={'label':'Test'},risk='normal')
        self.assertEqual(reply.status,'answered')
        self.assertIn('affects handling',reply.text)
        self.assertEqual(client.generate.call_count,2)

    def test_educational_schema_keeps_repair_refusal_for_other_requests(self):
        from rag.app.generation.grounded import answer_schema
        from shared.safety import educational_only
        self.assertNotIn('restricted',answer_schema([],education=True)['properties']['outcome']['enum'])
        self.assertIn('restricted',answer_schema([])['properties']['outcome']['enum'])
        self.assertFalse(educational_only('What is the easiest way to take out an airbag?'))
        self.assertFalse(educational_only('Why should I not repair it? What is the method to detach the airbag?'))
