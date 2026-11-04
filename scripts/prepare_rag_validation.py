"""Freeze fresh diagnostic questions and source-backed, AI-checked references."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata

from scripts.evaluate_rag import ROOT, METRICS, digest, load_cases, local_path

SCOPES = {'alza': 'output/recovery/baseline-20261104/scope.json',
          'myvi': 'output/recovery/scope-perodua-myvi-2021.json'}
MANUALS = {'alza': '75da8572-040f-4a48-8af8-cd848916e445_f628104b-af4a-4241-b0e2-517804c16b2b',
           'myvi': '906df65b-16ad-4ffa-af28-38d6118c7de7_30a3875c-ff32-4ee4-a94a-5f86b6e198f3'}


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split()).casefold()


def build(output):
    specs_path = ROOT / 'scripts/data/rag_validation_v1.json'
    specs = json.loads(specs_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    scopes = {name: json.loads((ROOT / path).read_text()) for name, path in SCOPES.items()}
    rows, sheet = [], ['# Fresh validation reference review', '',
        '30 development questions. References are AI-checked against saved sources, pending human review.',
        'Frozen before any answers were generated. This is not a final heldout test or expert validation.',
        'The Myvi manual is catalogued for 2021-current; its edition footer can show 2022, as disclosed in the initial source review.', '']
    previous = [json.loads(line)['user_input'] for line in (ROOT / 'output/evaluations/ragas-preparation/development-smoke-v1.jsonl').read_text().splitlines()]
    for spec in specs:
        if spec['question'] in previous:
            raise ValueError('Question duplicates the pilot')
        vehicle = spec.get('scope', 'alza')
        scope = scopes[vehicle]
        sources = []
        if 'reference' in spec:
            if 'guide' in spec:
                key = next(k for k, value in scope['document_metadata'].items()
                           if value.get('document_title') == spec['guide'])
                indices = [0]
            else:
                key, indices = MANUALS[vehicle], spec['chunks']
            meta = scope['document_metadata'][key]
            chunks_path = ROOT / 'output/chunks' / f'{key}.json'
            manifest_path = ROOT / 'output/sources' / f'{key}.json'
            chunks = json.loads(chunks_path.read_text())
            source_manifest = json.loads(manifest_path.read_text())
            excerpt = '\n\n'.join(chunks[i].get('source_content') or chunks[i]['text'] for i in indices)
            source = dict(title=meta['document_title'], document_id=meta['document_id'],
                source_revision=meta['index_revision'], source_type=meta.get('source_type', 'owners_manual'),
                source_manifest=str(manifest_path.relative_to(ROOT)), source_manifest_sha256=digest(manifest_path),
                chunks_path=str(chunks_path.relative_to(ROOT)), chunks_sha256=digest(chunks_path),
                chunk_indices=indices, excerpt=excerpt,
                source_check='AI checked saved source text; human review pending')
            if 'guide' not in spec:
                doc_id = meta['document_id']
                pdf = ROOT / f'output/documents/{doc_id}/{doc_id}.pdf'
                if digest(pdf) != source_manifest['source_sha256']:
                    raise ValueError('Original PDF does not match the prepared source')
                ocr = ROOT / f'output/documents/{doc_id}/ocr/{doc_id}'
                content = json.loads(next((ocr / 'metadata').glob('*_content_list.json')).read_text())
                pages = {r['page_idx'] + 1 for r in content
                         if normalized(spec['anchor']) in normalized(r.get('text', ''))}
                if len(pages) != 1:
                    raise ValueError(f"{spec['id']}: PDF anchor is missing or ambiguous: {pages}")
                page = pages.pop()
                image = ocr / f'images/pages/page-{page:05}.webp'
                source.update(pdf_path=str(pdf.relative_to(ROOT)), pdf_sha256=digest(pdf), pdf_page=page,
                              page_image_path=str(image.relative_to(ROOT)), page_image_sha256=digest(image),
                              source_check='AI checked saved chunks and original OCR page; human review pending')
            sources.append(source)
        else:
            sources.append(dict(title='Roadie behaviour requirement', source_type='application_requirement',
                excerpt=' '.join(spec['criteria']), source_check='AI-authored rubric; human review pending'))
        reference = spec.get('reference')
        row = dict(case_id=spec['id'], dataset_version='fresh-development-v1', split='development',
            scenario_group=spec.get('behavior') or ('guide:' + spec['guide'] if 'guide' in spec else 'manual:' + spec['id']),
            user_input=spec['question'], scope_file=SCOPES[vehicle], vehicle_code=scope['vehicle']['code'],
            history=spec.get('history', []), reference=reference,
            required_facts=re.split(r'(?<=[.!?])\s+', reference) if reference else spec['criteria'],
            prohibited_claims=[], reference_sources=sources,
            tags=['fresh_development', 'ai_reference_pending_human_review',
                  'behaviour' if not reference else 'manual' if 'chunks' in spec else 'guide',
                  'fixed_history_followup' if spec.get('history') else 'single_turn'],
            expected_behavior='answer' if reference else spec['behavior'],
            expected_response_types=['manual_only', 'mixed_sources', 'published_content'] if reference else [],
            eligible_metrics=sorted(METRICS) if reference else [],
            review_status='ai_checked', reviewer='AI source inspection; not human approval')
        rows.append(row)
        sheet += [f"## {row['case_id']}", '', '**Question:** ' + row['user_input'], '']
        if row['history']:
            sheet += ['**Fixed history:** ' + json.dumps(row['history'], ensure_ascii=False), '']
        sheet += ['**Reference / rubric:** ' + (reference or ' '.join(spec['criteria'])), '']
        for source in sources:
            sheet += ['**Source:** ' + source['title'] + (f"; PDF page {source['pdf_page']}" if 'pdf_page' in source else ''),
                      '', source['excerpt'], '']
    dataset = output / 'fresh-development-v1.jsonl'
    dataset.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    load_cases(dataset)
    (output / 'review-30-questions.md').write_text('\n'.join(sheet))
    manifest = dict(created_at=datetime.now(timezone.utc).isoformat(), dataset_sha256=digest(dataset),
        specs_sha256=digest(specs_path), cases=len(rows), factual_cases=sum(bool(r['reference']) for r in rows),
        behaviour_cases=sum(not r['reference'] for r in rows), reference_review='AI checked; human review pending',
        freeze_rule='No question, reference, metric or application changes after seeing validation outputs; all failures retained',
        purpose='Fresh development generalisation check, not a final FYP benchmark')
    (output / 'dataset-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(local_path(args.output))
