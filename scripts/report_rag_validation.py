"""Report paired fresh-case scores, coverage, rubric checks and model-call cost."""
import csv
from html import escape
import json
from pathlib import Path
import random
import statistics

from scripts.evaluate_rag import atomic_json
from scripts.run_rag_validation import ROOT_OUTPUT, SNAPSHOTS
from scripts.score_rag import ORDER, score_summary
from scripts.report_rag import LABELS

VARIANTS = tuple(SNAPSHOTS)
NAMES = dict(original='Original', improved_no_review='Fixes; review off', improved_full='Fixes + review')


def paired_values(scores, metric):
    available = {variant: {row['case_id']: row['metrics'][metric]['value'] for row in rows
        if row['metrics'][metric]['status'] == 'scored'} for variant, rows in scores.items()}
    common = sorted(set.intersection(*(set(rows) for rows in available.values())))
    return common, {variant: [available[variant][identity] for identity in common] for variant in available}


def bootstrap_delta(before, after, iterations=10000):
    if len(before) != len(after):
        raise ValueError('Paired observations required')
    if not before:
        return dict(mean=None, low=None, high=None, n=0)
    differences = [b-a for a, b in zip(before, after)]
    rng = random.Random(417)
    samples = sorted(statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(iterations))
    return dict(mean=statistics.mean(differences), low=samples[int(.025*iterations)],
                high=samples[min(iterations-1, int(.975*iterations))], n=len(differences))


def fmt(value):
    return f'{value:.3f}' if value is not None else 'N/A'


