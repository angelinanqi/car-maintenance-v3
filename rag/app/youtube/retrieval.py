"""YouTube's embedding/storage boundary: reuse the current shared embedder."""

from .config import COLLECTION_NAME


def open_store(database_path):
    from rag.app.embedding.vector_store import VectorStore

    return VectorStore(database_path, collection_name=COLLECTION_NAME)


def create_embedder():
    from rag.app.embedding.embedder import Embedder

    return Embedder()


def replace_video(store, video_id, chunks, embedder):
    # Compute everything before deleting old records. A failed write is repaired
    # on rerun by comparing the complete expected ID set. No concurrent writers.
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embedder.embed_documents(texts)
    if len(embeddings) != len(chunks):
        raise ValueError("Embedding count does not match chunk count.")
    store.collection.delete(where={"video_id": video_id})
    batch_size = store.client.get_max_batch_size()
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        store.upsert(
            [c["id"] for c in batch],
            [c["text"] for c in batch],
            embeddings[start : start + batch_size],
            [c["metadata"] for c in batch],
        )


def timestamp_url(video_id, start_seconds):
    return f"https://www.youtube.com/watch?v={video_id}&t={max(0, int(start_seconds))}s"


def group_by_video(results):
    """Lowest distance chunk supplies each video's primary timestamp."""
    best = {}
    for result in sorted(results, key=lambda result: result["distance"]):
        best.setdefault(result["metadata"]["video_id"], result)
    return list(best.values())


def retrieve_youtube(query, top_k=5, database_path=None):
    from rag.app.embedding.vector_store import CHROMA_PATH

    if not query.strip() or top_k < 1:
        raise ValueError("Provide a nonempty query and positive top_k.")
    store = open_store(database_path or CHROMA_PATH)
    count = store.collection.count()
    if not count:
        return []
    embedding = create_embedder().embed_query(query)
    response = store.search(embedding, top_k=min(top_k, count))
    documents = response.get("documents") or [[]]
    metadatas = response.get("metadatas") or [[]]
    distances = response.get("distances")
    if distances is None:
        distances = [[]]
    return [
        {
            "id": chunk_id,
            "text": documents[0][i],
            "metadata": metadatas[0][i],
            "distance": distances[0][i],
        }
        for i, chunk_id in enumerate(response["ids"][0])
    ]
