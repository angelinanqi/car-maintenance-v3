"""Exercise capture against real context packing/correction, with no API calls.

Run with .venv/bin/python -m unittest scripts.test_evaluation_capture_integration.
"""
import asyncio
import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from rag.app import query
from rag.app.generation import grounded
from rag.app.generation.provider import GenerationClient
from rag.app.retrieval.search import RetrievalResult
from scripts.evaluation_capture import EvaluationCapture


class RealGenerationCaptureTests(unittest.TestCase):
    def test_actual_correction_selects_matching_context_and_preserves_validated_answer(self):
        record = RetrievalResult(1, "washer", 0, "The washer tank is shared.",
            {"document_name": "manual", "content_type": "paragraph",
             "source_type": "manual", "document_type": "owners_manual",
             "source_fidelity_verified": True})
        responses = iter([
            {"text": "The washer tank is shared.", "basis": "source", "sources": [],
             "table_context_sufficient": False},
            {"text": "The washer tank is shared.", "basis": "source", "sources": ["S1"],
             "table_context_sufficient": False},
        ])

        def fake_call(client, prompt, **options):
            client.provider, client.model = "gemini", "fake-offline-model"
            return json.dumps({"outcome": "answer", "blocks": [next(responses)],
                               "references": [], "recommended_guides": [],
                               "recommended_videos": [], "clarification": None})

        with TemporaryDirectory() as directory, patch.object(GenerationClient, "generate", fake_call), \
                patch('rag.app.generation.grounded.settings.RAG_GROUNDING_REVIEW', False):
            with EvaluationCapture(query, grounded, GenerationClient, asset_dir=directory) as capture:
                reply = asyncio.run(asyncio.to_thread(query.generate,
                    "Does it use a shared washer tank?", [record], GenerationClient(),
                    scope={"label": "Test"}, risk="normal"))
            self.assertEqual(reply.status, "answered")
            self.assertIn("The washer tank is shared.", reply.text)
            self.assertEqual(capture.selected_attempt_id, 2)
            self.assertEqual(len(capture.calls), 2)
            attempt = capture.attempts[1]
            supplied = attempt["packed_context"]["sources"]
            payload = json.loads(capture.calls[1]["prompt"].split("\nInput:\n", 1)[1])
            self.assertEqual(supplied, payload["sources"])
            self.assertEqual(supplied[0]["content"], "The washer tank is shared.")
            self.assertEqual(capture.generation_result["text"], reply.text)

    def test_review_uses_captured_evidence_and_same_provider_then_validates_result(self):
        record = RetrievalResult(1, 'oil', 0, 'Park on level ground and wait more than five minutes.',
            dict(document_name='manual', content_type='paragraph', source_type='manual',
                 document_type='owners_manual'))
        draft = dict(outcome='answer', blocks=[dict(text='Wait more than five minutes. This prevents overfilling.',
            basis='source', sources=['S1'], table_context_sufficient=False)], references=[], clarification=None)
        reviewed = {**draft, 'blocks': [{**draft['blocks'][0],
            'text': 'Park on level ground and wait more than five minutes.'}]}
        responses = iter([draft, dict(evidence_checklist=[
            'S1: Include level-ground preparation and waiting. Remove unsupported overfilling explanation.'],
            answer=reviewed)])

        def fake_call(client, prompt, **options):
            client.provider, client.model = 'gemini', 'same-configured-model'
            return json.dumps(next(responses))

        with TemporaryDirectory() as directory, patch.object(GenerationClient, 'generate', fake_call), \
                patch('rag.app.generation.grounded.settings.RAG_GROUNDING_REVIEW', True):
            with EvaluationCapture(query, grounded, GenerationClient, asset_dir=directory) as capture:
                reply = grounded.generate('When can I check?', [record], GenerationClient(),
                    scope={'label': 'Test'}, risk='normal')
        self.assertNotIn('overfilling', reply.text)
        self.assertIn('level ground', reply.text)
        self.assertEqual(reply.cited_labels, ['S1'])
        self.assertEqual(len(capture.calls), 2)
        self.assertEqual({call['model'] for call in capture.calls}, {'same-configured-model'})
        evidence = capture.attempts[0]['packed_context']['sources'][0]['content']
        self.assertIn(evidence, capture.calls[1]['prompt'])
        self.assertEqual(capture.generation_result['text'], reply.text)


if __name__ == "__main__":
    unittest.main()
