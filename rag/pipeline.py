"""Ingest Markdown into Chroma. Query/retrieval is a separate flow."""

import argparse
from pathlib import Path

from rag.app.cleaning.cleaner import MarkdownCleaner
from rag.app.parsing.markdown_parser import convert_markdown_to_html
from rag.app.parsing.html_tree import HTMLParser, save_tree
from rag.app.normalization.builder import normalize_file
from rag.app.models.document_tree import load_document
from rag.app.chunking.chunker import chunk_document, save_chunks


def run_pipeline(
    input_path: str | Path = "data/markdown",
    output_dir: str | Path = "output",
    chroma_path: str | Path | None = None,
) -> dict:
    """Process one Markdown file or a directory of Markdown files.

    Replaces generated files and Chroma records for each selected document.
    Other documents (including removed/renamed sources) remain in the index.
    Exceptions propagate immediately; completed documents are not rolled back.
    Paths are relative to the caller's working directory unless absolute.
    """
    # TODO: OCR PIPELINE GOES HERE.
    # Future source document -> OCR-produced Markdown -> existing cleaning below.
    # For now input_path must already contain Markdown; no OCR is performed.
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    chroma_path = (
        Path(chroma_path)
        if chroma_path is not None
        else output_dir / "embeddings" / "chroma"
    )
    if input_path.is_file():
        if input_path.suffix.lower() != ".md":
            raise ValueError(f"Expected a Markdown file: {input_path}")
        files = [input_path]
    elif input_path.is_dir():
        files = sorted(input_path.glob("*.md"))
    else:
        raise FileNotFoundError(f"Input does not exist: {input_path}")
    if not files:
        raise FileNotFoundError(f"No Markdown files found: {input_path}")
    for source in files:
        if source.resolve() == (output_dir / "cleaning" / source.name).resolve():
            raise ValueError(
                "Input Markdown must be separate from generated cleaning output"
            )

    cleaner = MarkdownCleaner()
    parser = HTMLParser()
    embedder = None
    store = None
    documents = []
    for source in files:
        name = source.stem
        cleaned = output_dir / "cleaning" / source.name
        html = output_dir / "parse" / f"{name}.html"
        parsed = output_dir / "parse" / f"{name}_html_tree.json"
        normalized = output_dir / "nodes" / f"{name}_html_tree.json"
        chunks_path = output_dir / "chunks" / f"{name}.json"

        print(f"\nDocument: {name}")
        print("[1/6] Cleaning Markdown...")
        cleaner.clean_file(
            source, cleaned, output_dir / "cleaning" / "reports" / f"{name}.json"
        )
        print("[2/6] Converting Markdown to HTML...")
        html.parent.mkdir(parents=True, exist_ok=True)
        convert_markdown_to_html(cleaned, html)
        print("[3/6] Parsing HTML tree...")
        save_tree(parser.parse(html), parsed)
        print("[4/6] Normalizing and assigning local node IDs...")
        normalized.parent.mkdir(parents=True, exist_ok=True)
        normalize_file(parsed, normalized)
        print("[5/6] Chunking semantic tree...")
        chunks = chunk_document(load_document(normalized))
        save_chunks(name, chunks, chunks_path.parent)
        print("[6/6] Embedding and replacing document records in Chroma...")
        # Load the model only when needed and reuse it for all selected manuals.
        from rag.app.embedding.embedder import Embedder
        from rag.app.embedding.vector_store import VectorStore
        from rag.app.embedding.ingestion import process_document

        if embedder is None:
            embedder = Embedder()
            store = VectorStore(chroma_path)
        count = process_document(chunks_path, embedder, store)
        documents.append(
            {
                "document_name": name,
                "chunks": count,
                "tree_path": str(normalized),
                "chunks_path": str(chunks_path),
            }
        )

    print("Pipeline completed.")
    return {
        "status": "completed",
        "documents": documents,
        "chroma_path": str(chroma_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Markdown; replace each selected manual's Chroma records."
    )
    parser.add_argument(
        "--input",
        default="data/markdown",
        help="Markdown file or directory (non-recursive)",
    )
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--chroma-path", help="Defaults to OUTPUT_DIR/embeddings/chroma"
    )
    args = parser.parse_args()
    run_pipeline(args.input, args.output_dir, args.chroma_path)


if __name__ == "__main__":
    main()
