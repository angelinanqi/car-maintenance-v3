from rag.config.settings import EMBEDDING_BATCH_SIZE
from threading import Lock

from rag.config.settings import EMBEDDING_MODEL as MODEL_NAME
from rag.config.settings import EMBEDDING_DIMENSION, EMBEDDING_MAX_TOKENS, EMBEDDING_CPU_THREADS

_query_embedder = None
_query_lock = Lock()


def embed_query(query: str) -> list[float]:
    """Reuse one query encoder per process; serialize initialization and inference.

    Only model weights are retained. Queries, answers, scopes and index results
    are never cached. Restart the process after changing embedding settings.
    """
    global _query_embedder
    with _query_lock:
        if _query_embedder is None:
            _query_embedder = Embedder()
        return _query_embedder.embed_query(query)


def embed_documents(texts: tuple[str, ...]) -> list[list[float]]:
    """Use the same encoder for current published guide snapshots."""
    global _query_embedder
    with _query_lock:
        if _query_embedder is None:
            _query_embedder = Embedder()
        return _query_embedder.embed_documents(list(texts))


class Embedder:
    def __init__(self):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(EMBEDDING_CPU_THREADS)
        self.model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
        actual_dimension = self.model.get_sentence_embedding_dimension()
        if actual_dimension != EMBEDDING_DIMENSION:
            raise ValueError(f"EMBEDDING_DIMENSION={EMBEDDING_DIMENSION} does not match {MODEL_NAME} ({actual_dimension}). Rebuild with consistent settings.")
        self.model.max_seq_length = min(self.model.max_seq_length, EMBEDDING_MAX_TOKENS)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed chunk text for storage in the vector database.
        Nomic requires the search_document prefix for documents.
        """
        inputs = [f"search_document: {text}" for text in texts]
        lengths = self.model.tokenizer(inputs, truncation=False, return_length=True)["length"]
        for index, length in enumerate(lengths, start=1):
            if length > self.model.max_seq_length:
                raise ValueError(
                    f"Chunk #{index} has {length} tokens including its context and embedding prefix; "
                    f"the embedding model limit is {self.model.max_seq_length}. "
                    "Review the source block boundaries before reindexing; no text was truncated."
                )
        embeddings = self.model.encode(
            inputs,
            normalize_embeddings=True,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a user query.
        Nomic requires the search_query prefix for queries.
        """
        text = f"search_query: {query}"
        if not query.strip():
            raise ValueError("Query cannot be empty")
        length = self.model.tokenizer(text, truncation=False, return_length=True)["length"]
        if isinstance(length, list):
            length = length[0]
        if length > self.model.max_seq_length:
            raise ValueError("Query exceeds the embedding model's token limit; shorten the question or conversation context")

        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
        )
        return embedding.tolist()
