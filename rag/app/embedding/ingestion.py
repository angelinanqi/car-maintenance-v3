import json
from hashlib import sha256
from pathlib import Path
from rag.app.embedding.embedder import Embedder
from rag.app.embedding.vector_store import VectorStore


def load_chunks(file_path: Path) -> tuple[str, list[dict]]:
    """
    Load chunks from a JSON file.

    Supports:
    - a list of chunks
    - {"chunks": [...]}
    - a single chunk object
    """

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        chunks = data

    elif isinstance(data, dict) and "chunks" in data:
        chunks = data["chunks"]

    elif isinstance(data, dict):
        chunks = [data]

    else:
        raise ValueError(f"Unsupported chunk format in {file_path}")

    document_name = file_path.stem
    if not isinstance(chunks, list) or any(
        not isinstance(chunk, dict) for chunk in chunks
    ):
        raise ValueError(f"Invalid chunk list in {file_path}")
    for chunk in chunks:
        name = chunk.get("metadata", {}).get("document_name")
        if name is not None and name != document_name:
            raise ValueError(
                f"Chunk document name {name!r} does not match {document_name!r}"
            )

    return document_name, chunks


def create_chunk_id(document_name: str, index: int, chunk: dict) -> str:
    """
    Create a unique ID for a chunk.

    Chunk IDs are separate from node IDs.
    """
    digest = sha256(
        json.dumps(chunk, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"{document_name}_chunk_{index:06d}_{digest}"


def build_metadata(
    document_name: str,
    chunk: dict,
    chunk_id: str,
) -> dict:
    """
    Convert chunk metadata into a Chroma-compatible metadata dictionary.
    """

    metadata = chunk.get("metadata", {})

    node_ids = metadata.get("node_ids", [])

    # Chroma metadata values must be scalar values.
    # Store multiple node IDs as a JSON string.
    if isinstance(node_ids, list):
        node_ids = json.dumps(node_ids)

    result = {
        "chunk_id": chunk_id,
        "document_name": document_name,
        "node_ids": node_ids,
    }

    # Copy useful metadata when available.
    for key in [
        "parent_id",
        "node_type",
        "content_type",
        "section_path",
        "source_tag",
        "source_depth",
        "source_position",
        "src",
    ]:
        value = metadata.get(key)

        if value is not None:
            # Chroma does not accept arbitrary complex objects.
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            result[key] = value

    return result


def process_document(
    file_path: Path,
    embedder: Embedder,
    vector_store: VectorStore,
):
    document_name, chunks = load_chunks(file_path)

    texts = []
    ids = []
    metadatas = []

    for index, chunk in enumerate(chunks, start=1):
        text = chunk.get("text", "").strip()

        if not text:
            print(f"Skipping empty chunk " f"{document_name} #{index}")
            continue

        chunk_id = create_chunk_id(
            document_name,
            index,
            chunk,
        )

        metadata = build_metadata(
            document_name,
            chunk,
            chunk_id,
        )

        ids.append(chunk_id)
        texts.append(text)
        metadatas.append(metadata)

    print(f"\nEmbedding {len(texts)} chunks " f"from {document_name}...")

    embeddings = embedder.embed_documents(texts) if texts else []

    vector_store.replace_document(
        document_name=document_name,
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Stored {len(ids)} chunks " f"for {document_name}")
    return len(ids)