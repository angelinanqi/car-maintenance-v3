"""Bound model inputs without cutting factual passages or personal entries."""
from dataclasses import dataclass, field
import json
import re

from rag.config import settings
from shared.table_evidence import table_package, serialize_table


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False))


def content(record):
    text = record.metadata.get("source_content") or record.text.split("Content:\n", 1)[-1]
    preceding = record.metadata.get('preceding_source_context')
    if preceding:
        text = (f"Preceding text in the same column on PDF page {preceding['pdf_page']} "
                "(neighbouring evidence, not an inferred parent section):\n"
                + preceding['text'] + '\n\nRetrieved passage:\n' + text)
    return re.sub(r"^Image source:.*$", "", text, flags=re.M)


def bounded_history(history, budget=None):
    """Keep whole recent messages; a long answer must not erase its user topic."""
    budget = settings.RAG_HISTORY_CHARS if budget is None else budget
    messages = [{"role": m["role"], "content": m["content"]}
                for m in (history or [])[-settings.CHAT_HISTORY_LIMIT:]
                if m.get("role") in {"user", "assistant"} and isinstance(m.get("content"), str)]
    exchanges = []
    for message in messages:
        if message["role"] == "user":
            exchanges.append([message])
        elif exchanges:
            exchanges[-1].append(message)
    selected = []
    for exchange in reversed(exchanges):
        size = encoded_size(exchange)
        if size > budget:
            # Assistant prose is context, not evidence. Retain the whole user
            # request if its answer is too large, rather than losing all history.
            exchange = exchange[:1]
            size = encoded_size(exchange)
            if size > budget:
                break
        selected.insert(0, exchange)
        budget -= size
    return [message for exchange in selected for message in exchange]


def maintenance_source(context, budget):
    """Retain whole server-ordered entries, totals and an explicit coverage note."""
    result = {key: context[key] for key in ("vehicle_id", "as_of", "total_tasks", "total_standalone_services")}
    result.update(tasks=[], standalone_services=[], entries_omitted=False)
    if context.get('spending_summary') is not None:
        result['spending_summary'] = context['spending_summary']
    result['total_service_records'] = context.get('total_service_records', 0)
    result['recent_services'] = []
    result['service_history_omitted'] = False
    plan = context.get('service_plan')
    if plan:
        # Plan evidence shares P2's budget and preserves complete item entries.
        result['service_plan'] = {key: plan[key] for key in ('vehicle_id', 'mileage', 'as_of', 'total_tasks')}
        result['service_plan']['groups'] = {key: [] for key in plan['groups']}
    if encoded_size(json.dumps(result, ensure_ascii=False)) > budget:
        return None
    if plan:
        for group, entries in plan['groups'].items():
            for entry in entries:
                result['service_plan']['groups'][group].append(entry)
                if encoded_size(json.dumps(result, ensure_ascii=False)) > budget:
                    result['service_plan']['groups'][group].pop()
                    result['entries_omitted'] = True
                    break
    for key in ("tasks", "standalone_services", "recent_services"):
        for entry in context.get(key, []):
            result[key].append(entry)
            if encoded_size(json.dumps(result, ensure_ascii=False)) > budget:
                result[key].pop()
                break
    result['service_history_omitted'] = len(result['recent_services']) < result['total_service_records']
    result["entries_omitted"] = result['entries_omitted'] or result['service_history_omitted'] or any(
        len(result[key]) < context[total] for key, total in
        (("tasks", "total_tasks"), ("standalone_services", "total_standalone_services")))
    return json.dumps(result, ensure_ascii=False)


@dataclass
class GenerationContext:
    sources: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    omitted_sources: list[str] = field(default_factory=list)
    omitted_references: list[str] = field(default_factory=list)
    incomplete_section_labels: list[str] = field(default_factory=list)

    @property
    def incomplete(self):
        return bool(self.omitted_sources or self.incomplete_section_labels)


def public_values(value):
    """Internal row identifiers never need to be explained to a driver."""
    if isinstance(value, dict):
        return {key: public_values(item) for key, item in value.items()
                if key != 'id' and not key.endswith('_id')}
    if isinstance(value, list):
        return [public_values(item) for item in value]
    return value


