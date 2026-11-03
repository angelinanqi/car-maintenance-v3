"""Index extracted documents and authored guide HTML through shared stages."""
from shared.observability import observed
from pathlib import Path
from contextlib import closing
import json
import re
import shutil
from shared.source_elements import ELEMENT_PATTERN, FORMAT_VERSION, element_parts
from shared.table_evidence import table_fragments, table_search_text
from shared.visual_identity import image_search_text
from shared.source_pages import copy_page_assets

from rag.app.cleaning.cleaner import MarkdownCleaner
from rag.app.parsing.markdown_parser import convert_markdown_to_html, render_section_path
from rag.app.parsing.html_tree import HTMLParser, save_tree
from rag.app.normalization.builder import normalize_file
from rag.app.models.document_tree import load_document
from rag.app.chunking.chunker import chunk_document, save_chunks
from rag.config.settings import CHROMA_PATH, OUTPUT_DIR


@observed('index_pipeline')
def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path = OUTPUT_DIR,
    chroma_path: str | Path | None = None,
    *,
    metadata: dict | None = None,
) -> dict:
    source = Path(input_path)
    if not source.is_file():
        raise FileNotFoundError(f"Extracted Markdown file does not exist: {source}")
    is_html = source.suffix.lower() == '.html'
    if source.suffix.lower() not in {'.md', '.html'}:
        raise ValueError(f"Expected extracted Markdown or guide HTML: {source}")

    output_dir = Path(output_dir)
    if chroma_path is not None:
        chroma_path = Path(chroma_path)
    elif output_dir == OUTPUT_DIR:
        chroma_path = CHROMA_PATH
    else:
        chroma_path = output_dir / "embeddings/chroma"

    name = source.stem
    cleaned = output_dir / "cleaning" / source.name
    html = output_dir / "parse" / f"{name}.html"
    parsed = output_dir / "parse" / f"{name}_html_tree.json"
    normalized = output_dir / "nodes" / f"{name}_html_tree.json"
    chunks_path = output_dir / "chunks" / f"{name}.json"
    if source.resolve() == cleaned.resolve():
        raise ValueError("Source Markdown must be separate from generated cleaning output")

    original = source.read_text(encoding='utf-8-sig')
    element_path = source.parent / 'elements.json'
    if not element_path.is_file():
        raise ValueError('Extraction is missing elements.json. Reprocess the document through the backend.')
    elements = json.loads(element_path.read_text(encoding='utf-8'))
    if elements.get('article'):
        article = elements['article']
        metadata = {**(metadata or {}), 'source_kind': 'website',
                    'original_url': article['original_url'], 'article_title': article['article_title'],
                    'retrieved_at': article['retrieved_at'], 'content_sha256': article['content_sha256']}
    if elements.get('format_version') != FORMAT_VERSION:
        raise ValueError('Reprocess extraction to the current source-element format')
    copy_page_assets(elements, source.parent, output_dir / 'assets' / name)
    for element in elements['elements']:
        element['original_section_path'] = element['section_path'].copy()
        if not is_html:
            element['section_path'] = render_section_path(element['section_path'])
    asset_elements = list(elements['elements'])
    for element in elements['elements']:
        if element.get('parts'):
            asset_elements.extend(element_parts(element))
    for element in asset_elements:
        reference = element.get('asset_path') if element['kind'] == 'image' else element.get('visual_asset_path')
        if reference and element.get('asset_sha256'):
            from shared.source_elements import image_path
            from hashlib import sha256
            asset = source.parent / image_path(reference)
            if not asset.is_file() or sha256(asset.read_bytes()).hexdigest() != element['asset_sha256']:
                raise ValueError('Extraction asset does not match its recorded hash')
            target = output_dir / 'assets' / name / element['asset_sha256']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(asset, target)
    # Source elements are classified before prose cleaning and cannot enter
    # ordinary chunking. Their complete original evidence lives in the manifest.
    prose = original if is_html else ELEMENT_PATTERN.sub('\n\n', original)
    cleaned.parent.mkdir(parents=True, exist_ok=True)
    cleaner = MarkdownCleaner()
    cleaned.write_text(prose if is_html else cleaner.clean(prose), encoding='utf-8')
    cleaning_audit = {
        'document_name': name,
        'removed_blocks': cleaner.removed_malay_blocks.copy(),
        'source_elements': [],
    }
    for element in elements['elements']:
        # Descriptions are search aids. Keep original descriptions, cell values,
        # captions, images and provenance intact in the source manifest.
        element['retrieval_description'] = cleaner.clean(element['description']).strip()
        if element['kind'] == 'image' and not element.get('authored_description') and (is_html or element.get('identity_review') or element.get('generated_identity')):
            # Clean original prose before adding attribution/identification labels.
            element['retrieval_description'] = image_search_text({**element,
                'context': [cleaner.clean(text).strip() for text in element.get('context', [])]})
        if cleaner.removed_malay_blocks:
            cleaning_audit['source_elements'].append({
                'element_id': element['element_id'],
                'removed_blocks': cleaner.removed_malay_blocks.copy(),
            })
    cleaned.with_suffix('.removed_malay.json').write_text(
        json.dumps(cleaning_audit, ensure_ascii=False, indent=2), encoding='utf-8')
    html.parent.mkdir(parents=True, exist_ok=True)
    if is_html:
        html.write_text(prose, encoding='utf-8')
    else:
        convert_markdown_to_html(cleaned, html)
    save_tree(HTMLParser().parse(html), parsed)
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalize_file(parsed, normalized)
    chunks = chunk_document(load_document(normalized), document_title=(metadata or {}).get('document_title'))
    save_chunks(name, chunks, chunks_path.parent)
    data = json.loads(chunks_path.read_text(encoding='utf-8'))
    sections = {}
    for chunk in data:
        chunk['metadata']['content_type'] = 'paragraph'
        path = chunk['metadata'].get('section_path', [])
        text_key = ' '.join(re.findall(r'\w+', chunk['source_content'].lower()))
        chunk['metadata']['source_element_ids'] = []
        sections.setdefault(tuple(path), []).append((chunk, text_key))
    for element in elements['elements']:
        for context in element['context']:
            words = re.findall(r'\w+', context.lower())
            if len(words) < 4:
                continue
            context_key = ' '.join(words)
            matches = [chunk for chunk, text_key in sections.get(tuple(element['section_path']), [])
                       if context_key in text_key]
            if len(matches) == 1:
                ids = matches[0]['metadata']['source_element_ids']
                if element['element_id'] not in ids:
                    ids.append(element['element_id'])
    for element in elements['elements']:
        if element['kind'] == 'table':
            fragments = table_fragments(element)
            for fragment in fragments:
                search_text = '\n'.join([(metadata or {}).get('document_title', name),
                    'Section: ' + ' > '.join(element['section_path']), table_search_text(fragment)])
                data.append({'text': search_text, 'retrieval_text': search_text, 'metadata': {
                    'document_name': name, 'content_type': 'table', 'node_type': 'Table',
                    'element_id': element['element_id'], 'section_path': element['section_path'],
                    'evidence_type': 'table_cells_v1', 'structure_valid': True,
                    'source_content': json.dumps(fragment, ensure_ascii=False),
                    'pages': element.get('pages', []),
                }})
            if fragments:
                continue
        description = element['retrieval_description']
        if not description:
            continue
        context = (metadata or {})
        section = ('Section: ' + ' > '.join(element['section_path'])
                   if not (element.get('identity_review') or element.get('generated_identity')) else '')
        text = '\n'.join([context.get('document_title', name), context.get('car_model', ''),
                          section, element.get('vehicle_context', ''), description])
        guide_image = is_html and element['kind'] == 'image'
        data.append({'text': text, 'retrieval_text': text, 'metadata': {
            'document_name': name, 'content_type': 'paragraph' if guide_image else element['kind'],
            'node_type': element['kind'].title(), 'element_id': element['element_id'],
            'section_path': element['section_path'],
            'source_content': '\n'.join(filter(None, [element.get('vehicle_context'), description])) if guide_image else element['description'],
            **({'media_id': element['media_id'], 'start_seconds': 0} if guide_image else {}),
        }})
    if is_html:
        for item in elements.get('guide_media_texts', []):
            data.append({'text': item['text'], 'retrieval_text': item['text'], 'metadata': {
                'document_name': name, 'content_type': 'paragraph', 'source_content': item['text'],
                'media_id': item['media_id'], 'start_seconds': item['start_seconds'],
                **{key: item[key] for key in ('step_id', 'step_order', 'step_title', 'section_path') if key in item}}})
    if elements.get('emergency_steps'):
        for chunk in data:
            details = chunk['metadata']
            details['scenario_key'] = elements['scenario_key']
            path = details.get('section_path', [])
            for step in elements['emergency_steps']:
                if step['heading'] in path:
                    details.update({key: step[key] for key in ('step_id', 'step_order', 'step_title')})
                    break
    chunks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    sources = output_dir / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    staged = sources / f'{name}.tmp'
    staged.write_text(json.dumps(elements, ensure_ascii=False), encoding='utf-8')
    staged.replace(sources / f'{name}.json')

    from rag.app.embedding import embedder
    from rag.app.embedding.vector_store import VectorStore
    from rag.app.embedding.ingestion import process_document

    store = VectorStore(chroma_path)
    with closing(store.client):
        count = process_document(
            chunks_path, embedder, store,
            extra_metadata={**(metadata or {}), 'format_version': FORMAT_VERSION}
        )
    # Optional review artifacts never enter embeddings or affect index success.
    if not is_html:
        try:
            from shared.maintenance_extraction import prepare_safely
            prepare_safely(elements, output_dir)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Maintenance assistance unavailable; indexing is unaffected')
    return {
        "status": "completed",
        "documents": [{
            "document_name": name,
            "chunks": count,
            "tree_path": str(normalized),
            "chunks_path": str(chunks_path),
        }],
        "chroma_path": str(chroma_path),
    }
