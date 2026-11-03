"""One-off, additive HTML import. Run from the repository root; --apply persists.
Extra import-only dependency: resvg-py==0.5.0. Never updates existing content.
"""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import UUID, uuid5, NAMESPACE_URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
from backend import db, settings
from backend.models import CategoryInput, GuideInput, PlaybookInput
from backend.routes.guides import validate_guide
from backend.routes.emergency import publish_playbook, PlaybookReview, mobile_playbook
from backend.services.content_uploads import validate_image, store_upload
from backend.services.emergency_media import validate_steps
from shared.content_media import ContentMedia

SOURCE = 'malaysian_car_maintenance_road_safety.html'
PREFIX = 'road-safety-html-v1:'


def identity(key):
    return str(uuid5(NAMESPACE_URL, PREFIX + key))


def text(node):
    return node.get_text(' ', strip=True)


def html(node):
    """Adapt wrappers/headings to the actual TipTap/mobile schema, retaining words."""
    node = deepcopy(node)
    for tag in list(node.find_all(['figure', 'article', 'section', 'header'])):
        tag.unwrap()
    for tag in node.find_all(['figcaption', 'div']):
        if not tag.find(['p', 'div', 'ul', 'ol', 'img', 'h1', 'h2', 'h3', 'h4']):
            tag.name = 'p'
        else:
            tag.unwrap()
    for tag in node.find_all(['h4', 'h5', 'h6']):
        tag.name = 'h3'
    for tag in node.find_all('b'):
        tag.name = 'strong'
    for tag in node.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in {'href', 'src', 'alt', 'id', 'start'}}
    return ''.join(str(child) for child in node.contents)


def parse(path):
    soup = BeautifulSoup(path.read_text(), 'html.parser')
    categories, guides, playbooks = [], [], []
    sections = [s for s in soup.select('section.category') if s.get('id') != 'emergency-guides']
    for i, section in enumerate(sections):
        cat = dict(id=identity(section['id']), **CategoryInput(name=text(section.h2), display_order=i).model_dump())
        categories.append(cat)
        for article in section.select('article.article'):
            guides.append(dict(id=identity(article['id']), title=text(article.h3), category_id=cat['id'],
                               display_order=len(guides), node=deepcopy(article)))
    # Preserve library context and resource notes without inventing categories.
    overview = BeautifulSoup('<div></div>', 'html.parser').div
    header = deepcopy(soup.find('header', id='overview'))
    for action in header.select('.actions'): action.decompose()
    overview.append(header)
    main = soup.find('main')
    for child in main.find_all(recursive=False):
        if child.name == 'p' and 'footer' not in child.get('class', []): overview.append(deepcopy(child))
    resources = deepcopy(soup.find('section', id='resources'))
    footer = soup.select_one('.footer')
    if footer: resources.append(deepcopy(footer))
    for key, title, node in [('overview', text(header.h1), overview), ('resources', text(resources.h2), resources)]:
        guides.append(dict(id=identity(key), title=title, category_id=categories[-1]['id'], display_order=len(guides), node=node))
    emergency = soup.find(id='emergency-guides')
    universal = text(emergency.find('div', recursive=False))
    for i, article in enumerate(emergency.select('article.emergency')):
        steps = []
        warning = article.find('div', class_='callout', recursive=False)
        for j, step in enumerate(article.select('div.step')):
            body = deepcopy(step)
            title = text(body.h4)
            body.h4.decompose()
            # Emergency descriptions are plain text; keep paragraph/caption boundaries.
            description = '\n\n'.join(text(n) for n in body.find_all(['p', 'figcaption'], recursive=True))
            steps.append(dict(id=identity(f"{article['id']}:step:{j}"), title=title,
                              description=description, media=[], imageUrl='', node=deepcopy(step)))
        for j, tail in enumerate(article.find_all('p', recursive=False)):
            label = tail.find('b')
            title = text(label) if label else 'Sources'
            # Links are retained explicitly because the emergency reader uses plain text.
            description = text(tail)
            for a in tail.find_all('a'): description += '\n' + a['href']
            steps.append(dict(id=identity(f"{article['id']}:closing:{j}"), title=title,
                              description=description, media=[], imageUrl='', node=None))
        playbooks.append(dict(id=identity(article['id']), title=text(article.h3), display_order=i,
                              scenario_key=article['id'], category=text(emergency.h2),
                              description=universal, safety_warnings=text(warning),
                              source=f'{path.name}#{article["id"]}', steps=steps))
    assert len(guides) == 31 and len(playbooks) == 6
    assert sum(len(p['steps']) for p in playbooks) == 55
    assert sum(len(g['node'].find_all('img')) for g in guides) + sum(len(st['node'].find_all('img')) for p in playbooks for st in p['steps'] if st['node']) == len(soup.find_all('img')) == 70
    return soup, categories, guides, playbooks


