"""Lexical retrieval over the backend's current published content snapshot."""
from rag.app.generation.grounded import INJECTION, words
from rag.app.retrieval.hybrid import lexical_search
from rag.app.retrieval.search import RetrievalResult
import re


def records_for(sources):
    records = []
    for source in sources:
        text = source['title'] + '\n' + source.get('scenario_key', '').replace('-', ' ') + '\n' + source['content']
        if INJECTION.search(text):
            continue
        metadata = {**source, 'document_type': source['source_type'],
                    'document_name': source['title'], 'source_content': source['content'],
                    'content_type': 'paragraph', 'source_fidelity_verified': False}
        records.append(RetrievalResult(0, f"{source['source_type']}:{source['source_id']}", 0.0,
                                       text + '\n' + ' '.join(words(text)), metadata))
    return records


def retrieve_content(query, sources, top_k=5):
    if not sources:
        return []
    return lexical_search(query + ' ' + ' '.join(words(query)), records_for(sources), top_k)


def hazards(text):
    text = text.lower().replace('-', ' ')
    result = set()
    if re.search(r'\boverheat\w*', text):
        result.add('overheating')
    if re.search(r'\bfire\b', text):
        result.add('fire')
    if re.search(r'\b(fuel|petrol|gasoline)\b', text) and re.search(r'\b(leak\w*|smell)\b', text):
        result.add('fuel-leak')
    if re.search(r'\bbrakes?\b', text) and re.search(r'\b(fail\w*|floor|not working|stopped working|no longer work|don.t work|won.t work)\b', text):
        result.add('brake-failure')
    return result


def retrieve_emergency(query, sources):
    requested = hazards(query)
    matching = [s for s in sources if s['source_type'] == 'emergency_protocol'
                and requested & hazards(s.get('scenario_key', '') + ' ' + s['title'])]
    # Never select a protocol merely because its warnings mention another hazard.
    records = records_for(matching)
    if len(records) < 2:
        return records
    ranked = lexical_search(query, records, 1) if records else []
    return ranked or records[:1]


def public_source(record, label):
    metadata = record.metadata
    return {'label': label, 'source_type': metadata['source_type'],
            'source_id': metadata['source_id'], 'title': metadata['title'],
            'revision': metadata['revision'], 'reviewed_at': metadata.get('reviewed_at'),
            'source_reference': metadata.get('source_reference', '')}


def render_emergency(records):
    parts = []
    for number, record in enumerate(records, 1):
        metadata = record.metadata
        parts.append(f"Reviewed emergency protocol: {metadata['title']} [S{number}]\n\n"
                     + metadata['source_content'] + '\n\nSource reference: '
                     + metadata['source_reference'])
    return '\n\n'.join(parts)
