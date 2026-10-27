"""Source-preserving manual elements shared by extraction and indexing.

Descriptions are search aids, never interpreted specifications. Raw evidence
is retained separately from the restricted HTML used for display.
"""
import re
from hashlib import sha256
from html import escape
from pathlib import PurePosixPath

from bs4 import BeautifulSoup

FORMAT_VERSION = 2
ELEMENT_PATTERN = re.compile(
    r"<table\b[^>]*>.*?</table>|<img\b[^>]*>|!\[([^\]]*)\]\(([^\s)]+)(?:\s+[^)]*)?\)"
    r"|^[^\n]*\|[^\n]*\n[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*\n(?:[^\n]*\|[^\n]*(?:\n|$))*",
    re.I | re.S | re.M,
)
HEADING_PATTERN = re.compile(r'^\s*(#{1,6})\s+(.+)$', re.M)
ALLOWED_TAGS = {'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
                'caption', 'br', 'p', 'strong', 'b', 'em', 'i', 'sup', 'sub'}


def image_path(value):
    path = PurePosixPath(value)
    if (not value.startswith('images/') or path.is_absolute() or '..' in path.parts
            or '\\' in value or ':' in value or '?' in value or '#' in value):
        raise ValueError('Image reference must stay in the extraction images directory')
    return path.as_posix()


def sanitize_table(value):
    soup = BeautifulSoup(value, 'html.parser')
    for tag in list(soup.find_all(True)):
        if tag.parent is None:
            continue  # An unsafe ancestor already decomposed this descendant.
        if tag.name in {'script', 'style', 'iframe', 'object', 'img', 'svg'}:
            tag.decompose()
        elif tag.name not in ALLOWED_TAGS:
            tag.unwrap()
        else:
            attrs = {}
            if tag.name in {'td', 'th'}:
                for key in ('rowspan', 'colspan'):
                    try:
                        span = int(tag.get(key, 1))
                    except (TypeError, ValueError):
                        span = 1
                    attrs[key] = str(min(max(span, 1), 1000))
            tag.attrs = attrs
    return str(soup)


def table_cells(value):
    table = BeautifulSoup(value, 'html.parser').find('table')
    cells, occupied = [], set()
    rows = [r for r in table.find_all('tr') if r.find_parent('table') == table]
    valid = bool(rows) and table.find('table') is None
    for row_index, row in enumerate(rows):
        column = 0
        for cell in row.find_all(['td', 'th'], recursive=False):
            while (row_index, column) in occupied:
                column += 1
            try:
                rowspan, colspan = int(cell.get('rowspan', 1)), int(cell.get('colspan', 1))
                if not 1 <= rowspan <= 1000 or not 1 <= colspan <= 1000:
                    raise ValueError('Invalid span')
            except (TypeError, ValueError):
                rowspan, colspan, valid = 1, 1, False
            if row_index + rowspan > len(rows):
                valid = False
            for r in range(row_index, row_index + rowspan):
                for c in range(column, column + colspan):
                    if (r, c) in occupied:
                        valid = False
                    occupied.add((r, c))
            cells.append({'row': row_index, 'column': column,
                          'rowspan': rowspan, 'colspan': colspan,
                          'header': cell.name == 'th',
                          'text': cell.get_text(separator='\n', strip=True),
                          'original_html': str(cell)})
            column += colspan
    widths = [len({c for r, c in occupied if r == index}) for index in range(len(rows))]
    valid = valid and bool(widths) and len(set(widths)) == 1
    return cells, valid


def plain(value):
    return BeautifulSoup(value, 'html.parser').get_text(' ', strip=True).strip()


