"""Emergency text and approved descriptions adapted to the shared HTML pipeline."""
from html import escape
import json
from uuid import uuid5, NAMESPACE_URL
from shared.source_elements import FORMAT_VERSION


def revision(playbook):
    payload = [1, *[playbook.get(key) for key in
                   ('id', 'title', 'description', 'safety_warnings', 'source', 'scenario_key', 'steps')]]
    return str(uuid5(NAMESPACE_URL, json.dumps(payload, sort_keys=True, ensure_ascii=False)))


def eligible(playbook):
    return bool(playbook.get('status') == 'published' and playbook.get('reviewed_at')
                and playbook.get('source') and playbook.get('scenario_key') and playbook.get('steps'))


def prepare_html(playbook):
    parts = [f'<h1>{escape(playbook["title"])}</h1>',
             f'<p>Emergency scenario: {escape(playbook["scenario_key"])}</p>']
    for key, title in [('description', 'Situation'), ('safety_warnings', 'Safety warnings')]:
        if playbook.get(key):
            parts += [f'<h2>{title}</h2>', f'<p>{escape(playbook[key])}</p>']
    media, texts, steps = [], [], []
    for number, step in enumerate(playbook['steps'], 1):
        heading = f'Step {number}: {step["title"]}'
        parts += [f'<h2>{escape(heading)}</h2>', f'<p>{escape(step["description"])}</p>']
        context = dict(step_id=step['id'], step_order=number, step_title=step['title'])
        steps.append(dict(heading=heading, **context))
        for item in step.get('media', []):
            if not item.get('reviewed') or not item.get('asset_id'):
                continue
            media.append({**item, **context})
            text = '\n'.join(filter(None, [playbook['title'], playbook['scenario_key'], heading,
                step['description'], f'Reviewed {item["kind"]} description: {item["description"]}',
                item.get('vehicle_context')]))
            texts.append(dict(media_id=item['id'], start_seconds=0, text=text,
                              section_path=[playbook['title'], heading], **context))
    manifest = dict(format_version=FORMAT_VERSION, document_id=playbook['id'],
        source_revision=revision(playbook), source_type='html', elements=[],
        guide_media_texts=texts, emergency_steps=steps, scenario_key=playbook['scenario_key'])
    # No videos or image pixels enter an external ingestion pipeline. Reviewed
    # descriptions are evidence; original owned files are resolved by media ID.
    return '\n'.join(parts), manifest, {}, media, [], []
