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
    return re.sub(r"^Image source:.*$", "", text, flags=re.M)


def bounded_history(history, budget=None):
    """Keep the newest contiguous exchanges, with no partial messages."""
    budget = settings.RAG_CONTEXT_CHARS // 2 if budget is None else budget
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
            break
        selected.insert(0, exchange)
        budget -= size
    return [message for exchange in selected for message in exchange]


def maintenance_source(context, budget):
    """Retain whole server-ordered entries, totals and an explicit coverage note."""
    result = {key: context[key] for key in ("vehicle_id", "as_of", "total_tasks", "total_standalone_services")}
    result.update(tasks=[], standalone_services=[], entries_omitted=False)
    if encoded_size(json.dumps(result, ensure_ascii=False)) > budget:
        return None
    for key in ("tasks", "standalone_services"):
        for entry in context[key]:
            result[key].append(entry)
            if encoded_size(json.dumps(result, ensure_ascii=False)) > budget:
                result[key].pop()
                break
    result["entries_omitted"] = any(len(result[key]) < len(context[key])
                                    for key in ("tasks", "standalone_services"))
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
        return bool(self.omitted_sources or self.incomplete_section_labels
                    or any(source.get('table_complete') is False for source in self.sources))


def prepare_context(records, references, vehicle_profile=None, maintenance_context=None, *, image_sources=None):
    """Prioritize each original's evidence and report any factual omissions.

    Labels retain their positions in the caller's records, even when items are
    skipped. Descriptions may be shortened because they are search aids; factual
    evidence is included whole or omitted. No question-specific relevance rules.
    """
    result = GenerationContext()
    remaining = settings.RAG_CONTEXT_CHARS
    reference_allowance = remaining // 4 // max(1, len(references))
    reference_identities = {reference['label']: (reference.get('document_name'), reference.get('element_id'))
                            for reference in references}
    table_elements = {reference['label']: reference['table_element'] for reference in references
                      if reference.get('table_element')}
    pixel_labels = {reference['label']: reference.get('pixel_source_label', reference['label'])
                    for reference in references}
    for reference in references:
        # Internal join keys need not consume the model's description budget.
        item = {key: value for key, value in reference.items()
                if key not in {'document_name', 'element_id', 'table_element', 'source_label', 'pixel_source_label'}}
        if reference.get('kind') == 'table':
            # Repeated navigation paths can consume the entire preview allowance.
            # Literal captions and cell previews identify tables; inherited paths
            # remain in factual-source metadata, not promoted to table captions.
            item['title'] = reference.get('source_label') or 'Original table'
        while encoded_size(item) > reference_allowance and item.get("description"):
            excess = encoded_size(item) - reference_allowance
            item["description"] = item["description"][:-excess]
        result.references.append(item)

    # Bound personal data without letting it consume the entire manual budget.
    personal_budget = remaining // 2
    if vehicle_profile:
        item = {"label": "P1", "document_type": "personal_vehicle_profile",
                "content": json.dumps(vehicle_profile, ensure_ascii=False)}
        if encoded_size(item) <= personal_budget:
            result.sources.append(item)
            personal_budget -= encoded_size(item)
            remaining -= encoded_size(item)
        else:
            result.omitted_sources.append("P1")
    if maintenance_context:
        # Account for the source wrapper as well as its JSON text.
        item = {"label": "P2", "document_type": "personal_maintenance", "content": ""}
        text = maintenance_source(maintenance_context, max(0, personal_budget - encoded_size(item)))
        item["content"] = text
        if text is not None and encoded_size(item) <= personal_budget:
            result.sources.append(item)
            remaining -= encoded_size(item)
        else:
            result.omitted_sources.append("P2")

    seen = set()
    sections = {}
    manual_sources = []
    source_metadata = {}
    for index, record in enumerate(records, 1):
        kind = record.metadata.get('content_type', 'paragraph')
        structured_table = (kind == 'table' and record.metadata.get('evidence_type') == 'table_cells_v1'
                            and record.metadata.get('structure_valid') is True)
        if kind != 'paragraph' and not structured_table:
            continue
        metadata = record.metadata
        text = content(record)
        section_path = metadata.get("section_path") or []
        if isinstance(section_path, str):
            section_path = json.loads(section_path)
        identity = (metadata.get("source_type", "manual"),
                    metadata.get("document_id") or metadata.get("source_id") or metadata.get("document_name"),
                    metadata.get("document_name"), metadata.get("parent_id"),
                    metadata.get("section_chunk_index") if metadata.get("section_chunk_count", 1) > 1 else None,
                    tuple(section_path), metadata.get('element_id'), text)
        if identity in seen:
            continue
        seen.add(identity)
        item = {"label": f"S{index}",
                "title": metadata.get("title") or metadata.get("document_title") or metadata.get("document_name", "Reference"),
                "source_type": metadata.get("source_type", "manual"),
                "document_type": metadata.get("document_type", "other_reference"),
                "content_type": kind,
                "source_fidelity_verified": metadata.get("source_fidelity_verified", False),
                "section_path": section_path,
                "content": text}
        if structured_table:
            item['evidence_type'] = 'table_cells_v1'
            item['element_id'] = metadata['element_id']
            item['extraction_warning'] = ('Cell positions and spans are extracted, not independently verified. '
                'Use explicit headers, units, conditions and notes. Do not guess missing header relationships.')
        if metadata.get("section_chunk_count", 1) > 1:
            item["section_fragment"] = {
                "index": metadata["section_chunk_index"],
                "count": metadata["section_chunk_count"],
                # Reserve this field's size before packing. True is smaller
                # than False in JSON, so updating coverage cannot exceed budget.
                "all_chunks_supplied": False,
            }
        manual_sources.append(item)
        source_metadata[item['label']] = metadata
        if "section_fragment" in item:
            section_key = (metadata.get("document_name"), metadata.get("parent_id"))
            if not all(section_key):
                # A display heading is not a unique section identity. Without
                # source IDs, retain each fragment as its own incomplete group.
                section_key = (None, item["label"])
            sections.setdefault(section_key, []).append(item)

    # Source identity, not caption similarity, associates a table with its cells.
    # Keep validated display references independent of factual evidence. Reserve
    # their metadata before packing sources; missing cells never imply the
    # original itself is unavailable or authorize facts from its description.
    references_to_pack = result.references
    result.references = []
    for reference in references_to_pack:
        reference.update(evidence_labels=[], evidence_omitted=False)
        size = encoded_size(reference)
        if size > remaining:
            result.omitted_references.append(reference['label'])
            continue
        result.references.append(reference)
        remaining -= size
    grouped_labels = set()
    packed_pixels = set()
    table_references = {}
    # Pixel metadata is small and independent of extracted-cell size. A large
    # OCR fragment must not prevent inspection of an otherwise fitting original.
    for reference in result.references:
        for source in image_sources or []:
            if source['label'] != pixel_labels[reference['label']]:
                continue
            grouped_labels.add(source['label'])
            extra = encoded_size([source['label']]) - encoded_size([])
            size = extra + (0 if source['label'] in packed_pixels else encoded_size(source))
            if size > remaining:
                reference['evidence_omitted'] = True
                result.omitted_sources.append(source['label'])
                continue
            if source['label'] not in packed_pixels:
                result.sources.append(source)
                packed_pixels.add(source['label'])
            reference['evidence_labels'].append(source['label'])
            remaining -= size
    package_count = sum(reference['label'] in table_elements for reference in result.references)
    for reference in result.references:
        document_name, element_id = reference_identities[reference['label']]
        table_sources = [source for source in manual_sources
                         if source.get('evidence_type') == 'table_cells_v1'
                         and document_name
                         and source_metadata[source['label']].get('document_name') == document_name
                         and source.get('element_id') == element_id]
        element = table_elements.get(reference['label'])
        if element and table_sources:
            # Give each selected table a share before duplicate fragments/prose.
            # Whole small tables expand through the existing element identity.
            allowance = remaining // max(1, package_count)
            package_count -= 1
            source = dict(table_sources[0])
            source['evidence_type'] = 'table_cells_v2'
            source['table_complete'] = False
            source['content'] = ''
            extra = (encoded_size(reference['evidence_labels'] + [source['label']])
                     - encoded_size(reference['evidence_labels']))
            fragments = [json.loads(item['content']) for item in table_sources]
            package = table_package(element, fragments, allowance - encoded_size(source) - extra)
            grouped_labels.update(item['label'] for item in table_sources)
            if package is None:
                reference['evidence_omitted'] = True
                result.omitted_sources.extend(item['label'] for item in table_sources)
                continue
            source['content'] = serialize_table(package)
            source['table_complete'] = package['complete']
            result.sources.append(source)
            reference['evidence_labels'].append(source['label'])
            reference['evidence_omitted'] = reference['evidence_omitted'] or not package['complete']
            remaining -= encoded_size(source) + extra
            continue
        if element:
            package_count -= 1
        group = table_sources[:1]
        grouped_labels.update(source['label'] for source in group)
        if group:
            previous_size = encoded_size(reference)
            reference['evidence_labels'].extend(source['label'] for source in group)
        else:
            previous_size = encoded_size(reference)
        size = (encoded_size(reference) - previous_size
                + sum(encoded_size(source) for source in group))
        if size > remaining:
            if group:
                reference['evidence_labels'] = reference['evidence_labels'][:-len(group)]
            reference['evidence_omitted'] = True
            omitted = table_sources
            grouped_labels.update(source['label'] for source in omitted)
            result.omitted_sources.extend(source['label'] for source in omitted)
            continue
        result.sources.extend(group)
        table_references.update((source['label'], reference) for source in table_sources[1:])
        remaining -= size

    for source in manual_sources:
        if source['label'] in grouped_labels:
            continue
        reference = table_references.get(source['label'])
        extra = (encoded_size({**reference, 'evidence_labels': reference['evidence_labels'] + [source['label']]})
                 - encoded_size(reference)) if reference else 0
        if encoded_size(source) + extra > remaining:
            result.omitted_sources.append(source['label'])
            if reference:
                reference['evidence_omitted'] = True
            continue
        result.sources.append(source)
        remaining -= encoded_size(source) + extra
        if reference:
            reference['evidence_labels'].append(source['label'])
    for source in image_sources or []:
        if source['label'] not in grouped_labels:
            result.omitted_sources.append(source['label'])

    # Coverage describes the final packed input, not merely retrieved records.
    supplied_labels = {source['label'] for source in result.sources}
    for reference in result.references:
        if reference.get('page_region', {}).get('source_label') not in supplied_labels:
            reference.pop('page_region', None)
    for items in sections.values():
        items = [item for item in items if item['label'] in supplied_labels]
        if not items:
            continue
        counts = {item["section_fragment"]["count"] for item in items}
        indexes = {item["section_fragment"]["index"] for item in items}
        count = items[0]["section_fragment"]["count"]
        supplied = (len(counts) == 1 and len(indexes) == count
                    and all(1 <= index <= count for index in indexes))
        for item in items:
            item["section_fragment"]["all_chunks_supplied"] = supplied
    result.incomplete_section_labels = [
        item["label"] for item in result.sources
        if item.get("section_fragment", {}).get("all_chunks_supplied") is False
    ]
    return result
