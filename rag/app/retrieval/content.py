"""Hybrid retrieval over the backend's current published content snapshot."""
from functools import lru_cache
from dataclasses import replace
import json
from rag.app.generation.grounded import INJECTION
from rag.app.retrieval.hybrid import lexical_search, fuse
from rag.app.retrieval.search import RetrievalResult
from shared.safety import emergency_topics


def records_for(sources, *, include_media=True, include_indexed=False):
    records = []
    for source in sources:
        if source.get('indexed') and not include_indexed:
            continue  # Already searched as scoped persistent chunks, never re-embed in chat.
        text = source['title'] + '\n' + source.get('scenario_key', '').replace('-', ' ') + '\n' + source['content']
        if INJECTION.search(text):
            continue
        metadata = {**{key: value for key, value in source.items() if key != 'media'}, 'document_type': source['source_type'],
                    'document_name': source['title'], 'source_content': source['content'],
                    'content_type': 'paragraph', 'source_fidelity_verified': False,
                    'vehicle_independent': True}
        records.append(RetrievalResult(0, f"{source['source_type']}:{source['source_id']}", 0.0,
                                       text, metadata))
        if not include_media:
            continue
        for media in source.get('media', []):
            if not media.get('reviewed'):
                continue
            heading = '\n'.join(part for part in [source['title'], media['title'], media.get('step_title'), media.get('section_title'),
                                media.get('vehicle_context')] if part)
            description = f"Reviewed {media['kind']} description: {media['description']}"
            segments = [(media.get('start_seconds', 0), description)]
            segments.extend((segment['start_seconds'], description + '\nTranscript: ' + segment['text'])
                            for segment in media.get('transcript', []))
            for index, (seconds, passage) in enumerate(segments):
                evidence = heading + '\n' + passage
                if INJECTION.search(evidence):
                    continue
                media_metadata = {**metadata, 'source_content': evidence, 'media_id': media['id'],
                                  'start_seconds': seconds}
                records.append(RetrievalResult(0,
                    f"{source['source_type']}:{source['source_id']}:media:{media['id']}:{index}",
                    0.0, evidence, media_metadata))
    return records


@lru_cache(maxsize=8)
def snapshot_embeddings(texts):
    # Only embeddings of published content are cached, never queries or personal data.
    # Changed content produces a new key; current revision metadata is never cached.
    from rag.app.embedding.embedder import embed_documents
    return embed_documents(texts)


def retrieve_content(query, sources, top_k=5, *, query_embedding=None):
    if not sources:
        return []
    records = records_for(sources)
    lexical = lexical_search(query, records, max(top_k, 20))
    if query_embedding is None or not records:
        return lexical[:top_k]
    try:
        embeddings = snapshot_embeddings(tuple(r.text for r in records))
    except Exception:
        # Oversized/temporarily unavailable guide embeddings retain lexical search.
        return lexical[:top_k]
    scored = [(sum(a * b for a, b in zip(query_embedding, vector)), record)
              for record, vector in zip(records, embeddings)]
    dense = [replace(record, rank=i, distance=1 - score)
             for i, (score, record) in enumerate(sorted(scored, key=lambda item: -item[0]), 1)]
    return fuse(dense, lexical)[:top_k]


def retrieve_emergency(query, sources):
    requested = emergency_topics(query)
    matching = [s for s in sources if s['source_type'] == 'emergency_protocol'
                and requested & emergency_topics(s.get('scenario_key', '') + ' ' + s['title'])]
    # Never select a protocol merely because its warnings mention another hazard.
    records = records_for(matching, include_media=False, include_indexed=True)
    if len(records) < 2:
        return records
    ranked = lexical_search(query, records, 1) if records else []
    return ranked or records[:1]


def public_source(record, label):
    metadata = record.metadata
    section = metadata.get('section_path', [])
    if isinstance(section, str):
        section = json.loads(section)
    return {'label': label, 'source_type': metadata['source_type'],
            'source_id': metadata['source_id'], 'title': metadata['title'],
            'revision': metadata['revision'], 'reviewed_at': metadata.get('reviewed_at'),
            'source_reference': metadata.get('source_reference', ''),
            **{key: metadata[key] for key in ('media_id', 'start_seconds', 'step_id', 'step_order') if key in metadata},
            **({'chunk_id': record.chunk_id, 'section_path': section} if section else {})}


def render_emergency(records):
    parts = []
    for number, record in enumerate(records, 1):
        metadata = record.metadata
        # Diagram descriptions are navigation metadata, not additional safety
        # instructions. Keep the published advice verbatim and its source in the
        # existing citation card rather than exposing internal reference paths.
        text = '\n'.join(line for line in metadata['source_content'].splitlines()
                         if not line.strip().startswith('Diagram reference:'))
        parts.append(f"Reviewed emergency protocol: {metadata['title']} [S{number}]\n\n"
                     + text.strip())
    return '\n\n'.join(parts)
