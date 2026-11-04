"""Routing and unavailable-media fallbacks, without live dependencies."""
import unittest
from unittest.mock import patch

from rag.app.generation.grounded import GeneratedReply
from rag.app.generation.intent import Intent
from rag.app.query import handle_query, requested_video, ambiguous_fluid_fill
from rag.app.generation.grounded import unrequested_battery_procedure
from shared.safety import immediate_emergency, emergency_guidance


def intent(**values):
    return Intent(question='A resolved question', route='rag', risk='normal',
        specification=False, vehicle_conflict=False, requested_year=None,
        requested_engine=None, requested_variant=None, **values)


SCOPE = dict(scope_type='auto', scope_id='general', label='General assistance',
             document_ids=[], document_metadata={}, video_ids=[], content_sources=[])


class QueryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_unspecified_water_fill_does_not_guess_the_reservoir(self):
        self.assertTrue(ambiguous_fluid_fill('I am scared I might pour water into the wrong place. Which tank should I use?',[]))
        self.assertTrue(ambiguous_fluid_fill('My dad said to check the water in my car. Which water?',[]))
        for question in ['Where do I add windscreen washer fluid?', 'How do I check coolant?',
                         'I already poured water into the wrong tank.', 'What does coolant do?']:
            self.assertFalse(ambiguous_fluid_fill(question,[]),question)
        self.assertFalse(ambiguous_fluid_fill('Where do I add the water?',
            [{'role':'user','content':'How do I refill my windscreen washer?'}]))

    async def test_unspecified_fill_clarifies_without_search_or_model(self):
        with patch('rag.app.query.interpret') as interpret,patch('rag.app.query.retrieve_manual') as search:
            reply=await handle_query('Which tank should I pour water into?',scope=SCOPE)
        self.assertEqual(reply['response_type'],'clarification')
        interpret.assert_not_called();search.assert_not_called()

    def test_malay_active_overheating_has_hot_cap_precaution_without_model(self):
        question = 'Enjin kereta saya terlalu panas sekarang, keluar wap.'
        self.assertTrue(immediate_emergency(question))
        self.assertIn('do not open the radiator', emergency_guidance(question))
        self.assertFalse(immediate_emergency('Kalau enjin terlalu panas, apa saya buat?'))

    def test_unrequested_cable_steps_are_withheld_but_warnings_remain(self):
        self.assertTrue(unrequested_battery_procedure('Disconnect the negative lead from the weak battery.', intent()))
        self.assertFalse(unrequested_battery_procedure('Never disconnect the battery.', intent()))
        self.assertFalse(unrequested_battery_procedure('Inspect the battery for visible damage.', intent()))
    async def test_ambiguous_task_clarifies_before_retrieval_or_generation(self):
        with patch('rag.app.query.interpret', return_value=intent(clarification='Which fluid do you mean?')), \
                patch('rag.app.query.retrieve_manual') as search, \
                patch('rag.app.query.generate') as generate:
            result = await handle_query('Which water?', scope=SCOPE)
        self.assertEqual(result['response_type'], 'clarification')
        self.assertEqual(result['answer'], 'Which fluid do you mean?')
        search.assert_not_called()
        generate.assert_not_called()

    async def test_social_message_does_not_search_the_manuals(self):
        social = intent()
        social.route = 'chat'
        with patch('rag.app.query.interpret', return_value=social), \
                patch('rag.app.query.retrieve_manual') as search, \
                patch('rag.app.query.generate') as generate:
            result = await handle_query('Thanks!', scope=SCOPE)
        self.assertEqual(result['route'], 'chat')
        search.assert_not_called()
        generate.assert_not_called()

    async def test_requested_video_has_honest_fallback_even_if_writer_omits_it(self):
        with patch('rag.app.query.interpret', return_value=intent(instructional=True)), \
                patch('rag.app.query.generate', return_value=GeneratedReply(
                    'Inspect the tread wear bars.', 'answered', has_general_information=True)):
            result = await handle_query('I want to watch someone check the tread.', scope=SCOPE)
        self.assertEqual(result['videos'], [])
        self.assertIn("don't have a matching video", result['answer'])

    def test_picture_requests_do_not_acquire_a_video_limitation(self):
        self.assertFalse(requested_video('Can show picture?'))
        self.assertFalse(requested_video('Text only, no pictures or videos.'))
        self.assertTrue(requested_video('i wan see someone do it'))
        self.assertTrue(requested_video('got video or not?'))
        self.assertTrue(requested_video('Show a tutorial for replacing wiper blades.'))

    async def test_picture_only_request_does_not_search_videos(self):
        resolved=intent(instructional=True)
        resolved.question='How do I inspect tyre tread wear? Show pictures.'
        with patch('rag.app.query.interpret',return_value=resolved), \
                patch('rag.app.query.prepare_retrieval',return_value=[0.0]), \
                patch('rag.app.query.retrieve_youtube') as video_search, \
                patch('rag.app.query.generate',return_value=GeneratedReply('Inspect the tread wear bars.','answered',has_general_information=True)):
            result=await handle_query('How to check tyre wear? Show pictures.',scope={**SCOPE,'video_ids':None})
        video_search.assert_not_called()
        self.assertEqual(result['videos'],[])

    def test_emergency_rendering_preserves_advice_without_diagram_metadata(self):
        from rag.app.retrieval.content import render_emergency
        from rag.app.retrieval.search import RetrievalResult
        text='Never open a hot coolant cap.\n\nDiagram reference: hot engine icon.\n\nContact roadside assistance.'
        record=RetrievalResult(1,'emergency',0,text,dict(title='Overheating',source_content=text,source_reference='internal-file#overheating'))
        rendered=render_emergency([record])
        self.assertIn('Never open a hot coolant cap.',rendered)
        self.assertIn('Contact roadside assistance.',rendered)
        self.assertIn('[S1]',rendered)
        self.assertNotIn('Diagram reference:',rendered)
        self.assertNotIn('internal-file',rendered)


if __name__ == '__main__':
    unittest.main()
