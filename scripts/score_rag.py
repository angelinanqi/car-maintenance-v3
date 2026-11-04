"""Score saved Roadie captures with pinned RAGAS metrics; never regenerate chat.

Use the isolated evaluation Python environment. Run --prepare-only to inspect
sample/metric eligibility without importing RAGAS or contacting a provider.
"""
import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import distributions, version
import inspect
import json
import math
import os
from pathlib import Path
import statistics

from scripts.evaluate_rag import METRICS, atomic_json, digest, local_path

ORDER = ("context_precision", "context_recall", "faithfulness", "factual_correctness", "answer_relevancy")


def prepare_sample(artifact):
    case = artifact["case"]
    capture = artifact["capture"]
    selected = next((a for a in capture["generation_attempts"]
                     if a["id"] == capture["selected_attempt_id"]), None)
    sources = selected.get("packed_context", {}).get("sources", []) if selected else []
    # Pixels and generated visual descriptions are not authoritative text evidence.
    text_sources = [s for s in sources if s.get("content") and not s.get("pixels_supplied")
                    and s.get("content_type", "paragraph") in {"paragraph", "table"}
                    and not s.get("requires_page_images")]
    personal_types = {"personal_vehicle_profile", "personal_maintenance"}
    retrieval = [s for s in text_sources if s.get("document_type") not in personal_types]
    personal = [s for s in sources if s.get("document_type") in personal_types and s.get("content")]

    def render(source):
        # Preserve supplied headings/type along with exact content; never add a reference answer.
        return json.dumps({k: source[k] for k in
            ("title", "source_type", "document_type", "section_path", "content") if k in source}, ensure_ascii=False)

    visual_labels = {s["label"] for s in sources if s.get("pixels_supplied") or s.get("requires_page_images")}
    cited = set(capture.get("generation_result", {}).get("cited_labels", [])) if capture.get("generation_result") else set()
    reasons = {}
    for name in ORDER:
        if name not in case["eligible_metrics"]:
            reasons[name] = "Case uses a behaviour rubric rather than this metric"
        elif artifact["status"] != "captured":
            reasons[name] = "Application capture failed; retained as a system failure"
        elif name in {"context_precision", "context_recall", "faithfulness"} and not retrieval:
            reasons[name] = "No authoritative text context; inspect route/retrieval failure separately"
        elif name == "faithfulness" and cited.intersection(visual_labels):
            reasons[name] = "Answer cites visual evidence unavailable to the text-only judge"
    return {"case_id": case["case_id"], "user_input": artifact["evaluation_input"],
            "retrieved_contexts": [render(s) for s in retrieval],
            "grounding_contexts": [render(s) for s in retrieval + personal],
            "response": artifact.get("reply", {}).get("answer", ""), "reference": case["reference"],
            "not_applicable": reasons, "selected_attempt_id": capture["selected_attempt_id"],
            "text_source_labels": [s["label"] for s in retrieval],
            "visual_source_labels": sorted(visual_labels),
            "response_type": artifact.get("reply", {}).get("response_type"),
            "expected_behavior": case["expected_behavior"],
            "required_facts": case["required_facts"], "prohibited_claims": case["prohibited_claims"]}


def score_summary(rows):
    summary = {}
    for name in ORDER:
        records = [r["metrics"][name] for r in rows]
        values = [r["value"] for r in records if r["status"] == "scored"]
        summary[name] = {"mean": statistics.mean(values) if values else None,
                         "scored": len(values),
                         "errors": sum(r["status"] == "error" for r in records),
                         "not_applicable": sum(r["status"] == "not_applicable" for r in records)}
    return summary


