"""Searchable table fragments retaining literal cell coordinates and spans."""
import json


CELL_FIELDS = ('row', 'column', 'rowspan', 'colspan', 'header', 'text')


def serialize_table(package):
    """Encode the same literal cells with one shared field declaration.

    This is an answer-context representation, not an extraction/index format.
    Source cells, positions, spans and text are unchanged.
    """
    compact = dict(package)
    compact['cell_fields'] = list(CELL_FIELDS)
    compact['cells'] = []
    for cell in package['cells']:
        compact['cells'].append([cell[field] for field in CELL_FIELDS])
    return json.dumps(compact, ensure_ascii=False, separators=(',', ':'))


def table_literal_text(table):
    """Read literal values from either source encoding, excluding coordinates."""
    texts = [table.get('caption', '')]
    if 'cell_fields' in table:
        if table['cell_fields'] != list(CELL_FIELDS):
            raise ValueError('Unsupported table cell field order')
        for cell in table['cells']:
            texts.append(cell[5])
    else:
        texts.extend(cell['text'] for cell in table['cells'])
    texts.extend(table.get('notes', []))
    return '\n'.join(texts)


def table_reference_text(element):
    """Literal identification aid; factual answers still need structured cells."""
    texts = [element.get('caption', '')]
    cells = sorted(element.get('cells', []), key=lambda cell: (not cell['header'], cell['row'], cell['column']))
    texts.extend(cell['text'] for cell in cells if cell['text'])
    return '\n'.join(dict.fromkeys(text for text in texts if text))


def table_fragments(element, max_chars=2000):
    """Group whole rows; repeat explicit headers and cells spanning a boundary.

    No header, unit, condition or value is inferred. Oversized rows/notes stay
    whole so the existing embedding/context limits can report their omission.
    """
    if not element.get('structure_valid') or not element.get('cells'):
        return []
    cells = [{key: cell[key] for key in
              ('row', 'column', 'rowspan', 'colspan', 'header', 'text')}
             for cell in element['cells']]
    last_row = max(cell['row'] + cell['rowspan'] for cell in cells)
    headers = [cell for cell in cells if cell['header']]

    def fragment(start, end):
        included = [cell for cell in cells if
                    start <= cell['row'] < end or
                    cell['row'] < start < cell['row'] + cell['rowspan'] or
                    cell in headers]
        return {'element_id': element['element_id'],
                'row_range': [start, end - 1], 'total_rows': last_row,
                'caption': element.get('caption', ''),
                'cells': included, 'notes': element.get('notes', []),
                'extractor_notes': element.get('extractor_notes', []),
                'notes_origin': element.get('notes_origin', 'nearby_text_unverified'),
                'coordinate_system': 'zero_based; spans are explicit extraction geometry'}

    groups = []
    start = 0
    for end in range(1, last_row + 1):
        candidate = fragment(start, end)
        if end > start + 1 and len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
            groups.append(fragment(start, end - 1))
            start = end - 1
    groups.append(fragment(start, last_row))
    return groups


def table_search_text(fragment):
    """Literal values participate in the same text search as manual passages."""
    rows = {}
    for cell in fragment['cells']:
        rows.setdefault(cell['row'], []).append(cell)
    lines = [fragment['caption']]
    for row, cells in sorted(rows.items()):
        values = [f"column {cell['column']}: {cell['text']}"
                  for cell in sorted(cells, key=lambda c: c['column'])]
        lines.append(f"Row {row}: " + ' | '.join(values))
    lines.extend(fragment['notes'])
    return '\n'.join(lines)


def table_package(element, fragments, max_chars):
    """Fit whole tables first, otherwise whole retrieved rows with source context.

    The first source row is retained even in td-only extraction, without calling
    it a header. Explicit headers and cells spanning selected rows are retained.
    The limit measures JSON-string size because the package is source content.
    """
    if not element.get('structure_valid') or not element.get('cells'):
        return None
    cells = [{key: cell[key] for key in ('row', 'column', 'rowspan', 'colspan', 'header', 'text')}
             for cell in element['cells']]
    total_rows = max(cell['row'] + cell['rowspan'] for cell in cells)

    def package(rows):
        selected = [cell for cell in cells if cell['header'] or cell['row'] == 0
                    or any(row in rows for row in range(cell['row'], cell['row'] + cell['rowspan']))]
        supplied_rows = sorted(rows | {0} | {cell['row'] for cell in cells if cell['header']})
        return {'element_id': element['element_id'], 'total_rows': total_rows,
                'supplied_rows': supplied_rows, 'complete': len(supplied_rows) == total_rows,
                'caption': element.get('caption', ''), 'cells': selected,
                'notes': element.get('notes', []), 'extractor_notes': element.get('extractor_notes', []),
                'notes_origin': element.get('notes_origin', 'nearby_text_unverified'),
                'coordinate_system': 'zero_based; spans are explicit extraction geometry'}

    def fits(value):
        text = serialize_table(value)
        return len(json.dumps(text, ensure_ascii=False)) <= max_chars

    whole = package(set(range(total_rows)))
    if fits(whole):
        return whole
    rows = set()
    for fragment in fragments:
        if fragment.get('element_id') != element['element_id']:
            continue
        start, end = fragment['row_range']
        # Try the coherent retrieved range first; only split at row boundaries.
        candidate_rows = rows | set(range(start, end + 1))
        if fits(package(candidate_rows)):
            rows = candidate_rows
            continue
        for row in range(start, end + 1):
            if fits(package(rows | {row})):
                rows.add(row)
    return package(rows) if rows else None
