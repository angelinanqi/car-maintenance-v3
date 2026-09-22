from .config import COLLECTION_NAME


def open_store(database_path, *, create=True):
    from rag.app.embedding.vector_store import VectorStore

    return VectorStore(database_path, collection_name=COLLECTION_NAME, create=create)


def create_embedder():
    from rag.app.embedding.embedder import Embedder

    return Embedder()


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
    url = f"https://www.youtube.com/watch?v={video_id}"
    return url if start_seconds is None else f"{url}&t={max(0, int(start_seconds))}s"


def group_by_video(results):
    best = {}
    for result in sorted(results, key=lambda result: result["distance"]):
        best.setdefault(result["metadata"]["video_id"], result)
    return list(best.values())


def retrieve_youtube(
    query,
    top_k=5,
    database_path=None,
    *,
    query_embedding=None,
    best_only=False,
    diagnostics=None,
):
    from rag.app.embedding.vector_store import CHROMA_PATH

    if not query.strip() or top_k < 1:
        raise ValueError("Provide a nonempty query and positive top_k.")

    store = open_store(database_path or CHROMA_PATH, create=False)
    count = store.collection.count()

    if diagnostics is not None:
        from rag.config.settings import VIDEO_RELEVANCE_THRESHOLD

        diagnostics.update(
            indexed_chunks=count,
            raw_chunks=[],
            grouped_videos=[],
            selected_videos=[],
            threshold=VIDEO_RELEVANCE_THRESHOLD,
            metric=(store.collection.configuration.get("hnsw") or {}).get(
                "space", "l2"
            ),
            relevant=False,
            reason="No indexed YouTube chunks.",
        )

    if not count:
        return []

    embedding = query_embedding

    if embedding is None:
        embedding = create_embedder().embed_query(query)

    limit = min(top_k, count)
    response = store.search(embedding, top_k=limit)
    distances = (response or {}).get("distances") or []

    if not distances or not distances[0]:
        return []

    if best_only:
        # Expand a tied boundary so top_k cannot silently discard tied videos.
        while limit < count and distances[0][-1] == min(distances[0]):
            limit = min(limit * 2, count)
            response = store.search(embedding, top_k=limit)
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

    if best_only:
        hnsw_configuration = store.collection.configuration.get("hnsw") or {}
        metric = hnsw_configuration.get("space", "l2")
        selected = select_best_videos(results, metric)

        if diagnostics is not None:
            scored = [
                dict(r, score=distance_to_similarity(r["distance"], metric))
                for r in results
            ]

            diagnostics.update(
                raw_chunks=scored,
                grouped_videos=group_by_video(scored),
                selected_videos=selected,
                relevant=bool(selected),
                reason=(
                    "Best video(s) passed the threshold."
                    if selected
                    else (
                        "Best video score is below the threshold."
                        if results
                        else "No candidate chunks returned."
                    )
                ),
            )
        return selected

    return results


def distance_to_similarity(distance, metric):
    if metric == "l2":
        return 1 - distance / 2
    if metric in {"cosine", "ip"}:
        return 1 - distance
    raise ValueError(f"Unsupported video distance metric: {metric}")


def select_best_videos(results, metric="l2", threshold=None):
    # keep every best scoring video that passes the cosine similarity cutoff
    from rag.config.settings import VIDEO_RELEVANCE_THRESHOLD

    if threshold is None:
        threshold = VIDEO_RELEVANCE_THRESHOLD

    if metric not in {"l2", "cosine", "ip"}:
        raise ValueError(f"Unsupported video distance metric: {metric}")

    grouped = group_by_video(results)

    if not grouped:
        return []

    best_distance = grouped[0]["distance"]
    score = distance_to_similarity(best_distance, metric)
    if score < threshold:
        return []
    return [
        dict(result, score=score)
        for result in grouped
        if result["distance"] == best_distance
    ]
