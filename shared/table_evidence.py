"""Searchable table fragments retaining literal cell coordinates and spans."""
import json
import re


UNIT = r'kgf\s*/\s*cm[²2]|kpa|psi|bar|n[.·]?m|litres?|liters?|miles?|ml|mm|cm|km|l'
MEASUREMENT = re.compile(r'(?<![\w.,+-])([+-]?\d+(?:\.\d+)?)(?![\d.,])\s*(' + UNIT + r')(?!\w)', re.I)


def canonical_unit(unit):
    unit = re.sub(r'[\s.·]', '', unit.lower()).replace('²', '2')
    return 'l' if unit.startswith(('litre', 'liter')) else unit


def table_claim_error(text, table, question=''):
    """Verify literal measurements in their extracted row/column context.

    This is deliberately conservative about ambiguous conditions. It does not
    infer headers, convert units, or establish general semantic entailment.
    """
    measurements = list(MEASUREMENT.finditer(text))
    if not measurements:
        return None
    try:
        if 'cell_fields' in table:
            if table['cell_fields'] != list(CELL_FIELDS):
                return 'malformed_table'
            cells = [dict(zip(CELL_FIELDS, cell, strict=True)) for cell in table['cells']]
        else:
            cells = table['cells']
        if not isinstance(cells, list) or not cells:
            return 'malformed_table'
        for cell in cells:
            if (not isinstance(cell['text'], str) or type(cell['header']) is not bool
                    or any(type(cell[k]) is not int or not minimum <= cell[k] <= 10000
                    for k, minimum in (('row', 0), ('column', 0), ('rowspan', 1), ('colspan', 1)))):
                return 'malformed_table'
    except (KeyError, TypeError, ValueError):
        return 'malformed_table'
    headers = [c for c in cells if c['header'] or c['row'] == 0]
    data = [c for c in cells if c not in headers]
    identifiers = r'\b\d{3}/\d{2}[rR]\d{2}\b|\b(?:[A-Z]\d[A-Z]|\d[A-Z]{2})-[A-Z0-9]+\b'
    if any(re.search(r'\bengine\b', h['text'], re.I) for h in headers):
        identifiers += r'|(?<![\w.])\d\.\d\s*[lL]\b'
    condition_groups = (('front', 'rear'), ('cold', 'hot'), ('laden', 'unladen'),
                        ('loaded', 'unloaded'), ('manual', 'automatic'), ('normal load', 'full load'))
    all_text = table_literal_text(table)
    available_ids = set(re.findall(identifiers, all_text, re.I))
    available_ids = {re.sub(r'\s+', '', value.lower()) for value in available_ids}
    condition_words = set(' '.join(word for group in condition_groups for word in group).split())
    def label_words(value):
        return {word.lower() for word in re.findall(r'[a-zA-Z]{2,}', value)
                if word.lower() not in condition_words and word.lower() not in
                {'the', 'of', 'and', 'for', 'at', 'in', 'kpa', 'psi', 'bar', 'nm', 'litres', 'liters', 'ml', 'mm', 'cm', 'km'}}
    row_labels = [label_words(c['text']) for c in data if not re.search(r'\d', c['text'])]
    row_terms = set().union(*row_labels) if row_labels else set()
    for measurement in measurements:
        value, unit = measurement[1], canonical_unit(measurement[2])
        # Local clauses keep front/rear or loaded/unloaded values from borrowing
        # each other's qualifiers within the same sentence.
        start = max([0] + [m.end() for m in re.finditer(r';|,\s+(?=[a-z])|\band\b|\bbut\b',
                                                       text[:measurement.start()], re.I)])
        end_match = re.search(r';|\band\b|\bbut\b', text[measurement.end():], re.I)
        end = measurement.end() + end_match.start() if end_match else len(text)
        clause = text[start:end]
        local_terms = label_words(clause) & row_terms
        question_terms = label_words(question) & row_terms
        matched_labels = [label for label in row_labels if label and label.issubset(question_terms)]
        requested_terms = local_terms if len(matched_labels) > 1 else local_terms | question_terms
        local_ids = {re.sub(r'\s+', '', v.lower()) for v in re.findall(identifiers, clause, re.I)}
        question_ids = {re.sub(r'\s+', '', v.lower()) for v in re.findall(identifiers, question, re.I)}
        ids = local_ids | question_ids if len(question_ids) <= 1 else local_ids
        if len(available_ids) > 1 and not ids:
            return 'ambiguous_table_condition'
        candidates = []
        positions = ((cell, row) for cell in data for row in range(cell['row'], cell['row'] + cell['rowspan']))
        for cell, row in positions:
            column_headers = [h for h in headers if h['row'] <= cell['row']
                and h['column'] < cell['column'] + cell['colspan']
                and cell['column'] < h['column'] + h['colspan']]
            row_cells = [c for c in data if c['row'] <= row < c['row'] + c['rowspan']]
            context = ' '.join(c['text'] for c in column_headers + row_cells)
            literal = cell['text']
            pairs = [(m[1], canonical_unit(m[2])) for m in MEASUREMENT.finditer(literal)]
            if not pairs:
                numbers = re.findall(r'[+-]?\d+(?:\.\d+)?', literal)
                # A bare cell must contain values only, never a model/tyre label.
                if not re.fullmatch(r'[\d.\s(),/+-]+', literal):
                    continue
                unit_headers = [h for h in column_headers if re.search(r'(?<!\w)(?:' + UNIT + r')(?!\w)', h['text'], re.I)]
                if unit_headers:
                    nearest = sorted(unit_headers, key=lambda h: (h['colspan'], -h['row']))[0]['text']
                else:
                    nearest = '\n'.join(n.removeprefix('Associated source unit heading: ')
                        for n in table.get('notes', []) if n.startswith('Associated source unit heading: '))
                units = [canonical_unit(m[0]) for m in re.finditer(r'(?<!\w)(?:' + UNIT + r')(?!\w)', nearest, re.I)]
                if len(numbers) == len(units):
                    pairs = list(zip(numbers, units))
            if (value, unit) not in pairs:
                continue
            if not requested_terms.issubset(label_words(context)):
                continue
            compact_context = re.sub(r'\s+', '', context.lower())
            if ids and not all(identity in compact_context for identity in ids):
                continue
            valid = True
            for group in condition_groups:
                pattern = r'\b(?:' + '|'.join(group) + r')\b'
                local_conditions = set(re.findall(pattern, clause.lower()))
                question_conditions = set(re.findall(pattern, question.lower()))
                requested = (local_conditions | question_conditions if len(question_conditions) <= 1
                             else local_conditions)
                present = set(re.findall(pattern, context.lower())) or set(re.findall(pattern, table.get('caption', '').lower()))
                available = set(re.findall(pattern, all_text.lower()))
                if requested and available and not requested.issubset(present):
                    valid = False
                elif len(available) > 1 and not requested and len(present) == 1:
                    valid = False
            if valid:
                candidates.append(cell)
        if not candidates:
            return 'table_relationship_mismatch'
    return None


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
