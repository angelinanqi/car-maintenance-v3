"""Current published learning and reviewed emergency content for chat retrieval."""
from bs4 import BeautifulSoup

from backend import db


def guide_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Flattening table cells loses their relationships and bypasses the
    # display-only policy. Keep surrounding prose as answer evidence.
    for element in soup.find_all(['script', 'style', 'iframe', 'noscript', 'table']):
        element.decompose()
    # Keep ordered instructions numbered, rather than flattening them into prose.
    for listing in soup.find_all(['ol', 'ul']):
        for number, item in enumerate(listing.find_all('li', recursive=False), 1):
            item.insert(0, f'{number}. ' if listing.name == 'ol' else '- ')
    return soup.get_text('\n', strip=True)


def load(scope_type, scope_id):
    categories = {row['id']: row for row in db.all_rows('guide_categories', published=True)}
    sources = []
    for guide in db.all_rows('guides', status='published'):
        category_id = guide.get('category_id')
        if category_id and category_id not in categories:
            continue
        if scope_type == 'category' and category_id not in {None, str(scope_id)}:
            continue
        body = guide_text(guide['content'])
        for step in (guide.get('exploration') or {}).get('steps', []):
            if step.get('example_html'):
                body += '\n\n' + guide_text(step['example_html'])
            if step.get('activity'):
                activity = step['activity']
                body += '\n\n' + activity['prompt']
                body += '\n' + '\n'.join(option['text'] + ': ' + option['feedback'] for option in activity['options'])
        if not body:
            continue  # Images alone cannot establish textual instructions.
        sources.append({
            'source_type': 'learning_guide', 'source_id': guide['id'],
            'title': guide['title'], 'category_id': category_id,
            'content': '\n\n'.join(text for text in [guide.get('description', ''), body] if text),
            'revision': guide['updated_at'],
        })
    for protocol in db.all_rows('emergency_playbooks', status='published'):
        if not (protocol.get('reviewed_at') and protocol.get('source', '').strip()
                and protocol.get('scenario_key') and protocol.get('steps')):
            continue
        parts = []
        if protocol.get('description'):
            parts.append('Situation: ' + protocol['description'])
        if protocol.get('safety_warnings'):
            parts.append('Safety warnings: ' + protocol['safety_warnings'])
        for number, step in enumerate(protocol['steps'], 1):
            parts.append(f"{number}. {step['title']}\n{step['description']}")
        sources.append({
            'source_type': 'emergency_protocol', 'source_id': protocol['id'],
            'title': protocol['title'], 'content': '\n\n'.join(parts),
            'revision': protocol['updated_at'], 'reviewed_at': protocol['reviewed_at'],
            'scenario_key': protocol['scenario_key'], 'source_reference': protocol['source'],
        })
    return sorted(sources, key=lambda source: (source['source_type'], source['source_id']))
