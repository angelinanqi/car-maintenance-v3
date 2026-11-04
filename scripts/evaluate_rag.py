"""Capture development evaluation runs; RAGAS judging is a separate next stage.

Validate without loading application dependencies or calling any service:
  python -m scripts.evaluate_rag --dataset <cases.jsonl> --validate-only

Run reviewed cases using the existing app credentials/configuration:
  .venv/bin/python -m scripts.evaluate_rag --dataset <cases.jsonl> --output <new-dir>

Draft smoke cases require --allow-draft. Run in a standalone process, never inside
the application server. Artifacts contain source content and must stay local.
"""
import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import distributions
import json
import os
from pathlib import Path
import re
import shutil
from time import perf_counter

from scripts.evaluation_capture import EvaluationCapture

ROOT = Path(__file__).resolve().parents[1]
METRICS = {"context_precision", "context_recall", "faithfulness",
           "factual_correctness", "answer_relevancy"}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def local_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Evaluation inputs must stay within the project")
    return path


def load_cases(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("Dataset is empty")
    seen = set()
    for row in rows:
        identity = row["case_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identity) or identity in seen:
            raise ValueError("Invalid or duplicate case ID")
        seen.add(identity)
        if row["split"] not in {"development", "test"}:
            raise ValueError(f"{identity}: unsupported evaluation split")
        if not isinstance(row["user_input"], str) or not row["user_input"].strip():
            raise ValueError(f"{identity}: empty question")
        if not isinstance(row["history"], list):
            raise ValueError(f"{identity}: history must be a list")
        if not set(row["eligible_metrics"]).issubset(METRICS):
            raise ValueError(f"{identity}: unknown metric")
        if {"context_precision", "context_recall", "factual_correctness"}.intersection(row["eligible_metrics"]) and not row["reference"]:
            raise ValueError(f"{identity}: reference required")
        scope = json.loads(local_path(row["scope_file"]).read_text())
        if scope["vehicle"]["code"] != row["vehicle_code"]:
            raise ValueError(f"{identity}: wrong vehicle scope")
        for source in row["reference_sources"]:
            for key in ("source_manifest", "chunks", "pdf", "page_image"):
                path_key = "source_manifest" if key == "source_manifest" else key + "_path"
                hash_key = key + "_sha256"
                if path_key in source and digest(local_path(source[path_key])) != source[hash_key]:
                    raise ValueError(f"{identity}: reference artifact changed ({key})")
    return rows


def evaluation_input(case, scope):
    # Stable evaluator context, independent of either model's interpretation.
    vehicle = {key: scope["vehicle"].get(key) for key in
               ("code", "name", "year", "engine", "variant", "powertrain")}
    parts = ["Selected vehicle: " + json.dumps(vehicle, ensure_ascii=False)]
    if case["history"]:
        parts.append("Conversation history: " + json.dumps(case["history"], ensure_ascii=False))
    parts.append("Latest user question: " + case["user_input"])
    return "\n\n".join(parts)


def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


async def run(args, cases):
    # Configure before importing settings; the app configuration respects env overrides.
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
    from rag.config import settings
    from rag.app import query
    from rag.app.generation import grounded
    from rag.app.generation.provider import GenerationClient
    from rag.service import verify_revisions

    out = local_path(args.output)
    if not out.is_relative_to(ROOT / "output"):
        raise ValueError("Store private evaluation artifacts under output/")
    # Fail if the path exists so a rerun never overwrites or mixes conditions.
    out.mkdir(parents=True, exist_ok=False)
    (out / "cases").mkdir()
    shutil.copyfile(args.dataset, out / "dataset.jsonl")
    scope_paths = {row["scope_file"] for row in cases}
    scopes = {}
    for path in sorted(scope_paths):
        scope = json.loads(local_path(path).read_text())
        scope["scope_type"] = "vehicle"
        scopes[path] = verify_revisions(scope, allow_partial=False)
    atomic_json(out / "scopes.json", scopes)
    config_names = (
        "GEMINI_MODEL", "GEMINI_TEMPERATURE", "GEMINI_MAX_OUTPUT_TOKENS",
        "GEMINI_TIMEOUT", "GEMINI_MAX_RETRIES", "EMBEDDING_MODEL", "RERANK_MODEL",
        "RAG_RETRIEVAL_MODE", "RAG_CANDIDATES", "RAG_RRF_K", "RAG_TOP_K",
        "RAG_CONTEXT_CHARS", "RAG_RERANK", "RAG_GROUNDING_REVIEW", "RAG_VISUAL_INPUTS", "RAG_TABLE_PAGE_LIMIT",
    )
    source_hashes = {}
    for directory in ("rag", "shared", "backend", "scripts"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            relative = path.relative_to(ROOT)
            target = out / "source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            source_hashes[str(relative)] = digest(path)
    for path in (ROOT / "requirements.txt", ROOT / "backend/requirements.txt"):
        target = out / "source" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    manifest = {
        "format_version": 1, "condition": args.condition,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": digest(args.dataset),
        "configuration": {name: getattr(settings, name) for name in config_names},
        "source_sha256": source_hashes,
        "installed_packages": sorted({f"{d.metadata['Name']}=={d.version}" for d in distributions()}),
        "scope_file_sha256": {p: digest(local_path(p)) for p in sorted(scope_paths)},
        "scope_status": "saved scopes with strict local revision check; live publication not refreshed",
        "draft_run": any(row["review_status"] != "approved" for row in cases),
        "purpose": "diagnostic development" if all(r["split"] == "development" for r in cases) else "final evaluation",
        "limitations": ["RAG pipeline timing excludes HTTP/mobile rendering",
                        "Token usage is not exposed by the current GenerationClient",
                        "RAGAS scores have not been computed by this capture runner"],
    }
    atomic_json(out / "manifest.json", manifest)
    summary = []
    for case in cases:
        scope = scopes[case["scope_file"]]
        artifact = {"case_id": case["case_id"], "case": case,
                    "evaluation_input": evaluation_input(case, scope), "trace": {}}
        started = perf_counter()
        capture = EvaluationCapture(query, grounded, GenerationClient, asset_dir=out / "assets")
        try:
            with capture:
                artifact["reply"] = await query.handle_query(
                    case["user_input"], scope=scope, history=case["history"],
                    admin_trace=artifact["trace"],
                )
        except Exception as error:
            artifact["error_type"] = type(error).__name__
        artifact["capture"] = capture.artifact()
        artifact["latency_seconds"] = round(perf_counter() - started, 4)
        expected = settings.GEMINI_MODEL.removeprefix("models/")
        artifact["model_mismatch_call_ids"] = [call["id"] for call in capture.calls
            if call.get("response") is not None and call.get("model") != expected]
        reply = artifact.get("reply", {})
        artifact["status"] = (
            "error" if artifact.get("error_type") or artifact["model_mismatch_call_ids"]
            or reply.get("response_type") in {"generation_error", "retrieval_error"} else "captured"
        )
        # Type checks are structural diagnostics, not semantic correctness verdicts.
        artifact["response_type_matches"] = reply.get("response_type") in case["expected_response_types"]
        atomic_json(out / "cases" / (case["case_id"] + ".json"), artifact)
        row = {k: artifact[k] for k in ("case_id", "status", "latency_seconds", "response_type_matches")}
        row["response_type"] = reply.get("response_type")
        summary.append(row)
        atomic_json(out / "summary.json", summary)
        print(json.dumps(row), flush=True)
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(out / "manifest.json", manifest)
    return 1 if any(row["status"] == "error" for row in summary) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output")
    parser.add_argument("--condition", choices=("baseline", "finetuned"), default="baseline")
    parser.add_argument("--model", help="Application model for all LLM calls in this process")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    args.dataset = str(local_path(args.dataset))
    cases = load_cases(args.dataset)
    if args.validate_only:
        print(json.dumps({"valid_cases": len(cases), "dataset_sha256": digest(args.dataset),
                          "unreviewed_cases": sum(c["review_status"] != "approved" for c in cases)}))
        return 0
    if not args.output:
        parser.error("--output is required for a capture run")
    drafts = [c for c in cases if c["review_status"] != "approved"]
    if drafts and (not args.allow_draft or any(c["split"] != "development" for c in cases)):
        parser.error("Unreviewed cases require --allow-draft and development split only")
    return asyncio.run(run(args, cases))


if __name__ == "__main__":
    raise SystemExit(main())
