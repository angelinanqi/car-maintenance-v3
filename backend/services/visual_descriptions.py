"""Describe PDF illustrations through the existing private RAG connection."""
from hashlib import sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import shutil
import subprocess

import httpx
from PIL import Image

from backend import settings
from shared.source_elements import image_path
from shared.source_pages import element_page, page_assets
from shared.visual_identity import VisualIdentity

logger = logging.getLogger(__name__)


def render_pages(source, directory, pages):
    executable = settings.MINERU_EXECUTABLE or shutil.which('mineru')
    if not executable:
        raise ValueError('Configure MINERU_EXECUTABLE to render original PDF pages')
    executable = Path(executable)
    python = executable.with_name('python.exe' if executable.suffix == '.exe' else 'python')
    if not python.is_file():
        raise ValueError('The MinerU Python interpreter is unavailable for page rendering')
    subprocess.run([str(python), str(settings.PROJECT_ROOT / 'scripts/render_pdf_pages.py'),
                    '--source', str(source), '--output', str(directory),
                    '--pages', *[str(page) for page in pages]],
                   check=True, timeout=settings.MINERU_TIMEOUT)
    return json.loads((directory / 'pages.json').read_text(encoding='utf-8'))


def prepare_source_pages(elements, source, extraction, directory):
    """Package deduplicated pages for answer-time evidence without model calls."""
    numbers = set()
    for element in elements['elements']:
        page = element_page(element)
        if page is not None:
            numbers.add(page)
    numbers = sorted(numbers)
    elements['page_assets'] = []
    if not numbers:
        return
    digest = sha256(source.read_bytes()).hexdigest()
    if elements.get('source_sha256') != digest:
        raise ValueError('Page preparation does not match the source PDF')
    cache = directory / 'visual-pages' / digest / 'pdfium-1800-v1'
    rendered = render_pages(source, cache, numbers)
    if rendered['source_sha256'] != digest:
        raise ValueError('Page renders do not belong to this source PDF')
    for item in rendered['pages']:
        # The renderer emits basenames, never paths outside its source-keyed cache.
        if Path(item['path']).name != item['path'] or item['page'] not in numbers:
            raise ValueError('Invalid rendered source page')
        data = (cache / item['path']).read_bytes()
        if sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Rendered source page bytes changed')
        # Keep source-page resolution while avoiding oversized extraction uploads.
        # MinerU's original crops remain untouched; these are rendered page inputs.
        relative = f"images/pages/page-{item['page']:05d}.webp"
        target = extraction / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(BytesIO(data)) as page_image:
            with page_image.convert('RGB') as rgb:
                cached = False
                if target.is_file():
                    try:
                        with Image.open(target) as previous:
                            cached = (previous.size == rgb.size
                                      and previous.convert('RGB').tobytes() == rgb.tobytes())
                    except OSError:
                        pass  # An interrupted cache entry is regenerated from the PDF render.
                if not cached:
                    staged = target.with_suffix('.tmp')
                    rgb.save(staged, format='WEBP', lossless=True, method=4)
                    staged.replace(target)
        elements['page_assets'].append({'page': item['page'], 'asset_path': relative,
                                       'asset_sha256': sha256(target.read_bytes()).hexdigest()})
    if set(page_assets(elements)) != set(numbers):
        raise ValueError('Source-page rendering is incomplete')


def describe_pdf(elements, source, extraction, directory):
    """Require an exact single-page match; never guess a page from element order."""
    images = [item for item in elements['elements'] if item['kind'] == 'image']
    source_digest = sha256(source.read_bytes()).hexdigest()
    report = {'source_sha256': source_digest, 'generated_visual_identities': [], 'skipped': []}
    mapped = []
    for image in images:
        pages = image.get('pages', [])
        if (not image.get('provenance_available') or len(pages) != 1
                or not isinstance(pages[0], int) or isinstance(pages[0], bool) or pages[0] < 1):
            report['skipped'].append({'element_id': image['element_id'], 'reason': 'No unique source page'})
        else:
            mapped.append(image)
    if not mapped:
        return report
    if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
        raise ValueError('Configure the RAG service connection for PDF image descriptions')
    packaged = page_assets(elements)
    if packaged:
        if elements['source_sha256'] != source_digest:
            raise ValueError('Packaged pages do not belong to this source PDF')
        page_directory = extraction
        pages = {number: {'page': number, 'path': item['asset_path'], 'sha256': item['asset_sha256']}
                 for number, item in packaged.items()}
    else:
        page_directory = directory / 'visual-pages' / source_digest / 'pdfium-1800-v1'
        rendered = render_pages(source, page_directory, sorted({e['pages'][0] for e in mapped}))
        if rendered['source_sha256'] != source_digest:
            raise ValueError('Page renders do not belong to this source PDF')
        pages = {item['page']: item for item in rendered['pages']}
    metadata = extraction / 'metadata'
    metadata.mkdir(exist_ok=True)
    target = metadata / 'generated-identities.json'
    with httpx.Client(timeout=settings.RAG_SERVICE_TIMEOUT, follow_redirects=False,
                      headers={'Authorization': 'Bearer ' + settings.RAG_SERVICE_TOKEN}) as client:
        for image in mapped:
            asset = extraction / image_path(image['asset_path'])
            page = pages[image['pages'][0]]
            page_path = page_directory / page['path']
            data, page_data = asset.read_bytes(), page_path.read_bytes()
            if (sha256(data).hexdigest() != image['asset_sha256']
                    or sha256(page_data).hexdigest() != page['sha256']):
                raise ValueError('Source image or rendered page bytes changed')
            response = client.post(settings.RAG_SERVICE_URL + '/v1/visual-description', files={
                'original': ('original.png', data, 'application/octet-stream'),
                'source_page': ('page.png', page_data, 'image/png')})
            response.raise_for_status()
            result = response.json()
            identity = VisualIdentity.model_validate(result['identity']).model_dump()
            if (result['asset_sha256'] != image['asset_sha256']
                    or result['context_page_sha256'] != page['sha256']):
                raise ValueError('Description does not match the supplied originals')
            generated = {**identity, 'model': result['model'], 'asset_sha256': image['asset_sha256'],
                         'prompt_sha256': result['prompt_sha256'], 'source_sha256': source_digest,
                         'context_page': page['page'], 'context_page_sha256': page['sha256']}
            image['generated_identity'] = generated
            report['generated_visual_identities'].append({**result, 'element_id': image['element_id'],
                'source_sha256': source_digest, 'context_page': page['page']})
            logger.info('PDF visual descriptions: %d/%d complete (cached=%s)',
                        len(report['generated_visual_identities']), len(mapped), result.get('cache_reused', False))
    # The RAG service persists each completed description. Packaging needs only
    # the finished report; rewriting it per image duplicates that persistence
    # and can collide with readers/virus scanners on Windows.
    staged = target.with_suffix('.tmp')
    staged.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    staged.replace(target)
    return report
