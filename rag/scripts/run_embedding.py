from pathlib import Path
from rag.app.embedding.embedder import Embedder
from rag.app.embedding.vector_store import VectorStore
from rag.app.embedding.ingestion import process_document

CHUNK_DIR = Path("output/chunks")


def main():
    if not CHUNK_DIR.exists():
        raise FileNotFoundError(f"Chunk directory not found: {CHUNK_DIR}")
    chunk_files = sorted(CHUNK_DIR.glob("*.json"))

    if not chunk_files:
        raise FileNotFoundError(f"No JSON chunk files found in {CHUNK_DIR}")

    print(f"Found {len(chunk_files)} chunk files.")

    embedder = Embedder()
    vector_store = VectorStore()

    for file_path in chunk_files:
        process_document( file_path, embedder, vector_store,)

    print("\nEmbedding stage complete.")


if __name__ == "__main__":
    main()