def build():
    output = ROOT_OUTPUT / 'report'
    output.mkdir(exist_ok=True)
    manifests = {v: json.loads((ROOT_OUTPUT/v/'manifest.json').read_text()) for v in VARIANTS}
    if len({m['dataset_sha256'] for m in manifests.values()}) != 1:
        raise ValueError('Dataset differs between conditions')
    configs = [{k:value for k,value in manifests[v]['configuration'].items()
                if k != 'RAG_GROUNDING_REVIEW'} for v in VARIANTS]
    if any(c != configs[0] for c in configs):
        raise ValueError('Application settings differ beyond the intended review switch')
    score_manifests = {v: json.loads((ROOT_OUTPUT/v/'scoring/manifest.json').read_text()) for v in VARIANTS}
    if any(score_manifests[v]['configuration'] != score_manifests['original']['configuration'] for v in VARIANTS):
        raise ValueError('Evaluator differs between conditions')
    scores = {v: json.loads((ROOT_OUTPUT/v/'scoring/scores.json').read_text()) for v in VARIANTS}
    artifacts = {v: {p.stem: json.loads(p.read_text()) for p in (ROOT_OUTPUT/v/'cases').glob('*.json')} for v in VARIANTS}
    ids = sorted(artifacts['original'])
    if any(set(artifacts[v]) != set(ids) for v in VARIANTS):
        raise ValueError('Case coverage differs')
    audit = {v: {p.stem: json.loads(p.read_text()) for p in (ROOT_OUTPUT/'audit'/v).glob('*.json')} for v in VARIANTS}
    paired = {}
    for name in ORDER:
        common, values = paired_values(scores, name)
        paired[name] = dict(case_ids=common, n=len(common),
            means={v:statistics.mean(values[v]) if common else None for v in VARIANTS},
            full_minus_original=bootstrap_delta(values['original'], values['improved_full']),
            full_minus_no_review=bootstrap_delta(values['improved_no_review'], values['improved_full']))
    operations, rubric = {}, {}
    for variant in VARIANTS:
        rows = list(artifacts[variant].values())
        factual = [a for a in rows if a['case']['reference']]
        behaviours = [audit[variant].get(a['case_id'], {}) for a in rows if not a['case']['reference']]
        fact_audits = [audit[variant].get(a['case_id'], {}) for a in factual]
        valid_fact = [a for a in fact_audits if a.get('status') == 'audited']
        coverages = [len(a['covered_fact_indices'])/(len(a['covered_fact_indices'])+len(a['missing_fact_indices']))
                     for a in valid_fact if a['covered_fact_indices'] or a['missing_fact_indices']]
        operations[variant] = dict(cases=len(rows), factual_cases=len(factual),
            failures=sum(a['status'] != 'captured' for a in rows),
            model_mismatches=sum(len(a['model_mismatch_call_ids']) for a in rows),
            total_calls=sum(len(a['capture']['calls']) for a in rows),
            factual_mean_calls=statistics.mean(len(a['capture']['calls']) for a in factual),
            factual_median_seconds=statistics.median(a['latency_seconds'] for a in factual),
            factual_mean_seconds=statistics.mean(a['latency_seconds'] for a in factual))
        rubric[variant] = dict(behaviour_passes=sum(a.get('behaviour_pass') is True for a in behaviours),
            behaviour_audited=sum(a.get('status') == 'audited' for a in behaviours),
            behaviour_total=len(behaviours), factual_audited=len(valid_fact),
            mean_required_fact_coverage=statistics.mean(coverages) if coverages else None,
            applicability_failures=sum(not a['source_applicability_pass'] for a in valid_fact),
            safety_failures=sum(not a.get('safety_pass', True) for a in audit[variant].values() if a.get('status') == 'audited'),
            answers_with_unestablished_extra_claims=sum(bool(a['unsupported_or_uncertain_claims']) for a in valid_fact),
            mean_helpfulness=statistics.mean(a['helpfulness'] for a in valid_fact) if valid_fact else None,
            audit_errors=sum(a.get('status') != 'audited' for a in audit[variant].values()))
    result = dict(dataset_sha256=manifests['original']['dataset_sha256'],
        paired_metrics=paired, all_case_metric_availability={v:score_summary(scores[v]) for v in VARIANTS},
        operations=operations, ai_rubric=rubric,
        interpretation='Provisional source-backed fresh development comparison; not human-reviewed or final heldout results')
    atomic_json(output/'comparison.json', result)
    md = ['# Roadie: fresh 30-question pipeline comparison', '',
        '**Provisional development results.** 20 factual questions and 10 behaviour checks; AI-authored, source-checked references await human review.', '',
        f"Application model: `{manifests['original']['configuration']['GEMINI_MODEL']}`. Judge: `{score_manifests['original']['configuration']['judge']['model']}`. RAGAS: `{score_manifests['original']['configuration']['ragas_version']}`.", '',
        'All questions and references were frozen before generation. The same application model, corpus, saved scopes and evaluator settings were used. Application code came from saved snapshots, and no pipeline tuning occurred during this comparison.', '',
        'The middle condition includes retrieval/context and prompt fixes with review disabled. It is not an isolated retrieval-only ablation. Comparing the middle and final conditions isolates enabling the review pass.', '',
        '## Paired RAGAS results', '',
        'Each row uses the same scored cases in all three conditions. Missing scores are not zero and are not silently treated as successful answers.', '',
        '| Metric | Original | Fixes; review off | Fixes + review | Paired n | Full − original, 95% interval | Full − review off, 95% interval |',
        '| --- | ---: | ---: | ---: | ---: | --- | --- |']
    for name in ORDER:
        r=paired[name];d=r['full_minus_original'];review_delta=r['full_minus_no_review']
        md.append('| '+' | '.join([LABELS[name]]+[fmt(r['means'][v]) for v in VARIANTS]+[str(r['n']),
            f"{fmt(d['mean'])} [{fmt(d['low'])}, {fmt(d['high'])}]",
            f"{fmt(review_delta['mean'])} [{fmt(review_delta['low'])}, {fmt(review_delta['high'])}]"])+' |')
    md += ['', 'Intervals are paired case-bootstrap percentile intervals (10,000 resamples, fixed seed 417). They represent variation across these questions, not repeated model/judge variability or a representative population sample.', '',
        '## Coverage and operating cost', '',
        '| Condition | Capture failures | Model mismatches | Total application calls | Mean calls / factual case | Median seconds / factual case |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for v in VARIANTS:
        r=operations[v];md.append(f"| {NAMES[v]} | {r['failures']} | {r['model_mismatches']} | {r['total_calls']} | {r['factual_mean_calls']:.2f} | {r['factual_median_seconds']:.2f} |")
    md += ['', 'Local embedding/reranking models were warmed before timing. Cases and conditions ran serially in a fixed shuffled case order. These timings exclude HTTP/mobile rendering; conditions were run in blocks, so time-of-run and API variability remain confounders. Model-call counts are not token usage or monetary cost.', '',
        '## AI-assisted rubric checks', '',
        'The fixed judge saw one anonymous answer at a time, without variant labels or RAGAS scores. These are supplementary AI ratings, not human or automotive expert review. Extra claims absent from the original reference sources are labelled unestablished/uncertain, not automatically false.', '',
        '| Condition | Behaviour passes / audited | Required-fact coverage | Applicability failures | Safety flags | Mean helpfulness / 2 | Audit errors |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for v in VARIANTS:
        r=rubric[v];md.append(f"| {NAMES[v]} | {r['behaviour_passes']} / {r['behaviour_audited']} | {fmt(r['mean_required_fact_coverage'])} | {r['applicability_failures']} | {r['safety_failures']} | {fmt(r['mean_helpfulness'])} | {r['audit_errors']} |")
    md += ['', '## Metric availability', '', '| Condition | Metric | Scored | N/A | Errors |', '| --- | --- | ---: | ---: | ---: |']
    for v in VARIANTS:
        for name,r in result['all_case_metric_availability'][v].items():
            md.append(f"| {NAMES[v]} | {LABELS[name]} | {r['scored']} | {r['not_applicable']} | {r['errors']} |")
    md += ['', '## Limits and next decision', '',
        '- New prompts were authored after seeing the pilot failures, by an author aware of the implemented fixes. They are not an independently sampled external benchmark.',
        '- The corpus and vehicle scopes are the same as development. This tests new questions within the existing corpus, not unseen manuals or vehicles.',
        '- The judge, answer writer and review pass use the same model family; correlated errors and grader variability remain possible.',
        '- References and rubric judgments are AI-checked and pending human review. The recorded human-review sheets must not be represented as completed human evaluation.',
        '- Visual evidence can make text-only faithfulness unavailable. Application failures, score availability and paired case counts are reported separately.',
        '- Fixed follow-up histories are identical across conditions. This does not test how each system creates its own multi-turn conversation history.',
        '- A 0.75 target is a project choice, not a universal RAGAS pass standard. Improvements here do not prove every answer correct or complete.',
        '- Keep these questions as development data. Select a pipeline after reviewing tradeoffs; use that same frozen pipeline for base-model and fine-tuned-model experiments, with separate training data and a fresh final test set.', '',
        'Framework: [Es et al., RAGAs, EACL 2024](https://aclanthology.org/2024.eacl-demo.16/). Metric definitions: [RAGAS documentation](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/).', '',
        '## Per-case answers and review', '']
    cards=[]
    score_maps={v:{r['case_id']:r for r in scores[v]} for v in VARIANTS}
    for identity in ids:
        case=artifacts['original'][identity]['case']
        md += [f'### {identity}', '', case['user_input'], '', '**Reference / rubric:** '+(case['reference'] or ' '.join(case['required_facts'])), '']
        html_answers=[]
        for v in VARIANTS:
            a=artifacts[v][identity];review=audit[v].get(identity,{})
            answer=a.get('reply',{}).get('answer','No answer')
            md += ['**'+NAMES[v]+':**', '', answer, '', '**AI finding:** '+review.get('finding',review.get('error_type','No audit')), '']
            metrics=' · '.join(LABELS[n]+': '+(fmt(score_maps[v][identity]['metrics'][n]['value'])
                if score_maps[v][identity]['metrics'][n]['status']=='scored' else score_maps[v][identity]['metrics'][n]['status']) for n in ORDER)
            html_answers.append(f"<section class='answer'><h3>{escape(NAMES[v])}</h3><p class='meta'>{a['latency_seconds']:.2f}s · {len(a['capture']['calls'])} calls · {escape(a.get('reply',{}).get('response_type','error'))}</p><pre>{escape(answer)}</pre><p class='meta'>{escape(metrics)}</p><p><strong>AI finding:</strong> {escape(review.get('finding',review.get('error_type','No audit')))}</p></section>")
        cards.append(f"<article><h2>{identity}</h2><p class='question'>{escape(case['user_input'])}</p><p><strong>Reference / rubric:</strong> {escape(case['reference'] or ' '.join(case['required_facts']))}</p><details><summary>Compare all three answers</summary>{''.join(html_answers)}</details><details><summary>Original source excerpts</summary>{''.join('<pre>'+escape(s['excerpt'])+'</pre>' for s in case['reference_sources'])}</details></article>")
    (output/'report.md').write_text('\n'.join(md)+'\n')
    # Render the compact comparison sections directly; per-case details are
    # collapsible for review without embedding executable source content.
    tables=[];table=[]
    for line in md[:md.index('## Per-case answers and review')]:
        if line.startswith('|'):
            cells=[part.strip() for part in line.strip('|').split('|')]
            if all(set(c)<=set('-: ') for c in cells):continue
            table.append('<tr>'+''.join('<td>'+escape(c)+'</td>' for c in cells)+'</tr>')
        elif table:
            tables.append('<div class="scroll"><table>'+''.join(table)+'</table></div>');table=[]
    if table:tables.append('<div class="scroll"><table>'+''.join(table)+'</table></div>')
    limits=md[md.index('## Limits and next decision')+2:md.index('## Per-case answers and review')]
    html="""<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Roadie fresh validation</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#182334;font:16px/1.6 system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:36px 24px}h1{line-height:1.2}.meta{font-size:13px;color:#5b697a}.notice,article,.answer{background:white;border:1px solid #dce3ec;border-radius:10px;padding:20px;margin:16px 0}.notice{border-left:5px solid #b58136}.question{font-size:18px;font-weight:600}table{width:100%;border-collapse:collapse;background:white;font-size:14px}td{padding:10px;border-bottom:1px solid #dce3ec}tr:first-child{font-weight:650}.scroll{overflow:auto;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 ui-monospace,monospace;background:#f7f9fb;padding:15px}summary{cursor:pointer;color:#175b63}a{color:#175b63}</style><main>
    <h1>Roadie: fresh 30-question comparison</h1><div class='notice'><strong>Provisional development evidence.</strong> 20 factual questions and 10 behaviour checks, frozen before generation. AI-checked references and AI-assisted audits await human review. The same model, corpus and evaluator were used. No pipeline changes were made during this experiment.</div>
    <p>The middle condition contains retrieval/context and prompt fixes with review disabled. Comparing it with the final condition isolates the additional review pass.</p>
    <h2>Paired RAGAS results</h2><p>Each metric compares the same scored cases across all three conditions. Intervals use 10,000 paired case-bootstrap resamples. They do not measure repeated model/judge variability.</p>"""
    html += f"<p class='meta'>Application: {escape(manifests['original']['configuration']['GEMINI_MODEL'])} · Judge: {escape(score_manifests['original']['configuration']['judge']['model'])} · RAGAS {escape(score_manifests['original']['configuration']['ragas_version'])}</p>"
    html += tables[0]+'<h2>Coverage and operating cost</h2>'+tables[1]+'<p>Local models warmed; serial conditions and cases. HTTP/mobile time excluded. Timings remain exploratory; call counts are not monetary cost.</p>'
    html += '<h2>AI-assisted rubric checks</h2>'+tables[2]+'<p>Anonymous answers judged separately without variant labels or RAGAS scores. These ratings are not human expert verification.</p>'
    html += '<h2>Metric availability</h2>'+tables[3]+'<h2>Limits and next decision</h2><ul>'+''.join('<li>'+escape(line[2:])+'</li>' for line in limits if line.startswith('- '))+'</ul>'
    html += '<p><a href="../preparation/review-30-questions.md">Reference review sheet</a> · <a href="report.md">Full Markdown report</a> · <a href="comparison.json">Machine-readable comparison</a></p><h2>Per-case answers</h2>'+''.join(cards)+'</main></html>'
    (output/'report.html').write_text(html)
    with (output/'per-case.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['case_id','variant','status','response_type','seconds','calls']+list(ORDER))
        for identity in ids:
            for v in VARIANTS:
                a=artifacts[v][identity];writer.writerow([identity,v,a['status'],a.get('reply',{}).get('response_type'),a['latency_seconds'],len(a['capture']['calls'])]+[score_maps[v][identity]['metrics'][n]['value'] for n in ORDER])
    print(json.dumps(dict(paired_metrics=paired, operations=operations, ai_rubric=rubric),indent=2))


if __name__ == '__main__':
    build()
