"""Judge transport regression tests in the isolated RAGAS environment."""
import asyncio
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
from pydantic import BaseModel
from scripts.ragas_gemini import GeminiRagasJudge, SYSTEM


class Verdict(BaseModel):
    verdict: int


class JudgeTransportTests(unittest.TestCase):
    def test_output_text_property_is_used_with_neutral_system_prompt(self):
        calls = []
        async def create(**options):
            calls.append(options)
            # No .outputs attribute: matches the current Interactions response API.
            return SimpleNamespace(status="completed", output_text='{"verdict": 1}', usage=None)

        class AsyncClient:
            interactions = SimpleNamespace(create=create)
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False

        class Client:
            aio = AsyncClient()
            def __enter__(self): return self
            def __exit__(self, *args): return False

        with TemporaryDirectory() as directory, patch("scripts.ragas_gemini.genai.Client", return_value=Client()):
            judge = GeminiRagasJudge(model="offline-test", authentication={}, directory=directory)
            result = asyncio.run(judge.agenerate("Evaluate this evidence", Verdict))
            self.assertEqual(result.verdict, 1)
            self.assertEqual(calls[0]["system_instruction"], SYSTEM)
            self.assertFalse(calls[0]["store"])

    def test_repeated_relevance_prompts_are_separate_cached_samples(self):
        with TemporaryDirectory() as directory:
            async def exercise():
                judge = GeminiRagasJudge(model="offline-test", authentication={}, directory=directory)
                judge._request = AsyncMock(side_effect=[('{"verdict":1}', None), ('{"verdict":0}', None)])
                self.assertEqual((await judge.agenerate("Same prompt", Verdict)).verdict, 1)
                self.assertEqual((await judge.agenerate("Same prompt", Verdict)).verdict, 0)
                self.assertEqual(judge._request.await_count, 2)
                resumed = GeminiRagasJudge(model="offline-test", authentication={}, directory=directory)
                resumed._request = AsyncMock(side_effect=AssertionError("Cache should be used"))
                self.assertEqual((await resumed.agenerate("Same prompt", Verdict)).verdict, 1)
                self.assertEqual((await resumed.agenerate("Same prompt", Verdict)).verdict, 0)
                self.assertEqual(resumed._request.await_count, 0)
            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
