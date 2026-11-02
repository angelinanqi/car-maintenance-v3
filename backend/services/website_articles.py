"""Bounded public-page fetching and article snapshots, without browser execution."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from hashlib import sha256
from http.client import HTTPConnection, HTTPSConnection, HTTPException as HTTPClientError
from io import BytesIO
import ipaddress
import re
import socket
import time
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup, NavigableString
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
import trafilatura

from backend import db
from backend.locks import content_lock
from shared.article_snapshot import encode
from shared.source_elements import sanitize_table

USER_AGENT = 'RoadieArticleImporter/1.0'
MAX_HTML_BYTES = 3 * 1024 * 1024
MAX_IMAGE_BYTES = 1024 * 1024
MAX_ASSET_BYTES = 4 * 1024 * 1024
DNS_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='article-dns')


def public_url(value):
    try:
        parts = urlsplit(value)
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username
                or parts.password or parts.port not in {None, 80, 443}
                or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value):
            raise ValueError()
        host = parts.hostname.encode('idna').decode('ascii').lower()
        if host.rstrip('.') == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            raise ValueError()
        host_display = f'[{host}]' if ':' in host else host
        authority = host_display + (f':{parts.port}' if parts.port else '')
        return urlunsplit((parts.scheme, authority, parts.path or '/', parts.query, ''))
    except (ValueError, UnicodeError):
        raise HTTPException(422, 'Enter a public HTTP or HTTPS article URL using a standard web port.') from None


def public_addresses(host, port):
    lookup = DNS_POOL.submit(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    try:
        addresses = lookup.result(timeout=5)
    except FutureTimeout:
        lookup.cancel()
        raise OSError('Website DNS lookup timed out') from None
    if not addresses:
        raise HTTPException(422, 'The website has no public internet address.')
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if (not address.is_global or address.is_multicast or address.is_reserved
                or address == ipaddress.ip_address('168.63.129.16')):
            raise HTTPException(422, 'Website URLs must resolve exclusively to public internet addresses.')
    return addresses


def fetch(url, *, limit=MAX_HTML_BYTES, allowed=('text/html', 'application/xhtml+xml'), deadline=None,
          check_redirect=None):
    deadline = deadline or time.monotonic() + 30
    try:
        for _ in range(6):
            url = public_url(url)
            parts = urlsplit(url)
            port = parts.port or (443 if parts.scheme == 'https' else 80)
            addresses = public_addresses(parts.hostname, port)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            connection_class = HTTPSConnection if parts.scheme == 'https' else HTTPConnection
            connection = connection_class(parts.hostname, port, timeout=min(8, remaining))
            # Pin the actual TCP connection to the checked resolution. HTTPSConnection
            # still verifies the certificate and sends SNI for the original hostname.
            address = addresses[0][4]
            connection._create_connection = lambda *args, **kwargs: socket.create_connection(address[:2], timeout=min(8, remaining))
            try:
                target = urlunsplit(('', '', parts.path, parts.query, ''))
                connection.request('GET', target, headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity'})
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader('Location')
                    if not location:
                        raise HTTPException(422, 'The website returned an invalid redirect.')
                    url = public_url(urljoin(url, location))
                    if check_redirect:
                        check_redirect(url)
                    continue
                if response.status == 404 and allowed == ('text/plain',):
                    return url, b'', 'text/plain'
                if response.status != 200:
                    raise HTTPException(422, f'The website returned HTTP {response.status}. Use a freely accessible article.')
                mime = (response.getheader('Content-Type') or '').split(';')[0].strip().lower()
                if mime not in allowed or response.getheader('Content-Encoding', 'identity') != 'identity':
                    raise HTTPException(415, 'The website returned an unsupported content type or encoding.')
                length = response.getheader('Content-Length')
                if length and (not length.isdigit() or int(length) > limit):
                    raise HTTPException(413, 'The website response exceeds the download limit.')
                data = bytearray()
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError()
                    block = response.read1(min(65536, limit + 1 - len(data)))
                    if not block:
                        if length and len(data) != int(length):
                            raise HTTPException(422, 'The website response was incomplete. Retry or choose another source.')
                        return url, bytes(data), mime
                    data.extend(block)
                    if len(data) > limit:
                        raise HTTPException(413, 'The website response exceeds the download limit.')
            finally:
                connection.close()
        raise HTTPException(422, 'The website redirected too many times.')
    except (OSError, HTTPClientError, UnicodeError, ValueError):
        raise HTTPException(422, 'Could not retrieve the website safely. Check the URL and try again.') from None


def respect_robots(url, deadline):
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, '/robots.txt', '', ''))
    _, data, _ = fetch(robots_url, limit=256 * 1024, allowed=('text/plain',), deadline=deadline)
    rules = RobotFileParser()
    rules.parse(data.decode('utf-8', errors='replace').splitlines())
    if not rules.can_fetch(USER_AGENT, url):
        raise HTTPException(422, 'This website disallows automated article retrieval. Use an authorised source instead.')


def extract_article(html, url, deadline):
    soup = BeautifulSoup(html, 'html.parser')
    if not (soup.find('article') or soup.find('main') or soup.select_one('meta[property="og:type"][content="article"]')
            or re.search(r'"@type"\s*:\s*"(?:NewsArticle|Article|BlogPosting)"', str(soup))):
        raise HTTPException(422, 'This page has no identifiable article body. Use a public article page or upload an authorised PDF.')
    if soup.select_one('[data-paywall], .paywall, #paywall') or any(
            '"isAccessibleForFree":false' in script.get_text().replace(' ', '')
            for script in soup.find_all('script', type='application/ld+json')):
        raise HTTPException(422, 'Paywalled articles are unsupported. Use a freely accessible source.')
    title_node = soup.find('h1') or soup.find('title')
    title = title_node.get_text(' ', strip=True)[:300] if title_node else ''
    body = soup.find('article') or soup.find('main')
    if body and (body.find(['canvas', 'object']) or any(svg.find(['title', 'desc']) for svg in body.find_all('svg'))):
        raise HTTPException(422, 'This article contains embedded diagrams or interactive content that cannot be captured reliably. Upload an authorised PDF instead.')
    try:
        extracted = trafilatura.extract(html, url=url, output_format='html', include_comments=False,
                                       include_tables=True, include_images=True, include_formatting=True,
                                       favor_precision=True)
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(422, 'The article structure could not be extracted reliably. Use another source.') from None
    if not extracted or not title:
        raise HTTPException(422, 'No complete article was found. JavaScript, login and non-article pages are unsupported.')
    article = BeautifulSoup(extracted, 'html.parser')
    if body and len(body.find_all('table')) > len(article.find_all('table')):
        raise HTTPException(422, 'Article extraction omitted a table. Upload an authorised PDF to preserve its structure.')
    if len(article.get_text(' ', strip=True)) < 400 or len(article.find_all('p')) < 2:
        raise HTTPException(422, 'Too little article text was extracted. Use another source or upload an authorised PDF.')
    assets, image_sources, warnings = {}, [], []
    if body and body.find('iframe'):
        warnings.append('Embedded media is not included in this snapshot. Check whether its information is essential before publication.')

    def render(node):
        if isinstance(node, NavigableString):
            # Escape HTML and Markdown syntax from literal webpage text.
            return re.sub(r'([\\`*_{}\[\]<>#!|])', r'\\\1', str(node)).replace('\r', '')
        name = node.name
        if name in {'script', 'style', 'iframe', 'object', 'svg', 'form', 'nav', 'footer'}:
            return ''
        if name == 'table':
            return '\n\n' + sanitize_table(str(node)) + '\n\n'
        if name == 'img':
            source = urljoin(url, node.get('src', ''))
            alt = node.get('alt', '')[:300]
            record = {'url': source, 'alt': alt, 'stored': False}
            image_sources.append(record)
            if len(image_sources) <= 8 and sum(map(len, assets.values())) < MAX_ASSET_BYTES:
                try:
                    respect_robots(source, deadline)
                    _, data, _ = fetch(source, limit=min(MAX_IMAGE_BYTES, MAX_ASSET_BYTES - sum(map(len, assets.values()))),
                        allowed=('image/png', 'image/jpeg', 'image/webp', 'image/gif'), deadline=deadline,
                        check_redirect=lambda target: respect_robots(target, deadline))
                    with Image.open(BytesIO(data)) as image:
                        if image.width * image.height > 20_000_000:
                            raise ValueError('Image dimensions exceed limit')
                        image.verify()
                        extension = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp', 'GIF': 'gif'}[image.format]
                    path = f'images/{sha256(data).hexdigest()}.{extension}'
                    assets[path] = data
                    record.update(stored=True, path=path)
                    caption = re.sub(r'[^\w\s.,:;-]', '', alt) or 'Article illustration'
                    return f'\n\n![{caption}]({path})\n\n'
                except (HTTPException, OSError, ValueError, KeyError, UnidentifiedImageError, Image.DecompressionBombError):
                    pass
            warnings.append('An illustration could not be stored; check the original before publication.')
            return '\n\n[Illustration unavailable in snapshot]\n\n'
        text = ''.join(render(child) for child in node.children)
        if name and re.fullmatch('h[1-6]', name):
            return '\n\n' + '#' * int(name[1]) + ' ' + text.strip() + '\n\n'
        if name == 'li':
            depth = max(0, len(node.find_parents(['ul', 'ol'])) - 1)
            marker = '- '
            if node.parent.name == 'ol':
                marker = str(len(node.find_previous_siblings('li')) + 1) + '. '
            return '\n' + '  ' * depth + marker + text.strip() + '\n'
        if name in {'p', 'div', 'section', 'ul', 'ol', 'blockquote', 'pre'}:
            return '\n\n' + text.strip() + '\n\n'
        if name == 'br':
            return '\n'
        return text

    try:
        markdown = re.sub(r'\n{3,}', '\n\n', render(article)).strip() + '\n'
    except RecursionError:
        raise HTTPException(422, 'The article structure is too deeply nested to extract reliably.') from None
    if len(markdown) < 400:
        raise HTTPException(422, 'Article extraction was incomplete. Choose another source.')
    metadata = {'source_kind': 'website', 'original_url': url, 'article_title': title,
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'content_sha256': sha256(markdown.encode('utf-8')).hexdigest(),
                'images': image_sources, 'warnings': sorted(set(warnings))}
    return metadata, markdown, assets


def create(url):
    from backend.services import documents
    url = public_url(url)
    # The backend runs as one process; serialize submissions to prevent duplicates
    # and bound simultaneous extraction/download memory.
    with content_lock('website-articles'):
        deadline = time.monotonic() + 45
        respect_robots(url, deadline)
        final_url, html, _ = fetch(url, deadline=deadline,
                                 check_redirect=lambda target: respect_robots(target, deadline))
        metadata, markdown, assets = extract_article(html, final_url, deadline)
        metadata['submitted_url'] = url
        source_id = sha256(final_url.encode()).hexdigest()
        metadata['source_identifier'] = source_id
        filename = f"website-{source_id}-{metadata['content_sha256']}.md"
        if db.all_rows('documents', original_filename=filename):
            raise HTTPException(409, 'This article snapshot already exists in the Reference Library.')
        snapshot = encode(metadata, markdown, assets)
        return documents.create(UploadFile(filename=filename, file=BytesIO(snapshot)),
                                {'name': metadata['article_title'], 'document_type': 'other_reference', 'tags': []})
