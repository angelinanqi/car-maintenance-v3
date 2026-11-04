import unittest
from shared.answer_sections import validated_sections

class AnswerSectionsTests(unittest.TestCase):
    def test_text_must_match_fallback_exactly(self):
        self.assertEqual(validated_sections('Original answer', [{'text':'Altered answer'}], []), [])

    def test_unavailable_unknown_and_duplicate_references_cannot_load_assets(self):
        sections=[{'text':'Find the part.', 'reference_labels':['V1','V2','V99','https://bad']},
                  {'text':'Do the check.', 'reference_labels':['V1']}]
        result=validated_sections('Find the part.\n\nDo the check.', sections, [{'reference_label':'V1'}])
        self.assertEqual(result[0]['reference_labels'], ['V1'])
        self.assertEqual(result[1]['reference_labels'], [])
        self.assertEqual('\n\n'.join(s['text'] for s in result), 'Find the part.\n\nDo the check.')

    def test_legacy_and_malformed_layout_use_plain_text(self):
        for sections in (None, [], [{'text':''}], [{'text':'Answer','url':'https://bad'}]):
            self.assertEqual(validated_sections('Answer', sections, []), [])

    def test_revoked_picture_does_not_hide_historical_text(self):
        result=validated_sections('Answer', [{'text':'Answer','reference_labels':['V1']}], [])
        self.assertEqual(result, [{'text':'Answer','reference_labels':[]}])
