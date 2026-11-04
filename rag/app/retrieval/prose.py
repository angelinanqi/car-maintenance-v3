"""Select prose jointly and recover bounded context from original OCR geometry.

No inferred parent headings: multi-column PDF reading order is not ancestry.
Only uniquely matched, complete passages acquire preceding same-column text.
The prepared index and literal source_content remain unchanged.
"""
from dataclasses import replace
from functools import lru_cache
from hashlib import sha256
import json
import logging
import re
import unicodedata

from rag.config import settings

logger = logging.getLogger(__name__)
GENERIC_HEADING = re.compile(r'(?:ww\s*)?(?:warning|caution|note|notice|danger)', re.I)


def normalized(text):
    text = unicodedata.normalize('NFKC', text).translate(str.maketrans(
        {'“': '"', '”': '"', '‘': "'", '’': "'"}))
    return ' '.join(text.split())


@lru_cache(maxsize=16)
def read_ocr(path, modified, size):
    raw = path.read_bytes()
    rows = json.loads(raw)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Unsupported OCR record format')
    return rows, sha256(raw).hexdigest()


def same_column(left, right):
    a, b = left.get('bbox', []), right.get('bbox', [])
    if (len(a) != 4 or len(b) != 4
            or not all(isinstance(value, (float, int)) for value in a + b)
            or a[2] <= a[0] or b[2] <= b[0]):
        return False
    overlap = min(a[2], b[2]) - max(a[0], b[0])
    # A full-width heading must not bridge two separate columns.
    width = a[2] - a[0]
    return (overlap > 0 and b[2] - b[0] <= width * 1.6
            and (abs(a[0] - b[0]) <= max(20, width * 0.15)
                 or overlap / max(width, b[2] - b[0]) >= 0.65))


def preceding_context(text, rows):
    """Return literal neighbouring evidence only for an unambiguous full match."""
    target = normalized(text)
    matches = []
    for index, row in enumerate(rows):
        literal = normalized(row.get('text', ''))
        if (row.get('type') != 'text' or not literal or not target.startswith(literal)
                or not isinstance(row.get('page_idx'), int)):
            continue
        column = [(i, item) for i, item in enumerate(rows)
                  if item.get('type') == 'text' and item.get('page_idx') == row.get('page_idx')
                  and same_column(row, item)]
        column.sort(key=lambda pair: (pair[1]['bbox'][1], pair[0]))
        position = next((j for j, (i, _) in enumerate(column) if i == index), None)
        if position is None:
            continue
        joined = ''
        for _, item in column[position:]:
            joined = (joined + ' ' + normalized(item.get('text', ''))).strip()
            if joined == target:
                matches.append((row, column[:position]))
                break
            if not target.startswith(joined):
                break
    if len(matches) != 1:
        return None
    row, previous = matches[0]
    selected, length = [], 0
    # Include complete blocks, stop at a heading identifying a different section.
    # Generic WARNING/NOTE headings do not identify a subject themselves.
    for index, item in reversed(previous):
        literal = item.get('text', '').strip()
        if length + len(literal) > 1800 or len(selected) >= 12:
            break
        selected.append((index, literal))
        length += len(literal)
        if item.get('text_level') and not GENERIC_HEADING.fullmatch(literal):
            break
    selected.reverse()
    if not selected:
        return None
    return dict(text='\n\n'.join(text for _, text in selected),
                pdf_page=row['page_idx'] + 1, ocr_record_indices=[i for i, _ in selected])


def recover_context(record):
    metadata = record.metadata
    section = metadata.get('section_path') or []
    if isinstance(section, str):
        try:
            section = json.loads(section)
        except ValueError:
            return record
    # Named sections already have a subject. Avoid expanding ordinary passages
    # with unrelated neighbouring procedures merely to enlarge the context.
    if not isinstance(section, list) or not section or not GENERIC_HEADING.fullmatch(section[-1]):
        return record
    key = metadata.get('document_name', '')
    # Indexed revision IDs only; never construct a file path from arbitrary titles.
    match = re.fullmatch(r'([0-9a-f-]{36})_([0-9a-f-]{36})', key)
    if not match or metadata.get('content_type') != 'paragraph':
        return record
    try:
        document_id, revision = match.groups()
        manifest = json.loads((settings.OUTPUT_DIR / 'sources' / f'{key}.json').read_text())
        if manifest.get('document_id') != document_id or manifest.get('source_revision') != revision:
            return record
        directory = settings.OUTPUT_DIR / 'documents' / document_id / 'ocr' / document_id / 'metadata'
        paths = list(directory.glob('*_content_list.json'))
        if len(paths) != 1:
            return record
        path = paths[0]
        stat = path.stat()
        rows, digest = read_ocr(path, stat.st_mtime_ns, stat.st_size)
        context = preceding_context(metadata.get('source_content', ''), rows)
        if not context:
            return record
        context.update(ocr_sha256=digest, ocr_path=str(path.relative_to(settings.OUTPUT_DIR)),
                       method='unique_complete_text_match_same_page_column')
        return replace(record, metadata={**metadata, 'preceding_source_context': context})
    except (OSError, ValueError, KeyError, TypeError):
        # Missing/unsupported OCR cannot manufacture a section association.
        return record


def select_prose(question, records, top_k, *, diagnostics=None):
    from rag.app.generation.context import content
    from rag.app.retrieval.hybrid import rerank
    from shared.safety import SOURCE_INJECTION

    candidates, seen = [], set()
    for record in sorted(records, key=lambda r: r.rank):
        key = (record.metadata.get('document_name'), normalized(
            record.metadata.get('source_content') or record.text))
        if key in seen:
            continue
        seen.add(key)
        enriched = recover_context(record)
        # Apply the same integrity rule to recovered text as original evidence.
        if SOURCE_INJECTION.search(content(enriched)):
            continue
        candidates.append(enriched)
    ranked = candidates
    state = 'disabled'
    if settings.RAG_RERANK and len(candidates) > 1:
        try:
            originals = {r.chunk_id: r for r in candidates}
            search_records = [replace(r, text=r.text.split('Content:\n', 1)[0]
                                     + '\nContent:\n' + content(r)) for r in candidates]
            rankings = [rerank(question, search_records)]
            # Explicit separate questions need evidence for each part. A single
            # pairwise score can favour one topic and bury the other entirely.
            # Keep this syntactic and bounded: no extra LLM calls or guessed facts.
            parts = [part.strip() for part in re.findall(r'[^?]+\?', question)]
            if len(parts) > 1:
                rankings.extend(rerank(part, search_records) for part in parts[:3])
            ranked, selected = [], set()
            for position in range(len(candidates)):
                for ranking in rankings:
                    if position < len(ranking) and ranking[position].chunk_id not in selected:
                        item = ranking[position]
                        ranked.append(replace(originals[item.chunk_id], rank=len(ranked) + 1))
                        selected.add(item.chunk_id)
            state = 'applied'
        except Exception as error:
            logger.warning('Text reranking unavailable; retaining hybrid order (%s)', type(error).__name__)
            state = 'unavailable'
    if diagnostics is not None:
        diagnostics.update(text_reranking=state, text_candidate_count=len(candidates),
            text_rerank_order=[r.chunk_id for r in ranked],
            text_context_recovered=[r.chunk_id for r in candidates
                                    if r.metadata.get('preceding_source_context')])
    return [replace(r, rank=i) for i, r in enumerate(ranked[:top_k], 1)]
