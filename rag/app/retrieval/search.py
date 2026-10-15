from rag.config.settings import RAG_TOP_K
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from chromadb.api.types import QueryResult

if TYPE_CHECKING:
    from rag.app.embedding.embedder import Embedder
    from rag.app.embedding.vector_store import VectorStore


@dataclass
class RetrievalResult:
    rank: int
    chunk_id: str
    distance: float
    text: str
    metadata: dict[str, Any]


class Searcher:
    def __init__(
        self,
        embedder: "Embedder",
        vector_store: "VectorStore",
    ):
        self.embedder = embedder
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        document_name: str | None = None,
    ) -> list[RetrievalResult]:

        if not query.strip():
            raise ValueError("Query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")
        if document_name is not None and not document_name.strip():
            raise ValueError("document_name cannot be blank")

        query_embedding = self.embedder.embed_query(query)

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            document_name=document_name,
        )

        return self._build_results(results)

    @staticmethod
    def _build_results(
        results: QueryResult,
    ) -> list[RetrievalResult]:

        ids = results["ids"]
        distances = results["distances"]
        documents = results["documents"]
        metadatas = results["metadatas"]

        if ids is None or distances is None or documents is None or metadatas is None:
            raise ValueError("Chroma search did not return the expected result fields.")

        retrieval_results = []

        for index, chunk_id in enumerate(ids[0]):
            retrieval_results.append(
                RetrievalResult(
                    rank=index + 1,
                    chunk_id=chunk_id,
                    distance=distances[0][index],
                    text=documents[0][index],
                    metadata=dict(metadatas[0][index] or {}),
                )
            )

        return retrieval_results
