"""Offline scoring preparation tests; no RAGAS install or API access required."""
import unittest

from scripts.score_rag import ORDER, prepare_sample, score_summary


def artifact():
    return {"case_id": "DEV001", "status": "captured", "evaluation_input": "Question with vehicle",
        "case": {"case_id": "DEV001", "eligible_metrics": list(ORDER), "reference": "Reference answer",
                 "expected_behavior": "answer", "required_facts": [], "prohibited_claims": []},
        "reply": {"answer": "Final validated answer", "response_type": "manual_only"},
        "capture": {"selected_attempt_id": 2, "generation_result": {"cited_labels": ["S2"]},
            "generation_attempts": [
                {"id": 1, "packed_context": {"sources": [{"label": "S1", "content": "Discarded evidence"}]}},
                {"id": 2, "packed_context": {"sources": [
                    {"label": "S2", "content": "Exact supplied evidence", "document_type": "owners_manual", "content_type": "paragraph"},
                    {"label": "I1", "content": "Generated image description", "content_type": "image", "pixels_supplied": True},
                    {"label": "P1", "document_type": "personal_vehicle_profile", "content": "Saved personal vehicle"},
                ]}},
            ]}}


class ScoringPreparationTests(unittest.TestCase):
    def test_only_selected_attempt_sources_are_used_and_reference_is_not_evidence(self):
        sample = prepare_sample(artifact())
        joined = "\n".join(sample["retrieved_contexts"])
        self.assertIn("Exact supplied evidence", joined)
        for excluded in ("Discarded evidence", "Generated image description", "Reference answer", "Saved personal vehicle"):
            self.assertNotIn(excluded, joined)
        self.assertIn("Saved personal vehicle", "\n".join(sample["grounding_contexts"]))
        self.assertEqual(sample["response"], "Final validated answer")

    def test_cited_pixels_make_text_faithfulness_inapplicable(self):
        data = artifact()
        data["capture"]["generation_result"]["cited_labels"] = ["I1"]
        sample = prepare_sample(data)
        self.assertIn("faithfulness", sample["not_applicable"])
        self.assertNotIn("factual_correctness", sample["not_applicable"])

    def test_application_failure_remains_error_coverage_not_zero_scores(self):
        data = artifact()
        data["status"] = "error"
        self.assertEqual(set(prepare_sample(data)["not_applicable"]), set(ORDER))

    def test_undefined_and_missing_metrics_do_not_enter_mean(self):
        records = []
        for state, value in [("scored", 0.8), ("error", None), ("not_applicable", None)]:
            records.append({"metrics": {name: {"status": state, "value": value} for name in ORDER}})
        summary = score_summary(records)
        for result in summary.values():
            self.assertEqual(result, {"mean": 0.8, "scored": 1, "errors": 1, "not_applicable": 1})


if __name__ == "__main__":
    unittest.main()
