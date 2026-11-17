"""Scoped BM25S ranking and rank fusion over the current Chroma records."""
from shared.observability import observed
from dataclasses import replace
from functools import lru_cache
from threading import Lock
import logging
import re

from rag.app.retrieval.search import RetrievalResult, build_results
from rag.config import settings
from rag.app.generation.provider import inference_guard, check_budget

# Keep technical identifiers such as O/D, K3-VE, P0300, 1.3 and units intact.
TOKEN_PATTERN = r"(?u)\b[\w]+(?:[./-][\w]+)*\b"


def _expand_compound(match):
    """Retain exact compounds and expose their word components to BM25."""
    token = match.group()
    parts = re.split(r"[./-]", token)
    # Avoid adding fragments from numbers, mixed codes or short abbreviations.
    if len(parts) > 1 and all(len(part) > 1 and part.isalpha() for part in parts):
        return " ".join([token, *parts])
    return token


def tokenize(texts):
    import bm25s
    # Apply the same representation to documents and queries. BM25S removes
    # stopwords from the added components as well as the original terms.
    texts = [re.sub(TOKEN_PATTERN, _expand_compound, text) for text in texts]
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


@lru_cache(maxsize=8)
def lexical_index(texts):
    """Reuse immutable text snapshots; changed/revoked records never reuse metadata."""
    import bm25s
    tokens = tokenize(list(texts))
    if not any(tokens):
        return None
    index = bm25s.BM25()
    index.index(tokens, show_progress=False)
    return index


@observed('keyword_retrieval')
def lexical_search(query, records, top_k):
    if top_k < 1:
        raise ValueError("top_k must be greater than 0")
    if not records:
        return []
    query_tokens = tokenize([query])
    if not any(query_tokens):
        return []
    index = lexical_index(tuple(r.text for r in records))
    if index is None:
        return []
    ids, scores = index.retrieve(query_tokens, k=min(top_k, len(records)),
                                 show_progress=False)
    return [replace(records[int(i)], rank=rank)
            for rank, (i, score) in enumerate(zip(ids[0], scores[0]), 1) if score > 0]


@observed('result_merging')
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


_rerank_lock = Lock()


@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.RERANK_MODEL, max_length=512, device=settings.MODEL_DEVICE)


@observed('reranking')
def rerank(query, records):
    if not records:
        return []
    with inference_guard(_rerank_lock):
        model = reranker()
        tokenizer = model.tokenizer
        query_ids = tokenizer.encode(query, add_special_tokens=False, truncation=False, verbose=False)
        max_length = getattr(model, 'max_seq_length', None)
        if max_length is None:
            max_length = model.max_length
        budget = max_length - len(query_ids) - tokenizer.num_special_tokens_to_add(pair=True) - 8
        if budget < 64:
            raise ValueError('Reranking query leaves insufficient passage space')
        pairs, owners, counts, sampled = [], [], [], []
        query_tokens = set(query_ids)
        for index, record in enumerate(records):
            tokens = tokenizer.encode(record.text, add_special_tokens=False, truncation=False, verbose=False)
            stride = max(1, budget - min(48, budget // 4))
            starts = list(range(0, max(1, len(tokens) - budget + 1), stride))
            starts.append(max(0, len(tokens) - budget))
            starts = sorted(set(starts))
            # Bound CPU work, keeping both ends and the strongest literal matches.
            selected = {starts[0], starts[-1]}
            for start in sorted(starts, key=lambda s: (-len(query_tokens.intersection(tokens[s:s + budget])), s)):
                if len(selected) >= 8:
                    break
                selected.add(start)
            counts.append(len(selected))
            sampled.append(len(selected) < len(starts))
            for start in sorted(selected):
                pairs.append((query, tokenizer.decode(tokens[start:start + budget], skip_special_tokens=True)))
                owners.append(index)
        predictions = []
        for start in range(0, len(pairs), 16):
            check_budget()
            predictions.extend(model.predict(pairs[start:start + 16], batch_size=16))
        scores = [float('-inf')] * len(records)
        for owner, score in zip(owners, predictions, strict=True):
            scores[owner] = max(scores[owner], float(score))
    ordered = sorted(zip(scores, records), key=lambda pair: -float(pair[0]))
    details = {record.chunk_id: (count, partial) for record, count, partial in zip(records, counts, sampled)}
    return [replace(record, rank=i, metadata={**record.metadata, 'relevance_score':float(score),
                    'rerank_windows': details[record.chunk_id][0], 'rerank_sampled': details[record.chunk_id][1]})
            for i, (score, record) in enumerate(ordered, 1)]


@observed('hybrid_retrieval')
def search(store, query, embedding, document_ids, *, top_k=5, mode=None,
           use_reranker=None, content_type=None):
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
        dense = build_results(store.search(embedding, top_k=limit,
                                                      document_ids=document_ids, content_type=content_type))
    lexical = lexical_search(query, records, limit) if mode != "dense" else []
    # The legacy adaptive setting now uses the same fixed hybrid fusion.
    ranked = dense if mode == "dense" else lexical if mode == "lexical" else fuse(
        dense, lexical, k=settings.RAG_RRF_K)
    rerank_enabled = settings.RAG_RERANK if use_reranker is None else use_reranker
    if rerank_enabled:
        try:
            ranked = rerank(query, ranked[:limit])
        except Exception as error:
            logging.getLogger(__name__).warning("Semantic reranking unavailable; retaining hybrid rank (%s)", type(error).__name__)
    allowed = set(document_ids)
    if any(r.metadata.get("document_name") not in allowed for r in ranked):
        raise ValueError("Retrieval returned a record outside its document scope")
    return [replace(r, rank=i) for i, r in enumerate(ranked[:top_k], 1)]
