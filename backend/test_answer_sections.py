import unittest
from unittest.mock import patch
from backend.services.chat import restore_messages,save_turn
from backend.services.rag_client import ChatAnswer
from rag.service import Answer

class AnswerSectionIntegrationTests(unittest.TestCase):
    def test_http_models_preserve_optional_layout_and_old_replies(self):
        payload=dict(answer='Find it.\n\nCheck it.',answer_sections=[
            {'text':'Find it.','reference_labels':['V1']},{'text':'Check it.','reference_labels':[]}])
        for model in (Answer,ChatAnswer):
            self.assertEqual(model.model_validate(payload).model_dump()['answer_sections'],payload['answer_sections'])
            self.assertEqual(model.model_validate({'answer':'Old reply.'}).answer_sections,[])

    def test_restore_reauthorises_picture_without_rewriting_answer(self):
        message={'id':'m','role':'assistant','content':'Find it.\n\nCheck it.',
                 'reply':{'answer_sections':[{'text':'Find it.','reference_labels':['V1']},
                                            {'text':'Check it.','reference_labels':[]}],
                          'attachment_refs':[{'reference_label':'V1'}]}}
        with patch('backend.services.source_assets.resolve_manual_sources',return_value=([],[])), \
             patch('backend.services.source_assets.attachments',return_value=[{'reference_label':'V1'}]):
            restored=restore_messages([message],{'content_sources':[],'video_ids':[]},'s',{})[0]['reply']
        self.assertEqual(restored['answer_sections'][0]['reference_labels'],['V1'])
        with patch('backend.services.source_assets.resolve_manual_sources',return_value=([],[])), \
             patch('backend.services.source_assets.attachments',return_value=[]):
            withdrawn=restore_messages([message],{'content_sources':[],'video_ids':[]},'s',{})[0]['reply']
        self.assertEqual(withdrawn['answer'],message['content'])
        self.assertEqual(withdrawn['answer_sections'][0]['reference_labels'],[])

    def test_mismatched_saved_sections_cannot_replace_historical_answer(self):
        message={'id':'m','role':'assistant','content':'Original.',
                 'reply':{'answer_sections':[{'text':'Changed.','reference_labels':[]}]}}
        with patch('backend.services.source_assets.resolve_manual_sources',return_value=([],[])):
            reply=restore_messages([message],{'content_sources':[],'video_ids':[]},'s',{})[0]['reply']
        self.assertEqual(reply['answer_sections'],[])
        self.assertEqual(reply['answer'],'Original.')

    def test_save_keeps_placement_labels_and_uses_existing_authorisation_descriptors(self):
        answer={'answer':'Find it.','answer_sections':[{'text':'Find it.','reference_labels':['V1']}],
                'attachments':[{'asset_endpoint':'do-not-store'}]}
        with patch('backend.services.chat.db.client') as client:
            save_turn('s','Question',answer,[{'reference_label':'V1'}])
        rows=client.return_value.table.return_value.insert.call_args.args[0]
        reply=rows[1]['reply']
        self.assertEqual(reply['answer_sections'],answer['answer_sections'])
        self.assertNotIn('attachments',reply)
        self.assertEqual(reply['attachment_refs'],[{'reference_label':'V1'}])
