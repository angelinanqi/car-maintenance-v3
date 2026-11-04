"""Build a local HTML/Markdown/CSV report from saved capture and RAGAS results."""
import argparse
import csv
from html import escape
import json
from pathlib import Path

from scripts.evaluate_rag import local_path
from scripts.score_rag import ORDER, score_summary

LABELS = {"context_precision": "Context Precision", "context_recall": "Context Recall",
          "faithfulness": "Faithfulness", "factual_correctness": "Factual Correctness (F1)",
          "answer_relevancy": "Answer Relevancy"}


def display(result):
    if result["status"] == "scored":
        return f"{result['value']:.3f}"
    return "Error" if result["status"] == "error" else "N/A"


def build(run, scoring, output, notes, *, title="Roadie: five-case development baseline", baseline_scoring=None):
    rows = json.loads((scoring / "scores.json").read_text())
    summary = score_summary(rows)
    score_manifest = json.loads((scoring / "manifest.json").read_text())
    capture_manifest = json.loads((run / "manifest.json").read_text())
    artifacts = {row["case_id"]: json.loads((run / "cases" / (row["case_id"] + ".json")).read_text()) for row in rows}
    samples = {s["case_id"]: s for s in json.loads((scoring / "samples.json").read_text())}
    output.mkdir(parents=True, exist_ok=True)
    comparison = []
    if baseline_scoring:
        baseline_rows = json.loads((baseline_scoring / 'scores.json').read_text())
        baseline_manifest = json.loads((baseline_scoring / 'manifest.json').read_text())
        baseline_run = Path(baseline_manifest['capture_run'])
        baseline_capture = json.loads((baseline_run / 'manifest.json').read_text())
        if baseline_capture['dataset_sha256'] != capture_manifest['dataset_sha256']:
            raise ValueError('Comparison requires the same reviewed dataset')
        before_config = dict(baseline_manifest['configuration'])
        after_config = dict(score_manifest['configuration'])
        # Scorer source hashes are recorded, but all evaluator settings must match.
        if before_config != after_config:
            raise ValueError('Comparison requires the same evaluator configuration')
        baseline_summary = score_summary(baseline_rows)
        for name in ORDER:
            before, after = baseline_summary[name], summary[name]
            delta = after['mean'] - before['mean'] if before['mean'] is not None and after['mean'] is not None else None
            comparison.append(dict(metric=name, before=before, after=after, delta=delta))
        (output / 'comparison.json').write_text(json.dumps(dict(
            baseline_scoring=str(baseline_scoring), current_scoring=str(scoring),
            metrics=comparison), indent=2) + '\n')
    limits = ["These five development cases verify the evaluation workflow and expose diagnostic examples. They do not establish overall system accuracy or a fine-tuning benefit.",
              "Four cases have factual references; one tests clarification behaviour. N/A and evaluator errors are excluded from means and counted separately.",
              "The judge and generator use the same model in this run. Automated judgements can share model errors and are not independent expert verification.",
              "Faithfulness assesses support from supplied text. It can penalise allowed general-information claims, and cannot validate original image pixels.",
              "Factual Correctness measures agreement with the reviewed reference. Correct extra information absent from that reference can lower the score.",
              "Catalogue scopes came from saved inventories with strict local index-revision checks; live publication status was not refreshed.",
              "The initial response-type matcher expected manual_only for every answer. DEV003's published_content and DEV004's mixed_sources are valid answer types; those raw type mismatches are not semantic failures.",
              "Exploratory and failed runs are retained separately; the capture and scoring directories below identify this report's exact inputs."]
    md = [f"# {title}", "", "Diagnostic results, not a final benchmark.", "",
          f"Application model: `{capture_manifest['configuration']['GEMINI_MODEL']}`. "
          f"Judge: `{score_manifest['configuration']['judge']['model']}`. "
          f"RAGAS: `{score_manifest['configuration']['ragas_version']}`.", "",
          "| Metric | Mean | Scored cases | N/A | Errors |", "| --- | ---: | ---: | ---: | ---: |"]
    for name in ORDER:
        result = summary[name]
        mean = f"{result['mean']:.3f}" if result["mean"] is not None else "N/A"
        md.append(f"| {LABELS[name]} | {mean} | {result['scored']} | {result['not_applicable']} | {result['errors']} |")
    comparison_html = ''
    if comparison:
        md += ['', '## Comparison with preserved baseline', '',
               'Same reviewed development questions and evaluator settings. This is a combined pipeline change, not a fine-tuning comparison or an estimate of generalisation.', '',
               '| Metric | Before | After | Change | Scored before / after |',
               '| --- | ---: | ---: | ---: | ---: |']
        cells = []
        for item in comparison:
            name, before, after, delta = item['metric'], item['before'], item['after'], item['delta']
            values = [LABELS[name], f"{before['mean']:.3f}" if before['mean'] is not None else 'N/A',
                      f"{after['mean']:.3f}" if after['mean'] is not None else 'N/A',
                      f'{delta:+.3f}' if delta is not None else 'N/A',
                      f"{before['scored']} / {after['scored']}"]
            md.append('| ' + ' | '.join(values) + ' |')
            cells.append('<tr>' + ''.join('<td>' + escape(v) + '</td>' for v in values) + '</tr>')
        comparison_html = ("<section class='limits'><h2>Comparison with preserved baseline</h2>"
            "<p>Same reviewed development questions and evaluator settings. Combined pipeline changes; this does not establish generalisation or a fine-tuning benefit.</p>"
            "<div class='scroll'><table><thead><tr><th>Metric</th><th>Before</th><th>After</th><th>Change</th><th>Scored before / after</th></tr></thead><tbody>"
            + ''.join(cells) + '</tbody></table></div></section>')
    md += ["", "## Source inspection and behaviour checks", "", "These annotations are AI-assisted source inspection, not user-reviewed answer ratings or independent automotive expert review.", ""]
    for note in notes:
        md += [f"- **{note['case_id']} — {note['category']}:** {note['finding']}"]
    md += ["", "## Per-case results", ""]
    cards = []
    for row in rows:
        identity = row["case_id"]
        artifact, sample = artifacts[identity], samples[identity]
        case = artifact["case"]
        md += [f"### {identity}", "", "Question: " + case["user_input"], "", "Response:", "", artifact.get("reply", {}).get("answer", "No answer"), "",
               "Reference / expected behaviour:", "", case["reference"] or " ".join(case["required_facts"]), "",
               "Scores: " + "; ".join(f"{LABELS[n]} {display(row['metrics'][n])}" for n in ORDER), ""]
        metric_cells = "".join(f"<td>{escape(display(row['metrics'][n]))}</td>" for n in ORDER)
        context = "".join(f"<pre>{escape(text)}</pre>" for text in sample["retrieved_contexts"])
        case_notes = "".join(f"<p>{escape(note['finding'])}</p>" for note in notes if note["case_id"] == identity)
        cards.append(f"<article><h2>{escape(identity)}</h2><p class='question'>{escape(case['user_input'])}</p>"
                     f"<p class='meta'>{escape(case['vehicle_code'])} · {escape(sample['response_type'] or '')} · "
                     f"{artifact['latency_seconds']:.3f} s · {len(artifact['capture']['calls'])} application LLM calls</p>"
                     f"<h3>Actual answer</h3><pre>{escape(sample['response'])}</pre>"
                     f"<h3>Reviewed reference / expected behaviour</h3><pre>{escape(case['reference'] or ' '.join(case['required_facts']))}</pre>"
                     f"<div class='scroll'><table><thead><tr>{''.join('<th>'+escape(LABELS[n])+'</th>' for n in ORDER)}</tr></thead><tbody><tr>{metric_cells}</tr></tbody></table></div>"
                     f"<div class='note'>{case_notes}</div><details><summary>Inspect supplied text contexts ({len(sample['retrieved_contexts'])})</summary>{context}</details>"
                     f"<details><summary>Metric status details</summary><pre>{escape(json.dumps(row['metrics'],indent=2))}</pre></details>"
                     f"<details><summary>Intent and capture trace</summary><pre>{escape(json.dumps(artifact['capture']['intent'],ensure_ascii=False,indent=2))}</pre></details></article>")
    md += ["## Interpretation limits", ""] + ["- " + text for text in limits]
    md += ["", "## Reproducibility", "", f"Capture directory: `{run}`", "", f"Scoring directory: `{scoring}`", "",
           "The directories retain manifests, source snapshots, prompts, raw answers, supplied images, judge prompts, claim verdicts, dependency versions and per-metric results.", "",
           "Framework citation: [Es et al., EACL 2024](https://aclanthology.org/2024.eacl-demo.16/). "
           "Metric implementations: [RAGAS documentation](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/).", ""]
    (output / "report.md").write_text("\n".join(md))
    with (output / "per-case.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case_id", "response_type", "latency_seconds"] + [f"{n}_{field}" for n in ORDER for field in ("status", "value")])
        for row in rows:
            a = artifacts[row["case_id"]]
            writer.writerow([row["case_id"], a.get("reply", {}).get("response_type"), a["latency_seconds"]]
                            + [row["metrics"][n][field] for n in ORDER for field in ("status", "value")])
    stat_cards = "".join(f"<div class='stat'><span>{escape(LABELS[n])}</span><strong>{summary[n]['mean']:.3f}</strong>"
                         f"<small>{summary[n]['scored']} scored · {summary[n]['not_applicable']} N/A · {summary[n]['errors']} errors</small></div>"
                         if summary[n]["mean"] is not None else f"<div class='stat'>{escape(LABELS[n])}<strong>N/A</strong></div>" for n in ORDER)
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Roadie development evaluation</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#182334;font:16px/1.6 system-ui,sans-serif}main{max-width:1140px;margin:auto;padding:40px 24px}h1{font-size:32px;line-height:1.2}h2{margin-top:0}h3{font-size:15px;margin-bottom:8px}.eyebrow,.meta,small{color:#59697c}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:28px 0}.stat,article,.limits{background:white;border:1px solid #dce3ec;border-radius:12px;padding:22px}.stat span,.stat small{display:block}.stat strong{display:block;font-size:34px;color:#175b63}article{margin:20px 0}.question{font-size:19px;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 ui-monospace,monospace;background:#f6f8fb;padding:16px;border-radius:8px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:10px;border-bottom:1px solid #e1e6ed;text-align:left}.note{border-left:3px solid #bc8541;padding-left:16px;color:#6c4b22}details{margin-top:14px}summary{cursor:pointer;color:#175b63}li{margin-bottom:10px}a{color:#175b63}
</style><main>"""
    html += f"<p class='eyebrow'>ROADIE · DEVELOPMENT EVALUATION</p><h1>{escape(title)}</h1><p>Four answer cases and one clarification case. These results are diagnostic and do not establish overall system accuracy.</p>"
    html += f"<p class='meta'>Application: {escape(capture_manifest['configuration']['GEMINI_MODEL'])} · Judge: {escape(score_manifest['configuration']['judge']['model'])} · RAGAS {escape(score_manifest['configuration']['ragas_version'])}</p><div class='stats'>{stat_cards}</div>"
    html += comparison_html + "".join(cards)
    html += "<section class='limits'><h2>Interpretation limits</h2><ul>" + "".join("<li>" + escape(text) + "</li>" for text in limits) + "</ul>"
    html += "<p><a href='https://aclanthology.org/2024.eacl-demo.16/'>RAGAS framework paper, EACL 2024</a> · <a href='https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/'>Metric documentation</a></p></section></main></html>"
    (output / "report.html").write_text(html)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--scoring", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--notes")
    parser.add_argument("--title", default="Roadie: five-case development baseline")
    parser.add_argument("--baseline-scoring")
    args = parser.parse_args()
    notes = json.loads(local_path(args.notes).read_text()) if args.notes else []
    output = local_path(args.output)
    if not output.is_relative_to(local_path("output")):
        parser.error("Private reports must remain under output/")
    summary = build(local_path(args.run), local_path(args.scoring), output, notes,
                    title=args.title,
                    baseline_scoring=local_path(args.baseline_scoring) if args.baseline_scoring else None)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
