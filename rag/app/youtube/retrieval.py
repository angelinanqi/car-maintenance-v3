from rag.config.settings import RAG_TOP_K
from rag.config.settings import YOUTUBE_COLLECTION as COLLECTION_NAME
from rag.config.settings import YOUTUBE_WATCH_URL


def open_store(database_path, *, create=True):
    from rag.app.embedding.vector_store import VectorStore

    return VectorStore(database_path, collection_name=COLLECTION_NAME, create=create)


def create_embedder():
    from rag.app.embedding.embedder import SharedEmbedder

    return SharedEmbedder()


def replace_video(store, video_id, chunks, embedder):
    # compute everything before deleting old records. A failed write is repaired on rerun by comparing the complete expected ID set. No concurrent writers.
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
    url = f"{YOUTUBE_WATCH_URL}?v={video_id}"
    return url if start_seconds is None else f"{url}&t={max(0, int(start_seconds))}s"


def group_by_video(results):
    best = {}
    for result in sorted(results, key=lambda result: result["distance"]):
        best.setdefault(result["metadata"]["video_id"], result)
    return list(best.values())


def retrieve_youtube(
    query,
    top_k=RAG_TOP_K,
    database_path=None,
    *,
    query_embedding=None,
    diagnostics=None,
    video_ids=None,
):
    from rag.app.embedding.vector_store import CHROMA_PATH

    if video_ids is not None and not video_ids:
        return []

    if not query.strip() or top_k < 1:
        raise ValueError("Provide a nonempty query and positive top_k.")

    from chromadb.errors import NotFoundError

    try:
        store = open_store(database_path or CHROMA_PATH, create=False)
    except (FileNotFoundError, NotFoundError):
        # Videos are optional; a manual-only installation can still answer.
        return []
    count = store.collection.count()

    if diagnostics is not None:
        diagnostics.update(
            metric=(store.collection.configuration.get("hnsw") or {}).get(
                "space", "l2"
            ),
        )

    if not count:
        return []

    embedding = query_embedding

    if embedding is None:
        embedding = create_embedder().embed_query(query)

    limit = min(top_k, count)
    response = store.search(embedding, top_k=limit, **({"video_ids": video_ids} if video_ids is not None else {}))
    distances = (response or {}).get("distances") or []

    if not distances or not distances[0]:
        return []

    distance_row = distances[0]

    if distance_row is None:
        return []

    documents = (response or {}).get("documents") or []
    metadatas = (response or {}).get("metadatas") or []
    ids = (response or {}).get("ids") or []

    if not documents or not metadatas or not ids:
        return []

    results = [
        {
            "id": chunk_id,
            "text": documents[0][i],
            "metadata": metadatas[0][i],
            "distance": distance_row[i],
        }
        for i, chunk_id in enumerate(ids[0])
    ]

    return results


def distance_to_similarity(distance, metric):
    if metric == "l2":
        return 1 - distance / 2
    if metric in {"cosine", "ip"}:
        return 1 - distance
    raise ValueError(f"Unsupported video distance metric: {metric}")
