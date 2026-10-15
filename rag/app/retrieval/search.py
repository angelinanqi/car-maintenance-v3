from dataclasses import dataclass
from typing import Any

from chromadb.api.types import QueryResult


@dataclass
class RetrievalResult:
    rank: int
    chunk_id: str
    distance: float
    text: str
    metadata: dict[str, Any]


def build_results(results: QueryResult) -> list[RetrievalResult]:
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