async def run(args, artifacts, samples):
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    from rag.config import settings
    from google import genai
    from google.genai import types
    from ragas.embeddings import GoogleEmbeddings
    from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness, FactualCorrectness, AnswerRelevancy
    from scripts.ragas_gemini import GeminiRagasJudge

    authentication = ({"enterprise": True, "project": settings.GOOGLE_CLOUD_PROJECT,
                       "location": settings.GOOGLE_CLOUD_LOCATION} if settings.GEMINI_USE_CLOUD else
                      {"enterprise": False, "api_key": settings.GEMINI_API_KEY})
    judge = GeminiRagasJudge(model=args.judge_model or settings.GEMINI_MODEL,
                             authentication=authentication, directory=args.output / "judge")
    # Embeddings use generateContent's model endpoint, separate from Interactions.
    embedding_authentication = dict(authentication)
    embedding_location = args.embedding_location
    if settings.GEMINI_USE_CLOUD:
        # Embedding 001 is regional on Cloud, unlike the global Interactions model.
        embedding_location = embedding_location or ("us-central1" if args.embedding_model == "gemini-embedding-001" else "global")
        embedding_authentication["location"] = embedding_location
    embedding_api_version = "v1" if settings.GEMINI_USE_CLOUD else "v1beta"
    embed_client = genai.Client(**embedding_authentication, http_options=types.HttpOptions(
        api_version=embedding_api_version, timeout=60000, retry_options=types.HttpRetryOptions(attempts=2)))
    embedding_cache = args.output / "embedding-cache"
    embedding_cache.mkdir(exist_ok=True)

    class CachedGoogleEmbeddings(GoogleEmbeddings):
        def embed_text(self, text, **kwargs):
            cache_key = sha256(json.dumps([args.embedding_model, embedding_location,
                                           "SEMANTIC_SIMILARITY", text], ensure_ascii=False).encode()).hexdigest()
            path = embedding_cache / (cache_key + ".json")
            if path.exists():
                return json.loads(path.read_text())
            values = super().embed_text(text, **kwargs)
            atomic_json(path, values)
            return values

        def embed_texts(self, texts, **kwargs):
            # Cloud embedding 001 accepts one text per prediction request.
            return [self.embed_text(text, **kwargs) for text in texts]

    embeddings = CachedGoogleEmbeddings(client=embed_client, model=args.embedding_model,
        config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"))
    metrics = {"context_precision": ContextPrecision(llm=judge),
               "context_recall": ContextRecall(llm=judge),
               "faithfulness": Faithfulness(llm=judge),
               "factual_correctness": FactualCorrectness(llm=judge, mode="f1", atomicity="high", coverage="high"),
               "answer_relevancy": AnswerRelevancy(llm=judge, embeddings=embeddings, strictness=3)}
    configuration = {"ragas_version": version("ragas"), "judge": judge.configuration,
        "selected_metrics": args.metrics.split(","),
        "embedding_model": args.embedding_model, "strictness": 3,
        "embedding_location": embedding_location,
        "embedding_api_version": embedding_api_version,
        "embedding_task_type": "SEMANTIC_SIMILARITY", "embedding_batch_size": 1,
        "factual_correctness": {"mode": "f1", "atomicity": "high", "coverage": "high"},
        "scorer_sha256": digest(__file__),
        "metric_source_sha256": {name: digest(inspect.getfile(type(metric))) for name, metric in metrics.items()}}
    inputs = {a["case_id"]: digest(args.run / "cases" / (a["case_id"] + ".json")) for a in artifacts}
    signature = sha256(json.dumps({"config": configuration, "inputs": inputs}, sort_keys=True).encode()).hexdigest()
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text())["signature"] != signature:
        raise ValueError("Scoring inputs/configuration changed; use a new output directory")
    manifest = {"signature": signature, "configuration": configuration,
                "capture_run": str(args.run), "capture_case_sha256": inputs,
                "installed_packages": sorted({f"{d.metadata['Name']}=={d.version}" for d in distributions()}),
                "limitations": ["Five development cases are not a final benchmark",
                    "Judge and generator use the same model when their identifiers match; correlated errors are possible",
                    "Factual correctness measures reference agreement; correct extra details absent from references may be penalised",
                    "Only authoritative text contexts are scored; original image/page evidence requires separate review"],
                "started_at": datetime.now(timezone.utc).isoformat()}
    atomic_json(manifest_path, manifest)
    score_dir = args.output / "cases"
    score_dir.mkdir(exist_ok=True)
    rows = []
    try:
        for sample in samples:
            path = score_dir / (sample["case_id"] + ".json")
            row = json.loads(path.read_text()) if path.exists() else {"case_id": sample["case_id"], "metrics": {}}
            for name in ORDER:
                if name in row["metrics"] and not (args.retry_errors and row["metrics"][name]["status"] == "error"):
                    continue
                if name not in args.metrics.split(","):
                    result = {"status": "not_applicable", "value": None, "reason": "Metric not selected for this diagnostic run"}
                elif name in sample["not_applicable"]:
                    result = {"status": "not_applicable", "value": None, "reason": sample["not_applicable"][name]}
                else:
                    judge.namespace = sample["case_id"] + "/" + name
                    parameters = {"user_input": sample["user_input"], "retrieved_contexts": sample["retrieved_contexts"],
                                  "response": sample["response"], "reference": sample["reference"]}
                    if name == "faithfulness":
                        parameters["retrieved_contexts"] = sample["grounding_contexts"]
                    parameters = {k: v for k, v in parameters.items() if k in inspect.signature(metrics[name].ascore).parameters}
                    try:
                        scored = await asyncio.wait_for(metrics[name].ascore(**parameters), 300)
                        value = float(scored.value)
                        if not math.isfinite(value):
                            raise ValueError("Metric returned an undefined score")
                        result = {"status": "scored", "value": value, "reason": scored.reason}
                    except Exception as error:
                        result = {"status": "error", "value": None, "error_type": type(error).__name__,
                                  "status_code": getattr(error, "status_code", None) or getattr(error, "code", None)}
                row["metrics"][name] = result
                atomic_json(path, row)
                print(json.dumps({"case_id": sample["case_id"], "metric": name, **result}, default=str), flush=True)
            rows.append(row)
            atomic_json(args.output / "summary.json", score_summary(rows))
    finally:
        embed_client.close()
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(manifest_path, manifest)
    atomic_json(args.output / "scores.json", rows)
    return 1 if any(r["status"] == "error" for row in rows for r in row["metrics"].values()) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--judge-model")
    parser.add_argument("--embedding-model", default="gemini-embedding-001")
    parser.add_argument("--embedding-location", help="Cloud embedding region, separate from the global judge endpoint")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--cases", help="Optional comma-separated case IDs for a targeted smoke run")
    parser.add_argument("--metrics", default=",".join(ORDER), help="Optional comma-separated metric names")
    args = parser.parse_args()
    args.run, args.output = local_path(args.run), local_path(args.output)
    if not args.output.is_relative_to(local_path("output")):
        parser.error("Private scoring artifacts must be under output/")
    artifacts = [json.loads(p.read_text()) for p in sorted((args.run / "cases").glob("*.json"))]
    if not set(args.metrics.split(",")).issubset(METRICS):
        parser.error("Unknown metric name")
    if args.cases:
        selected = set(args.cases.split(","))
        if not selected.issubset({a["case_id"] for a in artifacts}):
            parser.error("Unknown case ID")
        artifacts = [a for a in artifacts if a["case_id"] in selected]
    if not artifacts:
        parser.error("No captured cases found")
    samples = [prepare_sample(a) for a in artifacts]
    args.output.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output / "samples.json", samples)
    if args.prepare_only:
        print(json.dumps({"samples": len(samples), "eligible_metric_pairs": sum(len(METRICS) - len(s["not_applicable"]) for s in samples)}))
        return 0
    return asyncio.run(run(args, artifacts, samples))


if __name__ == "__main__":
    raise SystemExit(main())
