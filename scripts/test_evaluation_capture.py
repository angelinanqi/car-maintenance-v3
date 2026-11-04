"""Offline checks for correction attribution and non-invasive capture."""
import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from scripts.evaluation_capture import EvaluationCapture
from scripts.evaluate_rag import load_cases


@dataclass
class Reply:
    text: str
    status: str = "answered"


@dataclass
class Context:
    sources: list


class CaptureTests(unittest.TestCase):
    def fixture(self, *, accept_correction=True, fail=False):
        class Provider:
            provider = model = None

            def generate(self, prompt, **kwargs):
                if fail:
                    raise TimeoutError("Simulated private provider error")
                self.provider, self.model = "gemini", "test-model"
                return "raw: " + prompt

        def prepare(records, references):
            return Context([{"label": "S1", "content": "Original evidence"}])

        grounded = SimpleNamespace(prepare_context=prepare)

        def generate(question, records, client, **kwargs):
            context = grounded.prepare_context(records, [])
            client.generate(question, images=[SimpleNamespace(label="I1", data=b"pixels", mime_type="image/png")])
            # Mutating the returned context must not alter its captured snapshot.
            context.sources[0]["content"] = "later mutation"
            if kwargs.get("_validation_feedback"):
                return Reply("Correction")
            original = Reply("Original")
            repaired = grounded.generate(question, records, client, _validation_feedback={"reason": "invalid_citation"})
            return repaired if accept_correction else original

        grounded.generate = generate

        def interpret(question, history, scope, client):
            client.generate("intent")
            return {"question": question, "search_query": "rewritten query"}

        query = SimpleNamespace(generate=generate, interpret=interpret)
        return query, grounded, Provider

    def test_accepted_correction_keeps_selected_evidence_and_restores_functions(self):
        query, grounded, provider = self.fixture()
        original = query.generate
        with TemporaryDirectory() as directory:
            capture = EvaluationCapture(query, grounded, provider, asset_dir=directory)
            async def exercise():
                with capture:
                    client = provider()
                    await asyncio.to_thread(query.interpret, "question", [], {}, client)
                    return await asyncio.to_thread(query.generate, "question", [], client)
            result = asyncio.run(exercise())
            self.assertEqual(result.text, "Correction")
            self.assertEqual(capture.selected_attempt_id, 2)
            self.assertEqual(capture.attempts[0]["returned_attempt_id"], 2)
            self.assertEqual(capture.calls[0]["stage"], "intent_analysis")
            self.assertEqual(capture.calls[2]["attempt_id"], 2)
            self.assertEqual(capture.attempts[1]["packed_context"]["sources"][0]["content"], "Original evidence")
            self.assertEqual((Path(directory) / sha256(b"pixels").hexdigest()).read_bytes(), b"pixels")
        self.assertIs(query.generate, original)
        self.assertIs(grounded.generate, original)

    def test_rejected_correction_does_not_replace_selected_attempt(self):
        query, grounded, provider = self.fixture(accept_correction=False)
        with TemporaryDirectory() as directory:
            with EvaluationCapture(query, grounded, provider, asset_dir=directory) as capture:
                self.assertEqual(query.generate("question", [], provider()).text, "Original")
            self.assertEqual(capture.selected_attempt_id, 1)
            self.assertEqual(len(capture.attempts), 2)

    def test_exception_is_recorded_without_private_error_message_and_patch_is_restored(self):
        query, grounded, provider = self.fixture(fail=True)
        original = query.generate
        with TemporaryDirectory() as directory:
            capture = EvaluationCapture(query, grounded, provider, asset_dir=directory)
            with self.assertRaises(TimeoutError):
                with capture:
                    query.generate("question", [], provider())
            self.assertEqual(capture.calls[0]["error_type"], "TimeoutError")
            self.assertNotIn("Simulated private", str(capture.artifact()))
            self.assertIsNone(capture.selected_attempt_id)
        self.assertIs(query.generate, original)

    def test_path_traversal_case_id_is_rejected_before_loading_scopes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            # Invalid IDs must be rejected before attempting scope/service access.
            path.write_text('{"case_id":"../escape"}\n')
            with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
                load_cases(path)


if __name__ == "__main__":
    unittest.main()