def build_elements(markdown):
    matches = list(ELEMENT_PATTERN.finditer(markdown))
    elements = []
    for index, match in enumerate(matches):
        raw = match.group(0)
        headings = []
        heading_end = 0
        for heading in HEADING_PATTERN.finditer(markdown, 0, match.start()):
            level = len(heading[1])
            headings = [h for h in headings if h[0] < level]
            headings.append((level, heading[2].strip()))
            heading_end = heading.end()
        # Immediate context cannot cross another element or a heading.
        left_start = max(matches[index - 1].end() if index else 0, heading_end)
        right_end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        next_heading = HEADING_PATTERN.search(markdown, match.end(), right_end)
        if next_heading:
            right_end = next_heading.start()
        left = markdown[left_start:match.start()]
        right = markdown[match.end():right_end]
        before = [plain(p) for p in re.split(r'\n\s*\n', left) if p.strip()][-2:]
        following = [plain(p) for p in re.split(r'\n\s*\n', right) if p.strip()]
        after = following[:3]
        context = [p for p in before + after if p and not p.startswith('#')]
        notes = [p for p in before + following if re.match(r'(?i)^(note|legend|key|remark|exception|\*|[●○◎])|^[A-Za-z]\s*[:=–-]', p)]
        notes = list(dict.fromkeys(notes))
        kind = 'image' if raw.lower().startswith('<img') or raw.startswith('![') else 'table'
        record = {'element_id': f'{kind}-{index:05d}', 'kind': kind,
                  'order': index, 'source_offset': match.start(),
                  'section_path': [h[1] for h in headings],
                  'context': context, 'notes': notes, 'pages': [],
                  'provenance_available': False, 'association_verified': False,
                  'caption': '', 'original_html': raw}
        record['context_origin'] = 'markdown_neighbours_unverified'
        record['notes_origin'] = 'nearby_text_unverified'
        if kind == 'table':
            table_html = raw
            if not raw.lower().startswith('<table'):
                lines = raw.strip().splitlines()
                html_rows = []
                for row_index, line in enumerate([lines[0]] + lines[2:]):
                    values = re.split(r'(?<!\\)\|', line.strip().strip('|'))
                    tag = 'th' if row_index == 0 else 'td'
                    html_rows.append('<tr>' + ''.join(f'<{tag}>{escape(v.strip().replace(chr(92) + "|", "|"))}</{tag}>' for v in values) + '</tr>')
                table_html = '<table>' + ''.join(html_rows) + '</table>'
                record['original_markdown'] = raw
            soup = BeautifulSoup(table_html, 'html.parser')
            caption = soup.find('caption')
            record['caption'] = caption.get_text(' ', strip=True) if caption else ''
            record['html'] = sanitize_table(table_html)
            record['cells'], record['structure_valid'] = table_cells(table_html)
            # MinerU commonly emits td-only schedules: item numbers occupy
            # column zero, with component/category labels in columns one/two.
            # Preserve those literal labels without embedding numerical values.
            labels = []
            # Prioritize left-hand category/component columns before long
            # detail cells, so later rows remain discoverable within the bound.
            for cell in sorted(record['cells'], key=lambda c: (c['column'], c['row'])):
                text = cell['text']
                if (cell['header'] or cell['column'] == 0
                        or (cell['column'] < 3 and re.search(r'[^\W\d_]', text)
                            and not re.search(r'\d', text))):
                    if text and text not in labels:
                        labels.append(text)
        else:
            image = BeautifulSoup(raw, 'html.parser').find('img') if raw.startswith('<') else None
            record['asset_path'] = image_path(image.get('src', '') if image else match[2])
            record['caption'] = image.get('alt', '') if image else match[1]
            labels = []
        if not record['caption']:
            captions = [p for p in context if re.match(r'(?i)^(table|figure|fig\.)\s*[\d:.-]', p)]
            record['caption'] = captions[0] if captions else ''
            record['caption_origin'] = 'nearby_text_unverified' if captions else 'missing'
        else:
            record['caption_origin'] = 'source_caption' if kind == 'table' else 'source_alt'
        # With no local prose, the existing heading/caption identifies the
        # original. Do not invent context from the neighbouring section.
        # A distant inherited heading is not evidence of a table/image topic.
        # Preserve the full path for attribution, but search the nearest heading.
        record['description'] = '\n'.join(record['section_path'][-1:] + [record['caption']]
                                         + labels + record['context'])[:1600]
        # Unlabelled images can still be associated with a retrieved paragraph.
        elements.append(record)
    return {'format_version': FORMAT_VERSION, 'elements': elements}


def public_element(record):
    """Exclude raw HTML, private asset paths and original cell markup."""
    fields = ('element_id', 'kind', 'caption', 'section_path', 'context', 'notes',
              'pages', 'bounding_boxes', 'provenance_available', 'association_verified', 'html', 'structure_valid')
    result = {key: record[key] for key in fields if key in record}
    if record.get('identity_review'):
        result['identity_review'] = {key: record['identity_review'][key] for key in
                                     ('title', 'description', 'uncertainty')}
    if record.get('generated_identity'):
        result['generated_identity'] = {key: record['generated_identity'][key] for key in
                                        ('title', 'description', 'uncertainty')}
    if 'cells' in record:
        result['cells'] = [{k: v for k, v in c.items() if k != 'original_html'} for c in record['cells']]
    return result


