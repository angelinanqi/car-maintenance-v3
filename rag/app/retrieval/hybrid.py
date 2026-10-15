"""Scoped BM25S ranking and rank fusion over the current Chroma records."""
from dataclasses import replace
from functools import lru_cache
import re
from threading import Lock

from rag.app.retrieval.search import RetrievalResult, Searcher
from rag.config import settings

# Keep technical identifiers such as O/D, K3-VE, P0300, 1.3 and units intact.
TOKEN_PATTERN = r"(?u)\b[\w]+(?:[./-][\w]+)*\b"


def tokenize(texts):
    import bm25s
    return bm25s.tokenize(texts, stopwords="en", token_pattern=TOKEN_PATTERN,
                         return_ids=False, show_progress=False)


def scoped_records(store, document_ids, content_type=None):
    if not document_ids:
        return []
    where = document_filter(document_ids)
    if content_type:
        where = {'$and': [where, {'content_type': content_type}]}
    data = store.collection.get(where=where,
                                include=["documents", "metadatas"])
    return [RetrievalResult(i + 1, identity, 0.0, text, dict(metadata or {}))
            for i, (identity, text, metadata) in enumerate(zip(
                data["ids"], data["documents"], data["metadatas"]))]


def document_filter(document_ids):
    if isinstance(document_ids, str) or not document_ids or any(
        not isinstance(identity, str) or not identity.strip() for identity in document_ids
    ):
        raise ValueError("An explicit nonempty document scope is required")
    ids = sorted(set(document_ids))
    if not ids:
        raise ValueError("An explicit nonempty document scope is required")
    return {"document_name": {"$in": ids}}


def lexical_search(query, records, top_k):
    import bm25s
    if top_k < 1:
        raise ValueError("top_k must be greater than 0")
    if not records:
        return []
    query_tokens = tokenize([query])
    if not any(query_tokens):
        return []
    tokens = tokenize([r.text for r in records])
    if not any(tokens):
        return []
    index = bm25s.BM25()
    index.index(tokens, show_progress=False)
    ids, scores = index.retrieve(query_tokens, k=min(top_k, len(records)),
                                 show_progress=False)
    return [replace(records[int(i)], rank=rank)
            for rank, (i, score) in enumerate(zip(ids[0], scores[0]), 1) if score > 0]


def fuse(dense, lexical, *, k=60, dense_weight=1.0, lexical_weight=1.0):
    scores, records = {}, {}
    for ranking, weight in ((dense, dense_weight), (lexical, lexical_weight)):
        seen = set()
        for rank, record in enumerate(ranking, 1):
            if record.chunk_id in seen:
                continue
            seen.add(record.chunk_id)
            records.setdefault(record.chunk_id, record)
            scores[record.chunk_id] = scores.get(record.chunk_id, 0) + weight / (k + rank)
    ordered = sorted(scores, key=lambda identity: (-scores[identity], identity))
    return [replace(records[identity], rank=rank) for rank, identity in enumerate(ordered, 1)]


def adaptive_weights(query):
    # Experimental only; fixed fusion remains the default.
    exact = re.search(r"\b(?:[A-Z]{1,4}\d{2,}|\d\.\d|(?:19|20)\d{2}|O/D|ABS|[A-Z]\d-[A-Z]{2})\b", query)
    return (1.0, 1.5) if exact else (1.0, 1.0)


_rerank_lock = Lock()


@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.RERANK_MODEL, max_length=512)


def rerank(query, records):
    if not records:
        return []
    with _rerank_lock:
        scores = reranker().predict([(query, r.text) for r in records])
    ordered = sorted(zip(scores, records), key=lambda pair: -float(pair[0]))
    return [replace(record, rank=i) for i, (_, record) in enumerate(ordered, 1)]


def search(store, query, embedding, document_ids, *, top_k=5, mode=None,
           use_reranker=None, diagnostics=None, content_type=None):
    mode = mode or settings.RAG_RETRIEVAL_MODE
    if not query.strip():
        raise ValueError("Query cannot be empty")
    if top_k < 1:
        raise ValueError("top_k must be greater than 0")
    if mode not in {"dense", "lexical", "hybrid", "adaptive"}:
        raise ValueError(f"Unknown retrieval mode: {mode}")
    document_filter(document_ids)
    document_ids = list(document_ids)
    records = scoped_records(store, document_ids, content_type)
    if not records:
        return []
    limit = min(max(top_k, settings.RAG_CANDIDATES), len(records))
    dense = []
    if mode != "lexical":
        dense = Searcher._build_results(store.search(embedding, top_k=limit,
                                                      document_ids=document_ids, content_type=content_type))
    lexical = lexical_search(query, records, limit) if mode != "dense" else []
    weights = adaptive_weights(query) if mode == "adaptive" else (1.0, 1.0)
    ranked = dense if mode == "dense" else lexical if mode == "lexical" else fuse(
        dense, lexical, k=settings.RAG_RRF_K, dense_weight=weights[0], lexical_weight=weights[1])
    rerank_enabled = settings.RAG_RERANK if use_reranker is None else use_reranker
    if rerank_enabled:
        ranked = rerank(query, ranked[:limit])
    allowed = set(document_ids)
    if any(r.metadata.get("document_name") not in allowed for r in ranked):
        raise ValueError("Retrieval returned a record outside its document scope")
    if diagnostics is not None:
        diagnostics.update(mode=mode, scoped_chunks=len(records), dense_ids=[r.chunk_id for r in dense],
                           lexical_ids=[r.chunk_id for r in lexical])
    return [replace(r, rank=i) for i, r in enumerate(ranked[:top_k], 1)]
