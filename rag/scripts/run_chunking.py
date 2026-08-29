from __future__ import annotations
import json
from pathlib import Path
from rag.app.database.models import DocumentNode
from rag.app.chunking.chunker import chunk_document, save_chunks

INPUT_DIR = Path("output/retrieval")
OUTPUT_DIR = Path("output/chunks")


def load_document(
    path: Path,
) -> DocumentNode:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return DocumentNode.from_tree_dict(data)


def main() -> None:
    INPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    files = sorted(INPUT_DIR.glob("*.json"))

    if not files:
        print(f"No retrieval files found in {INPUT_DIR}")
        return

    print(f"Found {len(files)} document(s).")

    for path in files:
        print()
        print("=" * 60)
        print(f"Chunking: {path.stem}")
        print("=" * 60)

        document = load_document(path)

        chunks = chunk_document(document)

        save_chunks(
            document_name=document.document_name,
            chunks=chunks,
            output_dir=OUTPUT_DIR,
        )

        print(f"Created {len(chunks)} chunk(s).")

    print()
    print("=" * 60)
    print("Chunking finished.")
    print("=" * 60)


if __name__ == "__main__":
    main()
