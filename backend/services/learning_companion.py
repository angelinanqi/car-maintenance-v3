"""Resolve current published learning; client context never supplies evidence."""
from bs4 import BeautifulSoup
from fastapi import HTTPException

from backend import db
from datetime import datetime


def same_revision(left, right):
    if left == right:
        return True
    try:
        return datetime.fromisoformat(str(left).replace('Z', '+00:00')) == datetime.fromisoformat(str(right).replace('Z', '+00:00'))
    except ValueError:
        return False


def sections(content):
    """H2 sections keep stable IDs and include their subordinate headings/media."""
    soup = BeautifulSoup(content, 'html.parser')
    result = {}
    for heading in soup.find_all('h2'):
        identity = heading.get('data-section-id')
        if not identity:
            continue
        if identity in result:
            raise HTTPException(422, 'Guide section IDs must be unique.')
        parts = [str(heading)]
        for sibling in heading.next_siblings:
            if getattr(sibling, 'name', None) == 'h2':
                break
            parts.append(str(sibling))
        result[identity] = {'id': identity, 'title': heading.get_text(' ', strip=True), 'content': ''.join(parts)}
    return result


def published_guide(guide_id):
    guide = db.get('guides', guide_id)
    if guide['status'] != 'published' or (guide.get('category_id') and not db.get('guide_categories', guide['category_id'])['published']):
        raise HTTPException(404, 'This learning guide is no longer published.')
    return guide


def guide_step(guide, step_id):
    steps = (guide.get('exploration') or {}).get('steps', [])
    step = next((step for step in steps if step['id'] == step_id), None)
    section = sections(guide['content']).get(step['section_id']) if step else None
    if not section:
        raise HTTPException(409, 'This learning section changed. Reopen the guide to continue.')
    return {**step, **section, 'step_id': step['id']}


def validate_exploration(values):
    exploration = values.get('exploration')
    if not exploration:
        if values.get('featured_in_companion') and values['status'] == 'published':
            raise HTTPException(422, 'Add exploration steps before featuring this guide.')
        return
    available = sections(values['content'])
    if values['status'] != 'published':
        return
    for step in exploration['steps']:
        if step['section_id'] not in available:
            raise HTTPException(422, 'An exploration step refers to a missing H2 section. Select a current section.')
        activity = step.get('activity')
        if activity and (not activity['prompt'].strip() or any(not option['text'].strip() or not option['feedback'].strip() for option in activity['options'])):
            raise HTTPException(422, 'Complete the activity question, choices and feedback before publishing.')
    if values.get('featured_in_companion') and not values.get('description', '').strip():
        raise HTTPException(422, 'Add an introduction for the featured learning invitation.')


def resolve(reference, user, scope=None):
    if reference.kind == 'guide':
        guide = published_guide(reference.guide_id)
        if not same_revision(guide['updated_at'], reference.revision):
            raise HTTPException(409, 'This guide changed. Reopen it to use the current version.')
        if scope is not None and not any(source['source_type'] == 'learning_guide' and source['source_id'] == str(reference.guide_id)
                                         for source in scope.get('content_sources', [])):
            raise HTTPException(404, 'This guide is not available in the current conversation.')
        section = guide_step(guide, reference.step_id) if reference.step_id else {'title': guide['title'], 'content': guide['content']}
        # The complete published guide is separately supplied as citeable evidence.
        return {'kind': 'guide', 'title': guide['title'], 'section_title': section['title'],
                'source_id': str(reference.guide_id), 'revision': reference.revision}
    from backend.services.service_planning import get_plan
    plan = get_plan(user, str(reference.plan_id))
    if plan['stale'] or plan['fingerprint'] != reference.revision:
        raise HTTPException(409, 'Your service plan needs refreshing before using it in a new explanation.')
    return {'kind': 'plan', 'title': 'Your service plan', 'plan': plan['snapshot'], 'revision': plan['fingerprint']}


def discovery(user):
    categories = {row['id'] for row in db.all_rows('guide_categories', published=True)}
    guides = [guide for guide in db.all_rows('guides', status='published', order_by=('display_order', 'created_at', 'id'))
              if not guide.get('category_id') or guide['category_id'] in categories]
    eligible = {guide['id']: guide for guide in guides}
    featured = [{key: guide.get(key) for key in ('id', 'title', 'description', 'beginner_friendly', 'learning_outcomes', 'updated_at')}
                for guide in guides if guide.get('featured_in_companion') and guide.get('exploration')]
    progress = db.all_rows('learning_progress', user_id=user['id'], completed=False)
    resumable = []
    for row in sorted(progress, key=lambda item: item.get('updated_at', ''), reverse=True):
        guide = eligible.get(row['id'])
        if guide and row.get('current_step_id') and guide.get('exploration'):
            valid = {step['id'] for step in guide['exploration']['steps']}
            resumable.append({'guide_id': guide['id'], 'title': guide['title'], 'revision': guide['updated_at'],
                              'step_id': row['current_step_id'] if row['current_step_id'] in valid else guide['exploration']['steps'][0]['id'],
                              'changed': not same_revision(row.get('guide_revision'), guide['updated_at'])})
    return {'featured': featured[:3], 'resume': resumable[:1]}
