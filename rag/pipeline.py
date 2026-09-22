import argparse
import json
from pathlib import Path
from rag.app.ocr import run_ocr
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

    # processes markdown files.
    # replaces generated files and Chroma records for each selected document, other documents (including removed/renamed sources) remain in the index
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

    return _run_files(files, output_dir, chroma_path)


def process_documents(
    paths,
    output_dir: str | Path = "output",
    chroma_path: str | Path | None = None,
    *,
    mineru_executable: str | Path | None = None,
) -> list[dict]:
    # Ingest PDFs,filename stems are the existing document_name identities

    files = (
        [Path(paths)]
        if isinstance(paths, (str, Path))
        else [Path(path) for path in paths]
    )
    if not files:
        raise ValueError("Provide at least one PDF")
    output_dir = Path(output_dir)
    chroma_path = (
        Path(chroma_path)
        if chroma_path is not None
        else output_dir / "embeddings" / "chroma"
    )
    return _run_files(
        files,
        output_dir,
        chroma_path,
        pdf_mode=True,
        mineru_executable=mineru_executable,
    )["documents"]


def _run_files(
    files, output_dir, chroma_path, *, pdf_mode=False, mineru_executable=None
):
    cleaner = None
    parser = HTMLParser()
    embedder = None
    store = None
    documents = []

    for source in files:
        name = source.stem

        try:
            if pdf_mode:
                source = run_ocr(
                    source, output_dir / "ocr", mineru_executable=mineru_executable
                )
            if cleaner is None:
                cleaner = MarkdownCleaner()
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
            # load the model only when needed and reuse it for all selected manuals

            from rag.app.embedding.embedder import Embedder
            from rag.app.embedding.vector_store import VectorStore
            from rag.app.embedding.ingestion import process_document

            if embedder is None:
                embedder = Embedder()
            if store is None:
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

            if pdf_mode:
                documents[-1].update(
                    document_id=name,
                    success=True,
                    status="processed",
                    ocr_path=str(source),
                )

        except Exception as error:
            if not pdf_mode:
                raise
            print(f"Failed to process {name}: {error}")
            documents.append(
                {
                    "document_id": name,
                    "success": False,
                    "status": "failed",
                    "error": str(error),
                }
            )

    print("Pipeline finished.")
    status = (
        "failed"
        if any(document.get("success") is False for document in documents)
        else "completed"
    )
    return {"status": status, "documents": documents, "chroma_path": str(chroma_path)}


def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDFs or Markdown; replace each selected manual's Chroma records."
    )
    parser.add_argument("--pdf", nargs="+", help="One or more PDFs to OCR and ingest")
    parser.add_argument("--mineru-executable", help="Path to MinerU executable")
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

    if args.pdf:
        results = process_documents(
            args.pdf,
            args.output_dir,
            args.chroma_path,
            mineru_executable=args.mineru_executable,
        )

        print(json.dumps(results, indent=2))

        if not all(result["success"] for result in results):
            parser.exit(1)
    else:
        run_pipeline(args.input, args.output_dir, args.chroma_path)


if __name__ == "__main__":
    main()
