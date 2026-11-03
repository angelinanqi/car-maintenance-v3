"""Adapt authored guide HTML to the existing document/source-element pipeline."""
from hashlib import sha256
from html import escape
import json
from uuid import NAMESPACE_URL, uuid5
from urllib.parse import parse_qs, urlsplit
import re

from bs4 import BeautifulSoup
from shared.source_elements import FORMAT_VERSION, build_elements

ADAPTER_VERSION = 1


def revision(guide):
    # Publication and presentation-only changes do not require new embeddings.
    payload = [ADAPTER_VERSION, *[guide.get(key) for key in
               ('id', 'title', 'description', 'content', 'exploration', 'media')]]
    return str(uuid5(NAMESPACE_URL, json.dumps(payload, sort_keys=True, ensure_ascii=False)))


def video_id(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    if parsed.hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com',
                               'youtube-nocookie.com', 'www.youtube-nocookie.com', 'youtu.be'}:
        return None
    parts = parsed.path.strip('/').split('/')
    identity = (parts[0] if parsed.hostname == 'youtu.be' else
                parts[1] if len(parts) == 2 and parts[0] in {'embed', 'shorts', 'live'} else
                parse_qs(parsed.query).get('v', [''])[0])
    return identity if re.fullmatch(r'[A-Za-z0-9_-]{11}', identity) else None


def guide_html(guide):
    parts = [f'<p>{escape(guide.get("description") or "")}</p>', guide.get('content') or '']
    headings = {heading.get('data-section-id'): heading.get_text(' ', strip=True)
                for heading in BeautifulSoup(guide.get('content') or '', 'html.parser').find_all('h2')}
    for step in (guide.get('exploration') or {}).get('steps', []):
        if step.get('section_id') in headings:
            parts.append(f'<h2 data-section-id="{escape(step["section_id"], quote=True)}">'
                         + escape(headings[step['section_id']]) + '</h2>')
        parts.append(step.get('example_html') or '')
        activity = step.get('activity')
        if activity:
            parts.append('<p>' + escape(activity['prompt']) + '</p>')
            parts.extend('<p>' + escape(option['text'] + ': ' + option['feedback']) + '</p>'
                         for option in activity['options'])
    # Retain legacy manually added media, including items never embedded inline.
    soup = BeautifulSoup('\n'.join(parts), 'html.parser')
    urls = {tag.get('src') or tag.get('href') for tag in soup.find_all(['img', 'iframe', 'a'])}
    for media in guide.get('media') or []:
        if media['url'] not in urls:
            tag = soup.new_tag('img' if media['kind'] == 'image' else 'iframe', src=media['url'])
            tag['alt' if media['kind'] == 'image' else 'title'] = media['title']
            soup.append(tag)
            urls.add(media['url'])
    for tag in list(soup.find_all(['script', 'style', 'noscript', 'object'])):
        tag.decompose()
    # The shared parser groups top-level headings. Editor wrappers carry no meaning.
    for tag in list(soup.find_all(['div', 'section', 'article', 'figure', 'figcaption'])):
        tag.unwrap()
    return soup


def prepare_html(guide, load_image, *, describe_image=None):
    """Classify originals before prose chunking; reuse existing table extraction."""
    soup = guide_html(guide)
    headings, elements, media, videos, assets, warnings = [], [], [], {}, {}, []
    legacy = {item['url']: item for item in guide.get('media') or []}
    section_id = None
    for tag in list(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'img', 'iframe', 'a'])):
        if tag.parent is None:
            continue
        if re.fullmatch(r'h[1-6]', tag.name):
            level = int(tag.name[1])
            headings = [(depth, title) for depth, title in headings if depth < level]
            headings.append((level, tag.get_text(' ', strip=True)))
            if level <= 2:
                section_id = tag.get('data-section-id') if level == 2 else None
            continue
        if tag.name in {'iframe', 'a'}:
            url = tag.get('src' if tag.name == 'iframe' else 'href', '')
            identity = video_id(url)
            if identity:
                videos.setdefault(identity, {'video_id': identity, 'title': tag.get('title') or '',
                                              'url': url, 'section_id': section_id})
            if tag.name == 'iframe':
                if identity:
                    link = soup.new_tag('a', href=url)
                    link.string = tag.get('title') or url
                    paragraph = soup.new_tag('p')
                    paragraph.append(link)
                    tag.replace_with(paragraph)
                else:
                    tag.decompose()
            continue
        if tag.name == 'img' and tag.find_parent('table'):
            continue
        context = '\n'.join('#' * depth + ' ' + title for depth, title in headings)
        previous = tag.find_previous(['p', 'li'])
        context += '\n\n' + (previous.get_text(' ', strip=True) if previous else '') + '\n\n'
        original = str(tag)
        if tag.name == 'img':
            url = tag.get('src', '')
            try:
                data = load_image(url)
                digest = sha256(data).hexdigest()
                local = 'images/' + digest
                assets[local] = data
            except Exception as error:
                warnings.append(f'Image unavailable ({type(error).__name__}): {url[:160]}')
                tag.decompose()
                continue
            tag['src'] = local
        record = build_elements(context + str(tag))['elements'][0]
        record.update(element_id=f'{record["kind"]}-{len(elements):05d}', original_html=original,
                      section_id=section_id, context_origin='guide_html', source_offset=len(elements))
        if record['kind'] == 'image':
            item = legacy.get(url, {})
            record.update(asset_sha256=digest, asset_available=True, original_url=url,
                          vehicle_context=item.get('vehicle_context', ''),
                          media_id=str(item.get('id') or uuid5(NAMESPACE_URL,
                              guide['id'] + ':' + url + ':' + ' > '.join(title for _, title in headings))))
            if item.get('description'):
                # Retain administrator-authored descriptions without manufacturing review records.
                record['description'] = item['description']
                record['authored_description'] = True
            elif describe_image:
                try:
                    generated = describe_image(data)
                    record['generated_identity'] = {**generated['identity'], 'asset_sha256': digest}
                except Exception as error:
                    warnings.append(f'Image description unavailable ({type(error).__name__}): {url[:160]}')
            identity = record.get('generated_identity') or {}
            media.append(dict(id=record['media_id'], kind='image', url=url,
                title=item.get('title') or identity.get('title') or record['caption'] or 'Guide image',
                description=item.get('description') or identity.get('description') or record['caption'],
                vehicle_context=item.get('vehicle_context', ''), source_reference=item.get('source_reference', ''),
                section_id=section_id, reviewed=False, start_seconds=0, transcript=[]))
        elements.append(record)
        tag.decompose()  # Original evidence follows the shared asset path, never prose flattening.
    media_texts = []
    for item in guide.get('media') or []:
        if item['kind'] != 'video':
            continue
        item = dict(start_seconds=0, transcript=[], vehicle_context='', source_reference='', section_id=None,
                    description='', reviewed=False) | item
        media.append(item)
        description = item['description']
        for seconds, text in [(item['start_seconds'], description), *[
                (segment['start_seconds'], description + '\n' + segment['text']) for segment in item['transcript']]]:
            if text.strip():
                media_texts.append(dict(media_id=str(item['id']), start_seconds=seconds,
                                       text=item['title'] + '\n' + text))
    manifest = {'format_version': FORMAT_VERSION, 'elements': elements, 'source_type': 'html',
                'guide_media_texts': media_texts,
                'document_id': guide['id'], 'source_revision': revision(guide)}
    return str(soup), manifest, assets, media, list(videos.values()), warnings
