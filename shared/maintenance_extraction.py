"""Deterministic, revision-bound assistance without OCR, models or vector writes.

All results are suggestions. Callers must authorize and persist admin selections;
this module is not an authorization or schedule-publication boundary.
"""
from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
import logging
from pathlib import Path
import re
import tempfile
from uuid import UUID

VERSION = 1
logger = logging.getLogger(__name__)


def normalized(text):
    # Preserve punctuation, units and technical identifiers; only collapse whitespace.
    return ' '.join(text.split())


def identity(manifest):
    if manifest.get('format_version') != 2:
        raise ValueError('Unsupported source-element format')
    document = str(UUID(manifest['document_id']))
    revision = str(UUID(manifest['source_revision']))
    if manifest.get('source_type') not in {'pdf', 'md'}:
        raise ValueError('Expected a PDF or Markdown source')
    return document, revision


def rank_table(element):
    heading = ' '.join([element.get('caption', ''), *element.get('section_path', [])])
    context = ' '.join(element.get('context', []) + element.get('notes', []))
    body = ' '.join(c.get('text', '') for c in element.get('cells', []))
    reasons = []
    score = 0
    for text, pattern, weight, reason in (
        (heading, r'\b(maintenance|service|inspection)\s+schedule\b|\bperiodic\s+(maintenance|inspection)\b', 5, 'Schedule heading'),
        (heading + ' ' + context, r'\bmaintenance\b|\bservicing\b', 2, 'Maintenance context'),
        (body, r'\b(km|kilometres?|kilometers?|miles?|months?|years?)\b', 2, 'Interval units'),
        (body, r'\b(inspect|replace|check|lubricate|clean)\b', 1, 'Maintenance actions'),
    ):
        if re.search(pattern, text, re.I):
            score += weight
            reasons.append(reason)
    return {'score': score, 'classification': 'likely' if score >= 5 else 'possible' if score >= 2 else 'other',
            'reasons': reasons, 'method': 'rules', 'is_probability': False}


def build_catalogue(manifest):
    document, revision = identity(manifest)
    tables = []
    seen = set()
    for element in manifest['elements']:
        if element.get('kind') != 'table':
            continue
        table_id = element['element_id']
        if not re.fullmatch(r'table-\d{5,}', table_id) or table_id in seen:
            raise ValueError('Invalid or duplicate table identifier')
        seen.add(table_id)
        for key, expected in (('document_id', document), ('source_revision', revision)):
            if key in element and element[key] != expected:
                raise ValueError('Table belongs to another document revision')
        uncertainty = []
        if not element.get('structure_valid'):
            uncertainty.append('incomplete_table_structure')
        if manifest['source_type'] == 'pdf' and not element.get('pages'):
            uncertainty.append('page_unavailable')
        if not element.get('association_verified'):
            uncertainty.append('context_association_unverified')
        tables.append({
            'document_id': document, 'source_revision': revision, 'table_id': table_id,
            'source_type': manifest['source_type'],
            'title': element.get('caption') or next(iter(reversed(element.get('section_path', []))), ''),
            'pages': deepcopy(element.get('pages', [])),
            'bounding_boxes': deepcopy(element.get('bounding_boxes', [])),
            'source_offset': element.get('source_offset'),
            'ranking': rank_table(element), 'uncertainty': uncertainty,
            'review_status': 'unreviewed', 'source': deepcopy(element),
        })
    tables.sort(key=lambda t: (-t['ranking']['score'], t['table_id']))
    return {'assistance_version': VERSION, 'document_id': document, 'source_revision': revision,
            'source_type': manifest['source_type'], 'table_count': len(tables), 'tables': tables}


def suggest_matches(name, catalogue):
    key = normalized(name).casefold()
    matches = []
    for item in catalogue:
        if item.get('active', True) is False:
            continue
        candidate = normalized(item['title']).casefold()
        similarity = SequenceMatcher(None, key, candidate).ratio()
        if candidate == key or similarity >= .8:
            matches.append({'item_id': item['id'], 'title': item['title'],
                            'action': item.get('action'), 'category': item.get('category', ''),
                            'method': 'exact_text' if candidate == key else 'similar_text',
                            'similarity': round(similarity, 3), 'requires_confirmation': True})
    return sorted(matches, key=lambda m: (-m['similarity'], str(m['item_id'])))[:5]


