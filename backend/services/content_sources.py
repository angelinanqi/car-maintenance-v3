"""Current published learning and reviewed emergency content for chat retrieval."""
from backend import db
from shared.safety import SOURCE_INJECTION
from shared.content_media import ContentMedia, timestamp_url


def reviewed_media(items, **context):
    """Validate stored records again; unreviewed media never becomes evidence."""
    result = []
    for raw in items or []:
        item = ContentMedia.model_validate(raw)
        if item.reviewed and (item.kind != 'video' or item.asset_id):
            result.append({**item.model_dump(mode='json'), **context})
    return result


def load(scope_type, scope_id):
    from backend.services.guide_indexing import index_rows, current
    categories = {row['id']: row for row in db.all_rows('guide_categories', published=True)}
    indexes = index_rows()
    sources = []
    for guide in db.all_rows('guides', status='published'):
        category_id = guide.get('category_id')
        if category_id and category_id not in categories:
            continue
        if scope_type == 'category' and category_id not in {None, str(scope_id)}:
            continue
        index = indexes.get(guide['id'])
        if not current(guide, index):
            continue
        media = index.get('media') or []
        from backend.services.learning_companion import sections
        available_sections = sections(guide['content']) if any(item['section_id'] for item in media) else {}
        for item in media:
            item['section_title'] = available_sections.get(item['section_id'], {}).get('title', '')
        sources.append({
            'source_type': 'learning_guide', 'source_id': guide['id'],
            'title': guide['title'], 'category_id': category_id,
            'content': '', 'indexed': True, 'index_revision': index['source_revision'],
            'chunk_count': index['chunk_count'], 'videos': index.get('videos') or [],
            'revision': guide['updated_at'],
            'media': media,
        })
    sources.extend(emergency_sources())
    return sorted(sources, key=lambda source: (source['source_type'], source['source_id']))


def emergency_sources():
    from backend.services.guide_indexing import index_rows, current
    protocols = db.all_rows('emergency_playbooks', status='published')
    indexes = index_rows(emergency=True) if protocols else {}
    sources = []
    for protocol in protocols:
        if not is_reviewed_protocol(protocol):
            continue
        index = indexes.get(protocol['id'])
        sources.append(emergency_source(protocol, index if current(protocol, index, emergency=True) else None))
    return sorted(sources, key=lambda source: source['source_id'])


def is_reviewed_protocol(protocol):
    return bool(protocol.get('status') == 'published' and protocol.get('reviewed_at')
                and (protocol.get('source') or '').strip() and protocol.get('scenario_key')
                and protocol.get('steps'))


def emergency_source(protocol, index=None):
    parts = []
    media = []
    if protocol.get('description'):
        parts.append('Situation: ' + protocol['description'])
    if protocol.get('safety_warnings'):
        parts.append('Safety warnings: ' + protocol['safety_warnings'])
    for number, step in enumerate(protocol['steps'], 1):
        parts.append(f"{number}. {step['title']}\n{step['description']}")
        media.extend(reviewed_media(step.get('media'), step_id=step['id'], step_order=number,
                                    step_title=step['title']))
    return {
        'source_type': 'emergency_protocol', 'source_id': protocol['id'],
        'title': protocol['title'], 'content': '\n\n'.join(parts),
        'indexed': True, 'index_ready': index is not None,
        'index_revision': index['source_revision'] if index else None,
        'chunk_count': index['chunk_count'] if index else 0,
        'revision': protocol['updated_at'], 'reviewed_at': protocol['reviewed_at'],
        'scenario_key': protocol['scenario_key'], 'source_reference': protocol['source'],
        'media': media,
    }


def resolve_content_media(citations, sources, *, emergency=False):
    """Resolve published guide media and reviewed emergency media from current sources."""
    current = {(s['source_type'], s['source_id']): s for s in sources}
    result, seen = [], set()
    for citation in citations:
        source = current.get((citation.get('source_type'), citation.get('source_id')))
        if not source or citation.get('revision') != source['revision']:
            continue
        for media in source.get('media', []):
            if source['source_type'] != 'learning_guide' and not media.get('reviewed'):
                continue
            # Normal answers attach only the media whose text was cited. Urgent
            # replies can illustrate their complete, reviewed protocol.
            if not emergency and citation.get('media_id') != media['id']:
                continue
            seconds = citation.get('start_seconds', media['start_seconds'])
            allowed = {media['start_seconds'], *[segment['start_seconds'] for segment in media['transcript']]}
            if type(seconds) is not int or seconds not in allowed:
                continue
            identity = (source['source_type'], source['source_id'], media['id'], seconds)
            if identity in seen:
                continue
            seen.add(identity)
            result.append({key: source[key] for key in ('source_type', 'source_id', 'revision', 'title')}
                          | {'media_id': media['id'], 'kind': media['kind'], 'title': media['title'],
                             'description': media['description'], 'vehicle_context': media['vehicle_context'],
                             'source_reference': media['source_reference'], 'section_id': media['section_id'],
                             'step_id': media.get('step_id'), 'step_title': media.get('step_title'),
                             'step_order': media.get('step_order'),
                             'url': timestamp_url(media['url'], seconds), 'start_seconds': seconds,
                             'source_label': citation.get('label'),
                             **{key: media[key] for key in ('asset_id', 'sha256', 'size_bytes', 'mime_type') if media.get(key) is not None}})
            if len(result) == 5:
                return result
    return result


def emergency_supplement(source):
    if SOURCE_INJECTION.search(source['title'] + '\n' + source['content']):
        return '', []
    citation = {key: source[key] for key in (
        'source_type', 'source_id', 'title', 'revision', 'reviewed_at', 'source_reference')}
    citation['label'] = 'S1'
    return ('Reviewed emergency protocol: ' + source['title'] + ' [S1]\n\n'
            + source['content']), [citation]


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
