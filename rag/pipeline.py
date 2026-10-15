"""Index extracted Markdown supplied by the production document worker."""
from pathlib import Path
import json
import re
from backend.source_elements import ELEMENT_PATTERN, FORMAT_VERSION

from rag.app.cleaning.cleaner import MarkdownCleaner
from rag.app.parsing.markdown_parser import convert_markdown_to_html
from rag.app.parsing.html_tree import HTMLParser, save_tree
from rag.app.normalization.builder import normalize_file
from rag.app.models.document_tree import load_document
from rag.app.chunking.chunker import chunk_document, save_chunks
from rag.config.settings import CHROMA_PATH, OUTPUT_DIR


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
    if source.suffix.lower() != ".md":
        raise ValueError(f"Expected extracted Markdown: {source}")

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
    if elements.get('format_version') != FORMAT_VERSION:
        raise ValueError('Reprocess extraction to the current source-element format')
    # Source elements are classified before prose cleaning and cannot enter
    # ordinary chunking. Their complete original evidence lives in the manifest.
    prose = ELEMENT_PATTERN.sub('\n\n', original)
    cleaned.parent.mkdir(parents=True, exist_ok=True)
    cleaned.write_text(MarkdownCleaner().clean(prose), encoding='utf-8')
    html.parent.mkdir(parents=True, exist_ok=True)
    convert_markdown_to_html(cleaned, html)
    save_tree(HTMLParser().parse(html), parsed)
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalize_file(parsed, normalized)
    chunks = chunk_document(load_document(normalized))
    save_chunks(name, chunks, chunks_path.parent)
    data = json.loads(chunks_path.read_text(encoding='utf-8'))
    for chunk in data:
        chunk['metadata']['content_type'] = 'paragraph'
        path = chunk['metadata'].get('section_path', [])
        text_key = ' '.join(re.findall(r'\w+', chunk['source_content'].lower()))
        nearby = []
        for element in elements['elements']:
            if element['section_path'] != path:
                continue
            for context in element['context']:
                words = re.findall(r'\w+', context.lower())
                # Link source neighbours, rather than every image in a section.
                if len(words) >= 4 and any(' '.join(part) in text_key for part in (words[:24], words[-24:])):
                    nearby.append(element['element_id'])
                    break
        chunk['metadata']['source_element_ids'] = nearby
    for element in elements['elements']:
        if not element['description'].strip():
            continue
        context = (metadata or {})
        text = '\n'.join([context.get('document_title', name), context.get('car_model', ''),
                          'Section: ' + ' > '.join(element['section_path']), element['description']])
        data.append({'text': text, 'retrieval_text': text, 'metadata': {
            'document_name': name, 'content_type': element['kind'],
            'node_type': element['kind'].title(), 'element_id': element['element_id'],
            'section_path': element['section_path'], 'source_content': element['description'],
        }})
    chunks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    sources = output_dir / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    staged = sources / f'{name}.tmp'
    staged.write_text(json.dumps(elements, ensure_ascii=False), encoding='utf-8')
    staged.replace(sources / f'{name}.json')

    from rag.app.embedding.embedder import Embedder
    from rag.app.embedding.vector_store import VectorStore
    from rag.app.embedding.ingestion import process_document

    count = process_document(
        chunks_path, Embedder(), VectorStore(chroma_path), extra_metadata={**(metadata or {}), 'format_version': FORMAT_VERSION}
    )
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