def extract_items(catalogue, selection, standard_items=()):
    """Extract only explicitly confirmed tables/columns; never infer frequencies.

    selection: document_id, source_revision, tables: [{table_id, confirmed: true,
    columns: [zero-based column], excluded_rows: [zero-based row]}].
    Merged category cells are retained with uncertainty instead of propagated.
    """
    if any(selection.get(k) != catalogue[k] for k in ('document_id', 'source_revision')):
        raise ValueError('Selection belongs to another document revision')
    tables = {t['table_id']: t for t in catalogue['tables']}
    suggestions, selected = [], set()
    for choice in selection.get('tables', []):
        table_id = choice['table_id']
        if choice.get('confirmed') is not True or table_id not in tables or table_id in selected:
            raise ValueError('Select each existing table once and explicitly confirm it')
        selected.add(table_id)
        columns, excluded = choice.get('columns', []), choice.get('excluded_rows', [])
        if (not columns or any(type(v) is not int or v < 0 for v in columns + excluded)
                or len(columns) != len(set(columns))):
            raise ValueError('Provide distinct nonnegative item columns and excluded rows')
        table = tables[table_id]
        cells = table['source'].get('cells', [])
        available = {c['column'] for c in cells}
        if not set(columns) <= available:
            raise ValueError('Selected column has no extracted cells; use manual entry')
        rows = {}
        for cell in cells:
            if cell['column'] in columns and cell['row'] not in excluded and not cell.get('header'):
                rows.setdefault(cell['row'], []).append(cell)
        for row, row_cells in sorted(rows.items()):
            row_cells.sort(key=lambda c: columns.index(c['column']))
            texts = [c['text'] for c in row_cells]
            original = '\n'.join(texts)
            name = normalized(original)
            if not name:
                continue
            uncertainty = list(table['uncertainty'])
            if any(c.get('rowspan', 1) > 1 or c.get('colspan', 1) > 1 for c in row_cells):
                uncertainty.append('merged_label_cell')
            if not any(char.isalpha() for char in name) or len(name) < 3:
                uncertainty.append('incomplete_or_symbol_only_label')
            if re.search(r'^(note|legend|item|description|maintenance items?)\b', name, re.I):
                uncertainty.append('possible_header_or_note')
            suggestions.append({'suggestion_id': f'{table_id}:row-{row}',
                'document_id': catalogue['document_id'], 'source_revision': catalogue['source_revision'],
                'table_id': table_id, 'row': row, 'columns': [c['column'] for c in row_cells],
                'original_text': original, 'original_cells': deepcopy(row_cells),
                'suggested_name': name, 'pages': table['pages'], 'bounding_boxes': table['bounding_boxes'],
                'status': 'suggested', 'uncertainty': uncertainty, 'mapped_item_id': None,
                'catalogue_matches': suggest_matches(name, standard_items)})
    counts = Counter(s['suggested_name'].casefold() for s in suggestions)
    for suggestion in suggestions:
        suggestion['potential_duplicate'] = counts[suggestion['suggested_name'].casefold()] > 1
    return {'assistance_version': VERSION, 'document_id': catalogue['document_id'],
            'source_revision': catalogue['source_revision'], 'suggestions': suggestions}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare(manifest, output_dir):
    document, revision = identity(manifest)
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = Path(output_dir) / 'maintenance' / f'{document}_{revision}.json'
    try:
        cached = json.loads(path.read_text(encoding='utf-8'))
        if (cached.get('assistance_version') == VERSION and cached.get('source_digest') == fingerprint
                and cached.get('document_id') == document and cached.get('source_revision') == revision):
            return path
    except (OSError, ValueError, AttributeError):
        pass
    result = build_catalogue(manifest)
    result['source_digest'] = fingerprint
    write_json(path, result)
    return path


def prepare_safely(manifest, output_dir):
    """Optional artifact failures must never change indexing or publication state."""
    try:
        return prepare(manifest, output_dir)
    except Exception:
        logger.exception('Maintenance assistance failed; indexing is unaffected')
        return None
