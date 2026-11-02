"""Current published learning and reviewed emergency content for chat retrieval."""
from bs4 import BeautifulSoup

from backend import db
from shared.safety import emergency_topics, SOURCE_INJECTION


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
    sources.extend(emergency_sources())
    return sorted(sources, key=lambda source: (source['source_type'], source['source_id']))


def emergency_sources():
    sources = []
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
    return sorted(sources, key=lambda source: source['source_id'])


def emergency_supplement(question, sources):
    """Add one real reviewed protocol; basic safety does not depend on it."""
    topics = emergency_topics(question)
    for source in sources:
        if (not topics.intersection(emergency_topics(source['scenario_key'] + ' ' + source['title']))
                or SOURCE_INJECTION.search(source['title'] + '\n' + source['content'])):
            continue
        citation = {key: source[key] for key in (
            'source_type', 'source_id', 'title', 'revision', 'reviewed_at', 'source_reference')}
        citation['label'] = 'S1'
        return ('\n\nReviewed emergency protocol: ' + source['title'] + ' [S1]\n\n'
                + source['content'] + '\n\nSource reference: ' + source['source_reference']), [citation]
    return '', []


def resolve_guide_recommendations(recommendations, sources, *, strict=False):
    """Resolve supplementary reading independently of factual citations."""
    guides = {source['source_id']: source for source in sources if source['source_type'] == 'learning_guide'}
    result = []
    seen = set()
    for item in recommendations:
        identity = item.get('source_id') if isinstance(item, dict) else None
        guide = guides.get(identity) if isinstance(identity, str) else None
        if not guide or item.get('revision') != guide['revision']:
            if strict:
                raise ValueError('Recommended guide is unpublished, ineligible or stale')
            continue
        if guide['source_id'] in seen:
            continue
        result.append({key: guide[key] for key in ('source_id', 'title', 'revision')})
        seen.add(guide['source_id'])
        if len(result) == 2:
            break
    return result