def raster(image):
    import resvg_py
    source = image['src']
    if not source.startswith('data:image/svg+xml;base64,'):
        raise ValueError('Unexpected asset; refusing to silently omit: ' + source[:120])
    svg = base64.b64decode(source.split(',', 1)[1], validate=True)
    png = resvg_py.svg_to_bytes(svg_string=svg.decode(), skip_system_fonts=True)
    validate_image(png, extension='.png', bounded=True)
    return png


def ensure(table, values):
    rows = db.all_rows(table, id=values['id'])
    if rows:
        if any(rows[0].get(k) != v for k, v in values.items()):
            raise ValueError(f'Existing {table}/{values["id"]} differs; refusing overwrite')
        return rows[0]
    return db.insert(table, values)


def asset(parent, image, step=None):
    data = raster(image)
    key = identity(f'{parent}:{step or "guide"}:{sha256(data).hexdigest()}')
    path = f'{"emergency" if step else "guides"}/{parent}/{"media" if step else "images"}/{key}.png'
    table = 'emergency_media_assets' if step else 'guide_images'
    values = dict(id=key, storage_path=path)
    if step:
        values.update(playbook_id=parent, step_id=step, kind='image', mime_type='image/png',
                      size_bytes=len(data), sha256=sha256(data).hexdigest())
    else:
        values['guide_id'] = parent
    existing = db.all_rows(table, id=key)
    if existing:
        if any(existing[0].get(k) != v for k, v in values.items()): raise ValueError('Asset conflict')
        url = db.bucket(settings.SUPABASE_CONTENT_BUCKET).get_public_url(path)
    else:
        # Recover an upload that completed before registration was interrupted.
        bucket = db.bucket(settings.SUPABASE_CONTENT_BUCKET)
        try:
            old = bucket.download(path)
        except Exception as error:
            if getattr(error, 'status', None) not in (400, 404) and 'not found' not in str(error).lower():
                raise
            old = None
        if old is not None:
            if old != data: raise ValueError('Storage asset conflict')
            db.insert(table, values)
            url = bucket.get_public_url(path)
        else:
            url = store_upload(data, path, 'image/png', table, values)['url']
    return values, url


