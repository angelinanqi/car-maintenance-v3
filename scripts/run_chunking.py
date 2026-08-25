from pathlib import Path
import json
from app.database.models import DocumentNode
from app.chunking.chunker import (
    chunk_document,
    save_chunks,
)

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

    files = sorted(INPUT_DIR.glob("*.json"))

    if not files:
        print(f"No JSON files found in {INPUT_DIR}")
        return

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

        print(f"Total chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
