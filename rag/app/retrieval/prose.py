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


def query_facets(question):
    """Bounded component queries, never a split on every occurrence of 'and'."""
    groups = [
        (r'\bwipers?\b', 'windscreen wiper inspection rubber streaks wet glass'),
        (r'\b(?:mirrors?|glass|windscreen)\b', 'windscreen glass mirrors visibility cleaning demister'),
        (r'\b(?:tyre|tire) pressure\b', 'tyre pressure cold manufacturer pressure gauge'),
        (r'\btread\b', 'tyre tread wear indicators shallow tread aquaplaning'),
        (r'\bcoolant\b', 'coolant level check cold engine reservoir lower upper markings hot cap'),
        (r'\b(?:engine oil|oil level|dipstick)\b', 'engine oil level dipstick inspection'),
        (r'\bbrake fluid\b', 'brake fluid reservoir level inspection'),
        (r'\b(?:washer fluid|windscreen washer|windshield washer)\b', 'windscreen washer fluid reservoir'),
        (r'\bbatter(?:y|ies)\b', 'vehicle battery inspection terminals condition'),
        (r'\b(?:preventive|corrective) maintenance\b', 'preventive corrective maintenance before failure owner checks professional repairs'),
        (r'\b(?:schedule|interval)\b.*\b(?:records?|mileage|dates?)\b|\b(?:records?|mileage|dates?)\b.*\b(?:schedule|interval)\b',
         'manufacturer maintenance schedule months kilometres whichever comes first service dates mileage records'),
        (r'\b(?:long trip|long journey|inter.state journey)\b', 'vehicle preparation long journey driver route weather service tyres'),
    ]
    facets = [query for pattern, query in groups if re.search(pattern, question, re.I)]
    # The glass mentioned in a wiper-only inspection is not a separate visibility task.
    if len(facets) > 1 and not re.search(r'\b(?:mirrors?|clean|visibility|demist|prepare the glass)\b', question, re.I):
        facets = [f for f in facets if not f.startswith('windscreen glass')]
    explicit = [part.strip() for part, ending in re.findall(r'([^?;]+)([?;]|$)', question)
                if len(part.split()) >= 3
                and not re.match(r'\s*(?:do not|don\x27t|avoid|no |I (?:do not|don\x27t|am not|don\x27t know))\b', part, re.I)
                and (ending in {'?', ';'} or re.match(
                    r'\s*(?:what|why|how|where|when|which|can|could|should|explain|describe|check|inspect)\b', part, re.I))]
    if len(explicit) > 1:
        return explicit[:8]
    coordinated = re.split(r'\band\s+(?=(?:what|how|why|when|where|which)\b)', question, flags=re.I)
    if len(coordinated) > 1:
        coordinated[0] = re.split(r'\b(?:explain|describe)\b', coordinated[0], maxsplit=1, flags=re.I)[-1]
        coordinated = [part.strip() for part in coordinated if len(part.split()) >= 4]
        if len(coordinated) > 1:
            return coordinated[:8]
    return facets if len(facets) > 1 or re.search(r'\bcoolant\b', question, re.I) else []


