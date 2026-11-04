"""Capture frozen pipeline variants on the same fresh development questions.

Each variant runs in its own process and imports only its saved application
snapshot. Corpus paths and credentials point to the existing local environment;
no application code, database rows, prepared indexes or references are changed.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import importlib
from importlib.metadata import distributions
import json
import os
from pathlib import Path
import random
import shutil
import sys
from time import perf_counter

from scripts.evaluate_rag import ROOT, atomic_json, digest, load_cases, local_path, evaluation_input
from scripts.evaluation_capture import EvaluationCapture

ROOT_OUTPUT = ROOT / 'output/evaluations/ragas-fresh-validation-01'
DATASET = ROOT_OUTPUT / 'preparation/fresh-development-v1.jsonl'
SNAPSHOTS = {
    'original': ROOT / 'output/evaluations/ragas/development-baseline-02',
    'improved_no_review': ROOT / 'output/evaluations/ragas/development-pipeline-fixes-05',
    'improved_full': ROOT / 'output/evaluations/ragas/development-pipeline-fixes-05',
}


def prepare_runtime(variant, run_dir):
    # Resolve main-project settings before importing any snapshot application.
    from shared.configuration import load_configuration
    load_configuration()
    for name, default in [('OUTPUT_DIR', 'output'), ('CHROMA_PATH', 'output/embeddings/chroma'),
                          ('YOUTUBE_OUTPUT_DIR', 'output/youtube')]:
        path = Path(os.getenv(name) or default).expanduser()
        os.environ[name] = str(path if path.is_absolute() else ROOT / path)
    credential_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if credential_path and not Path(credential_path).is_absolute():
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(ROOT / credential_path)
    os.environ['MONITOR_ENABLED'] = '0'
    os.environ['RAG_GROUNDING_REVIEW'] = 'true' if variant == 'improved_full' else 'false'
    snapshot = SNAPSHOTS[variant]
    expected = json.loads((snapshot / 'manifest.json').read_text())
    pipeline = run_dir / 'pipeline'
    if not pipeline.exists():
        pipeline.mkdir()
        for package in ['rag', 'shared', 'backend']:
            shutil.copytree(snapshot / 'source' / package, pipeline / package)
        shutil.copyfile(ROOT / 'app.config.json', pipeline / 'app.config.json')
    hashes = {}
    for package in ['rag', 'shared', 'backend']:
        for path in sorted((pipeline / package).rglob('*.py')):
            name = str(path.relative_to(pipeline))
            value = digest(path)
            if expected['source_sha256'].get(name) != value:
                raise ValueError(f'Frozen pipeline differs from saved capture: {name}')
            hashes[name] = value
    # The current runner/capture helpers stay loaded. Reset application contracts
    # and configuration so every application import comes from the chosen snapshot.
    for name in list(sys.modules):
        if name == 'shared' or name.startswith('shared.'):
            del sys.modules[name]
    sys.path.insert(0, str(pipeline))
    importlib.invalidate_caches()
    return snapshot, pipeline, hashes


async def capture(args):
    cases = load_cases(DATASET)
    run_dir = ROOT_OUTPUT / args.variant
    if run_dir.exists() and not args.resume:
        raise ValueError('Existing run requires explicit --resume')
    run_dir.mkdir(parents=True, exist_ok=args.resume)
    (run_dir / 'cases').mkdir(exist_ok=True)
    origin, pipeline, hashes = prepare_runtime(args.variant, run_dir)
    from rag.config import settings
    from rag.app import query
    from rag.app.generation import grounded
    from rag.app.generation.provider import GenerationClient
    from rag.service import verify_revisions
    if not Path(query.__file__).is_relative_to(pipeline):
        raise ValueError('Application did not load from frozen snapshot')
    scopes = {}
    for path in sorted({case['scope_file'] for case in cases}):
        scope = json.loads(local_path(path).read_text())
        scope['scope_type'] = 'vehicle'
        scopes[path] = verify_revisions(scope, allow_partial=False)
    config_names = ['GEMINI_MODEL', 'GEMINI_TEMPERATURE', 'GEMINI_MAX_OUTPUT_TOKENS',
        'GEMINI_TIMEOUT', 'GEMINI_MAX_RETRIES', 'EMBEDDING_MODEL', 'RERANK_MODEL',
        'RAG_RETRIEVAL_MODE', 'RAG_CANDIDATES', 'RAG_RRF_K', 'RAG_TOP_K',
        'RAG_CONTEXT_CHARS', 'RAG_RERANK', 'RAG_VISUAL_INPUTS', 'RAG_TABLE_PAGE_LIMIT']
    config = {name: getattr(settings, name) for name in config_names}
    config['RAG_GROUNDING_REVIEW'] = getattr(settings, 'RAG_GROUNDING_REVIEW', False)
    signature = dict(dataset_sha256=digest(DATASET), source_sha256=hashes, configuration=config,
                     variant=args.variant, snapshot_origin=str(origin), runner_sha256=digest(__file__))
    manifest_path = run_dir / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if any(manifest.get(key) != value for key, value in signature.items()):
            raise ValueError('Resume inputs/configuration differ from this frozen run')
    else:
        manifest = dict(**signature, format_version=1, condition=args.variant,
            started_at=datetime.now(timezone.utc).isoformat(),
            purpose='Fresh development generalisation check', draft_run=True,
            installed_packages=sorted({f"{d.metadata['Name']}=={d.version}" for d in distributions()}),
            reference_review='AI source checked; human review pending',
            scope_status='Saved scopes; strict local revision checks; no live publication refresh',
            limitations=['Single run per condition, same-family judge, author aware of prior failures',
                         'Fixed follow-up histories, not full interactive conversation trajectories',
                         'Warm local models; serial cases; latency excludes HTTP/mobile and is exploratory'])
        atomic_json(manifest_path, manifest)
        shutil.copyfile(DATASET, run_dir / 'dataset.jsonl')
        atomic_json(run_dir / 'scopes.json', scopes)
    # Equal warmup for all variants; do not count cold local-model loading as a
    # model-review latency penalty. No application LLM is called for warmup.
    warmup_started = perf_counter()
    from rag.app.embedding.embedder import embed_query
    from rag.app.retrieval.hybrid import reranker
    await asyncio.to_thread(embed_query, 'vehicle evaluation warmup')
    await asyncio.to_thread(reranker().predict, [('vehicle safety', 'A vehicle reference.')])
    manifest['warmup_seconds'] = round(perf_counter() - warmup_started, 4)
    order = list(cases)
    random.Random(417).shuffle(order)
    manifest['case_order'] = [row['case_id'] for row in order]
    atomic_json(manifest_path, manifest)
    summary = []
    for case in order:
        path = run_dir / 'cases' / f"{case['case_id']}.json"
        if path.exists():
            artifact = json.loads(path.read_text())
        else:
            scope = scopes[case['scope_file']]
            artifact = dict(case_id=case['case_id'], case=case,
                            evaluation_input=evaluation_input(case, scope), trace={})
            started = perf_counter()
            recorder = EvaluationCapture(query, grounded, GenerationClient, asset_dir=run_dir / 'assets')
            try:
                with recorder:
                    artifact['reply'] = await query.handle_query(case['user_input'], scope=scope,
                        history=case['history'], admin_trace=artifact['trace'])
            except Exception as error:
                artifact['error_type'] = type(error).__name__
            artifact['capture'] = recorder.artifact()
            artifact['latency_seconds'] = round(perf_counter() - started, 4)
            expected_model = settings.GEMINI_MODEL.removeprefix('models/')
            artifact['model_mismatch_call_ids'] = [call['id'] for call in recorder.calls
                if call.get('response') is not None and call.get('model') != expected_model]
            reply = artifact.get('reply', {})
            artifact['status'] = 'error' if (artifact.get('error_type') or artifact['model_mismatch_call_ids']
                or reply.get('response_type') in {'generation_error', 'retrieval_error'}) else 'captured'
            artifact['response_type_matches'] = reply.get('response_type') in case['expected_response_types']
            atomic_json(path, artifact)
        row = dict(case_id=case['case_id'], status=artifact['status'],
                   latency_seconds=artifact['latency_seconds'],
                   response_type=artifact.get('reply', {}).get('response_type'),
                   application_calls=len(artifact['capture']['calls']))
        summary.append(row)
        atomic_json(run_dir / 'summary.json', summary)
        print(json.dumps(dict(variant=args.variant, **row)), flush=True)
    manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
    atomic_json(manifest_path, manifest)
    return 1 if any(row['status'] == 'error' for row in summary) else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True, choices=SNAPSHOTS)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(capture(args)))