def run(path, apply):
    soup, categories, guides, playbooks = parse(path)
    report = dict(source=path.name, source_sha256=sha256(path.read_bytes()).hexdigest(),
                  learning_topics=len(categories), learning_guides=len(guides), emergency_scenarios=len(playbooks),
                  emergency_procedure_steps=41, emergency_total_steps=55, diagrams=70,
                  youtube_link_occurrences=sum('youtube.com' in a.get('href', '') for a in soup('a')),
                  mappings=[], applied=apply)
    # Validate all required fields and render every image before making any writes.
    for guide in guides:
        GuideInput(**{k:v for k,v in guide.items() if k not in {'id', 'node'}},
                   content=html(guide['node']), status='draft')
    for playbook in playbooks:
        payload = {k:v for k,v in playbook.items() if k != 'id'}
        payload['steps'] = [{k:v for k,v in step.items() if k != 'node'} for step in playbook['steps']]
        PlaybookInput(**payload, status='draft')
    for image in soup('img'): raster(image)
    if not apply: return report
    # Reuse exact existing category names; never rename or publish someone else's category.
    existing_categories = db.all_rows('guide_categories')
    for category in categories:
        matches = [r for r in existing_categories if r['name'].casefold() == category['name'].casefold()]
        if len(matches) > 1: raise ValueError('Ambiguous category ' + category['name'])
        if matches:
            old = category['id']; category['id'] = matches[0]['id']
            if not matches[0]['published'] or matches[0].get('archived'): raise ValueError('Matching category is hidden')
            for guide in guides:
                if guide['category_id'] == old: guide['category_id'] = category['id']
        else: ensure('guide_categories', category)
    for guide in guides:
        node = guide.pop('node')
        # Parent first: storage registration has a guide foreign key.
        existing = db.all_rows('guides', id=guide['id'])
        if not existing:
            # Also avoid duplicate titles from unrelated imports.
            if any(r['title'] == guide['title'] for r in db.all_rows('guides')): raise ValueError('Existing guide title collision')
            ensure('guides', dict(id=guide['id'], **GuideInput(**{k:v for k,v in guide.items() if k != "id"}, status='draft').model_dump(mode='json')))
        for image in node('img'):
            _, image['src'] = asset(guide['id'], image)
        content = html(node)
        assert text(BeautifulSoup(content, 'html.parser')) == text(node)
        values = validate_guide(GuideInput(**{k:v for k,v in guide.items() if k != "id"}, content=content, status='published', beginner_friendly=True).model_dump(mode='json'), guide['id'])
        current = db.get('guides', guide['id'])
        if current['status'] == 'published':
            if any(current.get(k) != v for k, v in values.items()): raise ValueError('Published guide differs; refusing overwrite')
        else:
            # A partial import draft may only contain our empty initial content or final content.
            if current['content'] not in ('<p></p>', content): raise ValueError('Draft edited; refusing overwrite')
            db.update('guides', guide['id'], dict(**values, published_at=datetime.now(timezone.utc).isoformat()))
        assert db.get('guides', guide['id'])['content'] == content
        report['mappings'].append(dict(module='learning', title=guide['title'], id=guide['id'], category_id=guide['category_id']))
        print('Verified guide:', guide['title'], flush=True)
    for playbook in playbooks:
        nodes = [step.pop('node') for step in playbook['steps']]
        initial = PlaybookInput(**{k:v for k,v in playbook.items() if k != "id"}, status="draft").model_dump(mode='json')
        existing = db.all_rows('emergency_playbooks', id=playbook['id'])
        if not existing:
            if any(r['scenario_key'] == playbook['scenario_key'] or r['title'] == playbook['title'] for r in db.all_rows('emergency_playbooks')): raise ValueError('Existing emergency collision')
            db.insert('emergency_playbooks', dict(id=playbook['id'], **initial, reviewed_at=None))
        for step, node in zip(playbook['steps'], nodes):
            if node is None: continue
            for image in node('img'):
                stored, url = asset(playbook['id'], image, step['id'])
                caption = text(image.find_parent('figure').figcaption)
                media = ContentMedia(id=stored['id'], asset_id=stored['id'], kind='image', url=url,
                    title=image.get('alt', step['title']), description=caption, reviewed=True,
                    source_reference=playbook['source'], sha256=stored['sha256'], size_bytes=stored['size_bytes'], mime_type='image/png')
                step['media'].append(media.model_dump(mode='json'))
        values = PlaybookInput(**{k:v for k,v in playbook.items() if k != "id"}).model_dump(mode='json', exclude={'status'})
        validate_steps(playbook['id'], values['steps'])
        current = db.get('emergency_playbooks', playbook['id'])
        if current['status'] == 'published':
            if any(current.get(k) != v for k, v in values.items()): raise ValueError('Published emergency differs; refusing overwrite')
        else:
            if current['steps'] not in (initial['steps'], values['steps']): raise ValueError('Draft emergency edited; refusing overwrite')
            current = db.update('emergency_playbooks', playbook['id'], values)
            publish_playbook(UUID(playbook['id']), PlaybookReview(confirm_review=True, expected_updated_at=current['updated_at']))
        saved = db.get('emergency_playbooks', playbook['id'])
        assert saved['status'] == 'published' and saved['steps'] == values['steps']
        assert len(mobile_playbook(saved)['steps']) == len(saved['steps']) + 2
        report['mappings'].append(dict(module='emergency', title=playbook['title'], id=playbook['id'], steps=len(saved['steps'])))
        print('Verified emergency:', playbook['title'], flush=True)
    report['verification'] = 'Persisted fields compared exactly; emergency publication validation and mobile adapter passed.'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(SOURCE))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, default=Path('output/road-safety-import.json'))
    args = parser.parse_args()
    result = run(args.source, args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'mappings'}, indent=2))