def prepare_context(records, references, vehicle_profile=None, maintenance_context=None, *, image_sources=None):
    """Pack whole ranked passages; media descriptors do not spend the factual budget.

    Source labels retain record positions so the existing backend citation resolver
    and original-asset endpoints continue to work. No generated summaries intervene.
    """
    result = GenerationContext(references=list(references))
    remaining = settings.RAG_CONTEXT_CHARS
    personal = []
    if vehicle_profile:
        personal.append(dict(label='P1', document_type='personal_vehicle_profile', source_type='personal',
            content=json.dumps(public_values(vehicle_profile), ensure_ascii=False)))
    if maintenance_context:
        text = maintenance_source(maintenance_context, min(remaining // 2, 4500))
        if text:
            personal.append(dict(label='P2', document_type='personal_maintenance', source_type='personal',
                content=json.dumps(public_values(json.loads(text)), ensure_ascii=False)))
        else:
            result.omitted_sources.append('P2')
    for item in personal:
        if len(item['content']) <= remaining // 2:
            result.sources.append(item)
            remaining -= len(item['content'])
        else:
            result.omitted_sources.append(item['label'])
    seen = set()
    for index, record in enumerate(records, 1):
        metadata = record.metadata
        kind = metadata.get('content_type', 'paragraph')
        if kind not in {'paragraph', 'table'} and metadata.get('evidence_type') != 'ingestion_image_description':
            continue
        text = content(record).strip()
        # Generic learning-library illustration references describe placeholders,
        # not the actual attached manual original. Keep factual prose intact.
        text = re.sub(r'(?m)^Diagram reference:.*\n?', '', text)
        text = re.sub(r'(?m)^(?:Video:|Further reading:).*\n?', '', text).strip()
        identity = (metadata.get('document_name'), text)
        if not text or identity in seen:
            continue
        seen.add(identity)
        item = dict(label=f'S{index}', title=metadata.get('title') or metadata.get('document_title')
                    or metadata.get('document_name', 'Source'), content=text,
                    source_type=metadata.get('source_type', 'manual'),
                    document_type=metadata.get('document_type', 'other_reference'), content_type=kind,
                    source_fidelity_verified=metadata.get('source_fidelity_verified', False))
        if metadata.get('evidence_type'):
            item['evidence_type'] = metadata['evidence_type']
        if kind == 'table':
            try:
                fragment = json.loads(text)
                unit_headings = []
                for sibling in records:
                    meta = sibling.metadata
                    associations = meta.get('source_element_ids') or []
                    if isinstance(associations, str):
                        associations = json.loads(associations)
                    if (meta.get('document_name') == metadata.get('document_name')
                            and metadata.get('element_id') in associations
                            and meta.get('source_fidelity_verified')):
                        unit_headings.extend(re.findall(r'\bkPa\s*\([^\n)]+\)', content(sibling), re.I))
                # This is an explicit indexed source-element association, not a
                # similarity-based neighbour. All matching unit headings must agree.
                unit_headings = list(dict.fromkeys(unit_headings))
                if len(unit_headings) == 1:
                    fragment = {**fragment, 'notes': list(fragment.get('notes', []))
                                + ['Associated source unit heading: ' + unit_headings[0]]}
                    item['content'] = json.dumps(fragment, ensure_ascii=False)
                reference = next((r for r in references if r.get('document_name') == metadata.get('document_name')
                                  and r.get('element_id') == metadata.get('element_id')), None)
                if reference and reference.get('table_element'):
                    package = table_package(reference['table_element'], [fragment], remaining)
                    if package:
                        if len(unit_headings) == 1:
                            package['notes'] = list(package.get('notes', [])) + ['Associated source unit heading: ' + unit_headings[0]]
                        item['content'] = serialize_table(package)
                        item['evidence_type'] = 'table_cells_v2'
                else:
                    item['evidence_type'] = 'table_cells_v1'
            except (ValueError, KeyError, TypeError):
                result.omitted_sources.append(item['label'])
                continue
        size = len(item['content']) + len(item['title']) + 80
        if size > remaining:
            result.omitted_sources.append(item['label'])
            continue
        result.sources.append(item)
        remaining -= size
    return result
