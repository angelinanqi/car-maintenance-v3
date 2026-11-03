"""Bound OCR heading ancestry using the PDF's own outline and page metadata."""
from bisect import bisect_right
import hashlib
import re

from shared.source_elements import HEADING_PATTERN


def read_pdf_outline(path):
    from pypdf import PdfReader

    reader = PdfReader(path)
    entries = []

    def visit(items, parents):
        previous_title = None
        for item in items:
            if isinstance(item, list):
                if previous_title:
                    visit(item, parents + [previous_title])
                continue
            previous_title = ' '.join(str(item.get('/Title', '')).split())
            if not previous_title:
                continue
            page = reader.get_destination_page_number(item)
            if page is not None and 0 <= page < len(reader.pages):
                entries.append({'page': page, 'path': parents + [previous_title]})

    try:
        visit(reader.outline, [])
        return entries, len(reader.pages)
    finally:
        reader.close()


def _text(value):
    return ' '.join(value.split())


def _literal_heading(value):
    # PDF titles are literal strings, not Markdown or HTML instructions.
    return re.sub(r'([\\`*_\[\]<>])', r'\\\1', value)


def escape_literal_headings(markdown, content_list):
    """Escape heading markers inside uniquely located, declared plain text.

    A literal # in an OCR legend must not become Markdown structure. Unknown or
    repeated blocks are left alone; their location cannot be established here.
    """
    offsets = set()
    for entry in content_list:
        if entry.get('type') != 'text' or entry.get('text_level', 0):
            continue
        text = entry.get('text')
        if not isinstance(text, str) or not text or markdown.count(text) != 1:
            continue
        start = markdown.find(text)
        end = start + len(text)
        if (start and markdown[start - 1] != '\n'
                or not re.match(r'[ \t]*(?:\n|$)', markdown[end:])):
            continue
        for match in re.finditer(r'(?m)^ {0,3}(#{1,6})(?=[ \t])', text):
            offsets.add(start + match.start(1))
    for offset in sorted(offsets, reverse=True):
        markdown = markdown[:offset] + '\\' + markdown[offset:]
    return markdown, sorted(offsets)


def reconcile_headings(markdown, content_list, outline, page_count):
    """Create a processing copy; never guess heading identity or parent names.

    MinerU's ordered heading list must agree with the entire Markdown heading
    sequence. Empty metadata titles retain their ordered slot, but every
    available title and level must match. A mismatch disables the correction.
    """
    report = {'status': 'skipped', 'source_sha256': hashlib.sha256(markdown.encode('utf-8')).hexdigest(),
              'outline': outline}

    def skip(reason):
        report['reason'] = reason
        return markdown, report

    if not outline:
        return skip('No usable PDF outline')
    if any(not entry['path'] or len(entry['path']) > 6 for entry in outline):
        return skip('Outline exceeds supported Markdown heading depth')
    if any(a['page'] > b['page'] for a, b in zip(outline, outline[1:])):
        return skip('Outline destinations are not in document order')
    headings = list(HEADING_PATTERN.finditer(markdown))
    source_headings = [entry for entry in content_list
                       if entry.get('type') == 'text' and isinstance(entry.get('text_level'), int)
                       and entry['text_level'] > 0]
    if not headings or len(headings) != len(source_headings):
        return skip('OCR and Markdown heading counts differ')
    for heading, entry in zip(headings, source_headings):
        if (len(heading[1]) != entry['text_level']
                or not isinstance(entry.get('text'), str)
                or entry['text'] and _text(heading[2]) != _text(entry['text'])):
            return skip('OCR and Markdown heading sequence differs')
        page = entry.get('page_idx')
        if not isinstance(page, int) or not 0 <= page < page_count:
            return skip('Heading page metadata is unavailable')
    pages = [entry['page_idx'] for entry in source_headings]
    if pages != sorted(pages):
        return skip('Heading pages are not in document order')
    source_titles = {(entry['page_idx'], _text(entry['text'])) for entry in source_headings if entry['text']}
    anchors = [entry for entry in outline if (entry['page'], _text(entry['path'][-1])) in source_titles]
    report['outline_anchor_count'] = len(anchors)
    if not anchors:
        return skip('No outline destination matches a source heading')

    groups = {}
    for entry in outline:
        paths = groups.setdefault(entry['page'], [])
        if entry['path'] not in paths:
            paths.append(entry['path'])
    if any(len({path[0] for path in paths}) > 1 for paths in groups.values()):
        return skip('Shared outline destinations have no common parent')
    starts = sorted(groups)
    edits = []
    previous_scope = []
    changes = []
    heading_pages = []
    for heading, entry in zip(headings, source_headings):
        index = bisect_right(starts, entry['page_idx']) - 1
        if index < 0:
            heading_pages.append(entry['page_idx'] + 1)
            continue
        paths = groups[starts[index]]
        # A shared destination does not identify which sibling owns the text.
        # Keep only their common ancestry rather than selecting one arbitrarily.
        scope = []
        for titles in zip(*paths):
            if len(set(titles)) != 1:
                break
            scope.append(titles[0])
        title_is_scope = bool(scope and _text(heading[2]) == _text(scope[-1]))
        prefix = scope[:-1] if title_is_scope else scope
        level = len(scope) if title_is_scope else len(scope) + len(heading[1])
        if level > 6:
            return skip('Combined outline and local heading depth exceeds six')
        if scope != previous_scope:
            line_start = markdown.rfind('\n', 0, heading.start(1)) + 1
            inserted = ''.join('#' * depth + ' ' + _literal_heading(title) + '\n\n'
                               for depth, title in enumerate(prefix, start=1))
            if inserted:
                edits.append((line_start, line_start, inserted))
                heading_pages.extend([entry['page_idx'] + 1] * len(prefix))
            previous_scope = scope
        edits.append((heading.start(1), heading.end(1), '#' * level))
        heading_pages.append(entry['page_idx'] + 1)
        changes.append({'page': entry['page_idx'] + 1, 'title': heading[2].strip(),
                        'source_level': len(heading[1]), 'processing_level': level,
                        'outline_path': scope})
    derived = markdown
    for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        derived = derived[:start] + replacement + derived[end:]
    report.update(status='applied', headings=len(headings),
                  empty_metadata_titles=sum(not entry['text'] for entry in source_headings),
                  shared_destination_pages=[page + 1 for page, paths in groups.items() if len(paths) > 1],
                  headings_review=changes, heading_pages=heading_pages)
    return derived, report
