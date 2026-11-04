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
    for result in sorted(results, key=lambda result: (
            result.get('retrieval_method') != 'title_keywords',
            result['distance'] if result.get('distance') is not None else float('inf'))):
        best.setdefault(result["metadata"]["video_id"], result)
    return list(best.values())


def title_candidates(store, query, where, limit=4):
    """Complement dense recall with scoped title matches, using existing BM25.

    These are discovery candidates, never factual evidence or a fabricated
    vector score. The writer still checks the operation and vehicle match.
    """
    import re
    from rag.app.retrieval.hybrid import lexical_search, tokenize
    from rag.app.retrieval.search import RetrievalResult

    def normalise(text):
        text = re.sub(r'\b(?:tyres?|tires?)\b', 'tyre', text.lower())
        text = re.sub(r'\breplac(?:e|es|ed|ing|ement)\b', 'replace', text)
        return re.sub(r'\b([a-z]{3,})s\b', r'\1', text)

    data = store.collection.get(where=where, include=['documents', 'metadatas'])
    records, originals, rows = [], {}, []
    seen = set()
    for identity, text, metadata in zip(data['ids'], data['documents'], data['metadatas']):
        metadata = metadata or {}
        title = metadata.get('video_title', '')
        video_id = metadata.get('video_id')
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        rows.append((identity, text, metadata, normalise(title)))
    tokens = tokenize([normalise(query)] + [row[3] for row in rows])
    query_terms = set(tokens[0])
    for (identity, text, metadata, title), title_terms in zip(rows, tokens[1:]):
        # A single shared component/creator word is too weak for this fallback.
        if len(query_terms & set(title_terms)) < 2:
            continue
        records.append(RetrievalResult(1, identity, 0, title, metadata))
        originals[identity] = dict(id=identity, text=text, metadata=metadata,
                                  distance=None, retrieval_method='title_keywords')
    return [originals[r.chunk_id] for r in lexical_search(normalise(query), records, limit)]


def retrieve_youtube(
    query,
    top_k=RAG_TOP_K,
    database_path=None,
    *,
    query_embedding=None,
    diagnostics=None,
    video_ids=None,
    guide_video_ids=None,
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
    options = {"video_ids": video_ids} if video_ids is not None else {}
    if video_ids is None and guide_video_ids is not None:
        allowed = {'guide_only': {'$ne': True}}
        if guide_video_ids:
            allowed = {'$or': [allowed, {'video_id': {'$in': sorted(set(guide_video_ids))}}]}
        options['extra_where'] = allowed
    response = store.search(embedding, top_k=limit, **options)
    distances = (response or {}).get("distances") or []

    documents = (response or {}).get("documents") or []
    metadatas = (response or {}).get("metadatas") or []
    ids = (response or {}).get("ids") or []

    distance_row = distances[0] if distances and distances[0] else []
    results = [
        {
            "id": chunk_id,
            "text": documents[0][i],
            "metadata": metadatas[0][i],
            "distance": distance_row[i],
        }
        for i, chunk_id in enumerate(ids[0])
    ] if distance_row and documents and metadatas and ids else []

    where = ({'video_id': {'$in': sorted(set(video_ids))}} if video_ids is not None
             else options.get('extra_where'))
    try:
        lexical = title_candidates(store, query, where)
    except Exception as error:
        import logging
        logging.getLogger(__name__).warning('Video title search unavailable (%s)', type(error).__name__)
        lexical = []
        if diagnostics is not None:
            diagnostics['title_search_error'] = type(error).__name__
    if diagnostics is not None:
        diagnostics['title_candidate_ids'] = [item['metadata']['video_id'] for item in lexical]
    lexical_ids = {item['metadata']['video_id'] for item in lexical}
    # Keep a real dense score where available; lexical-only rows have no score.
    results = [{**item, 'retrieval_method': 'title_keywords'} if item['metadata']['video_id'] in lexical_ids
               else item for item in results]
    existing = {item['metadata']['video_id'] for item in results}
    results.extend(item for item in lexical if item['metadata']['video_id'] not in existing)

    return results


def distance_to_similarity(distance, metric):
    if metric == "l2":
        return 1 - distance / 2
    if metric in {"cosine", "ip"}:
        return 1 - distance
    raise ValueError(f"Unsupported video distance metric: {metric}")