def add_provenance(manifest, metadata):
    """Use only exact source matches from MinerU content-list JSON.

    Unknown release schemas stay preserved as raw evidence. No ordering-based
    page guesses or visual proximity claims are made.
    """
    for data in metadata:
        if not isinstance(data, list):
            continue
        for source_index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            candidates = []
            for record in manifest['elements']:
                match = False
                if record['kind'] == 'table' and item.get('table_body'):
                    match = sanitize_table(item['table_body']) == record['html']
                elif record['kind'] == 'image' and item.get('img_path'):
                    match = item['img_path'] == record['asset_path']
                if match:
                    candidates.append(record)
            # Repeated identical tables cannot be mapped to pages by guessing.
            if len(candidates) != 1:
                continue
            for record in candidates:
                record.setdefault('source_records', []).append({
                    'schema': 'mineru_content_list_v1', 'index': source_index,
                    'page_idx': item.get('page_idx'), 'bbox': item.get('bbox'),
                })
                page = item.get('page_idx')
                if isinstance(page, int) and not isinstance(page, bool) and page >= 0:
                    record['pages'] = sorted(set(record['pages'] + [page + 1]))
                    record['provenance_available'] = True
                    if isinstance(item.get('bbox'), list):
                        record.setdefault('bounding_boxes', []).append({'page': page + 1, 'bbox': item['bbox'], 'coordinate_system': 'mineru-native'})
                prefix = 'table' if record['kind'] == 'table' else 'image'
                caption = item.get(prefix + '_caption')
                notes = item.get(prefix + '_footnote')
                if isinstance(caption, list) and caption and all(isinstance(c, str) for c in caption):
                    record['caption'] = '\n'.join(caption)
                    record['caption_origin'] = 'extractor_caption'
                if isinstance(notes, list) and all(isinstance(n, str) for n in notes):
                    record['notes'] = list(dict.fromkeys(record['notes'] + notes))
                    record['extractor_notes'] = notes.copy()
                    record['association_verified'] = False  # extraction association is not human verification
                # MinerU can put a diagram before its page headings in Markdown.
                # Recover bounded source context from explicit same-page boxes,
                # rather than dropping an otherwise identifiable uncaptioned asset.
                box = item.get('bbox')
                if (not record['context'] and isinstance(box, list) and len(box) == 4
                        and all(isinstance(v, (int, float)) for v in box)
                        and isinstance(page, int) and not isinstance(page, bool)):
                    neighbours = [entry for entry in data if isinstance(entry, dict)
                                  and entry.get('type') == 'text' and entry.get('page_idx') == page
                                  and isinstance(entry.get('text'), str)
                                  and isinstance(entry.get('bbox'), list) and len(entry['bbox']) == 4
                                  and all(isinstance(v, (int, float)) for v in entry['bbox'])]
                    before = sorted((e for e in neighbours if e['bbox'][3] <= box[1]),
                                    key=lambda e: e['bbox'][3])[-3:]
                    after = sorted((e for e in neighbours if e['bbox'][1] >= box[3]),
                                   key=lambda e: e['bbox'][1])[:1]
                    # Respect headings explicitly identified by the extractor.
                    # Keep the nearest preceding heading, but none of its predecessor's text.
                    start = 0
                    for index, entry in enumerate(before):
                        if isinstance(entry.get('text_level'), int) and entry['text_level'] > 0:
                            start = index
                    before = before[start:]
                    if after and isinstance(after[0].get('text_level'), int) and after[0]['text_level'] > 0:
                        after = []
                    record['context'] = [plain(e['text']) for e in before + after]
                    record['context_origin'] = 'same_page_vertical_neighbours_unverified'
                    record['description'] = '\n'.join([record['description']] + record['context'])[:1600]
                record['description'] = '\n'.join([record['caption'], record['description']] + record['notes'])[:1600]
                if record['kind'] == 'table' and isinstance(item.get('logical_table_id'), str):
                    record['logical_table_id'] = item['logical_table_id']
                    record['is_continuation'] = item.get('is_continuation') is True
                if record['kind'] == 'table' and item.get('img_path'):
                    try:
                        record['visual_asset_path'] = image_path(item['img_path'])
                    except ValueError:
                        pass
    groups = {}
    for record in manifest['elements']:
        if record.get('logical_table_id'):
            groups.setdefault(record['logical_table_id'], []).append(record)
    for parts in groups.values():
        if len(parts) < 2 or parts[0].get('is_continuation') or not all(p.get('is_continuation') for p in parts[1:]):
            continue
        first = parts[0]
        # Join only an explicitly declared logical table, retaining every part.
        first['parts'] = [{k: v for k, v in p.items() if k != 'parts'} for p in parts]
        first['original_html'] = '\n'.join(p['original_html'] for p in parts)
        contents = [BeautifulSoup(p['html'], 'html.parser').find('table').decode_contents() for p in parts]
        first['html'] = '<table>' + ''.join(contents) + '</table>'
        first['cells'], valid = table_cells(first['html'])
        first['structure_valid'] = valid and all(p['structure_valid'] for p in parts)
        first['pages'] = sorted({page for p in parts for page in p['pages']})
        first['notes'] = list(dict.fromkeys(note for p in parts for note in p['notes']))
        first['bounding_boxes'] = [box for p in parts for box in p.get('bounding_boxes', [])]
        first['description'] = '\n'.join(p['description'] for p in parts)[:1600]
        removed = {p['element_id'] for p in parts[1:]}
        manifest['elements'] = [p for p in manifest['elements'] if p['element_id'] not in removed]


def inspect_assets(manifest, directory):
    """Record availability and byte identity without claiming topic relevance."""
    missing = []
    for record in manifest['elements']:
        reference = record.get('asset_path') if record['kind'] == 'image' else record.get('visual_asset_path')
        if not reference:
            continue
        path = directory / image_path(reference)
        available = path.is_file() and not path.is_symlink()
        record['asset_available'] = available
        if available:
            record['asset_sha256'] = sha256(path.read_bytes()).hexdigest()
        else:
            missing.append(reference)
    manifest['asset_audit'] = {'missing': sorted(set(missing))}
    return manifest['asset_audit']