def select_prose(question, records, top_k, *, diagnostics=None):
    if top_k < 1:
        raise ValueError('top_k must be greater than 0')
    from rag.app.generation.context import content
    from rag.app.retrieval.hybrid import rerank
    from shared.safety import SOURCE_INJECTION
    candidates, seen = [], set()
    for record in sorted(records, key=lambda r: r.rank):
        key = (record.metadata.get('document_name'), normalized(record.metadata.get('source_content') or record.text))
        if key in seen:
            continue
        seen.add(key)
        section = record.metadata.get('section_path', [])
        if isinstance(section, str):
            section = json.loads(section)
        identity_text = ' '.join(section) + ' ' + content(record)
        if (re.search(r'\bcoolant\b', question, re.I)
                and not re.search(r'overheat|steam|temperature warning', question, re.I)
                and re.search(r'start the engine', content(record), re.I)
                and re.search(r'steam.{0,80}hood|hood.{0,80}steam', content(record), re.I)):
            continue  # A routine level check must not become an overheating/restart protocol.
        transmission = re.search(r'\b(manual|automatic)[- ]transmission\b', question, re.I)
        if transmission:
            other = 'automatic' if transmission[1].lower() == 'manual' else 'manual'
            if re.search(r'\b' + other + r' transmission\b', identity_text, re.I) and not re.search(
                    r'\b' + transmission[1] + r' transmission\b', identity_text, re.I):
                continue
        if not SOURCE_INJECTION.search(content(record)):
            candidates.append(record)
    transmission = re.search(r'\b(manual|automatic)[- ]transmission\b', question, re.I)
    if transmission:
        specific = [r for r in candidates if re.search(
            r'\b' + transmission[1] + r' transmission\b', r.text + ' ' + str(r.metadata.get('section_path', '')), re.I)]
        if specific:
            candidates = specific
    ranked = candidates
    facets = query_facets(question)
    state = 'disabled'
    facet_winners = []
    if settings.RAG_RERANK and len(candidates) > 1:
        try:
            originals = {r.chunk_id: r for r in candidates}
            search_records = [replace(r, text=r.text.split('Content:\n', 1)[0] + '\nContent:\n' + content(r)) for r in candidates]
            rankings = [rerank(question, search_records)] + [rerank(part, search_records) for part in facets]
            facet_winners = [(facet, ranking[0].chunk_id if ranking
                              and ranking[0].metadata['relevance_score'] >= -1 else None)
                             for facet, ranking in zip(facets, rankings[1:])]
            # Require a competitive match in at least one actual component query.
            scores = {}
            for ranking in rankings:
                best = ranking[0].metadata['relevance_score'] if ranking else -100
                for r in ranking:
                    score = r.metadata['relevance_score']
                    if score >= best - 2.5:
                        scores[r.chunk_id] = max(scores.get(r.chunk_id, -100), score)
            order = []
            for ranking in rankings:
                if ranking and ranking[0].chunk_id not in order:
                    order.append(ranking[0].chunk_id)
            order += [r.chunk_id for r in rankings[0] if r.chunk_id in scores and r.chunk_id not in order]
            if not facets and re.search(r'\b(?:check|checking|dipstick|procedure|sequence|replace|replacement)\b', question, re.I):
                procedures = [r for r in rankings[0]
                    if r.metadata.get('source_type', 'manual') == 'manual'
                    and r.metadata.get('document_type') in {'owners_manual','service_manual','maintenance_booklet'}
                    and r.metadata['relevance_score'] >= -1
                    and re.search(r'(?m)^\s*1[.)]\s', content(r))]
                if procedures:
                    first = procedures[0]
                    scores[first.chunk_id] = first.metadata['relevance_score']
                    order = [first.chunk_id] + [key for key in order if key != first.chunk_id]
            ranked = [replace(originals[key], metadata={**originals[key].metadata,
                       'relevance_score': scores.get(key, -100)}) for key in order]
            state = 'applied'
        except Exception as error:
            logger.warning('Text reranking unavailable (%s)', type(error).__name__)
            state = 'unavailable'
    # A directly relevant manufacturer procedure must not be blended with a
    # generic version of the same task (different preparation/labels/intervals).
    manual = [r for r in ranked if r.metadata.get('source_type', 'manual') == 'manual'
              and r.metadata.get('document_type') in {'owners_manual','service_manual','maintenance_booklet'}
              and (r.metadata.get('relevance_score', -100) >= -1)
              and re.search(r'(?m)^\s*1[.)]\s|\bwhichever (?:is |comes )?(?:first|earlier)\b', content(r), re.I)]
    if manual and not facets and re.search(r'\b(?:check|checking|dipstick|procedure|sequence|replace|replacement|how to)\b', question, re.I):
        ranked = manual + [r for r in ranked if r.metadata.get('source_type','manual') == 'manual' and r not in manual]
    selected = ranked[:top_k]
    if diagnostics is not None:
        selected_ids = {r.chunk_id for r in selected}
        diagnostics.update(text_reranking=state, text_candidate_count=len(candidates),
            retrieval_facets=[f'part_{i}' for i in range(1, len(facets) + 1)], manufacturer_priority=bool(manual),
            text_selection_limit=top_k,
            uncovered_facets=[f'part_{i}' for i, (_, winner) in enumerate(facet_winners, 1)
                              if winner not in selected_ids],
            text_rerank_order=[r.chunk_id for r in selected])
    return [replace(r, rank=i) for i,r in enumerate(selected,1)]
