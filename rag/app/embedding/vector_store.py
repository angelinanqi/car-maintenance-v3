from pathlib import Path
from typing import Any
import chromadb
from chromadb.api.types import QueryResult, Metadata

CHROMA_PATH = Path("output/embeddings/chroma")
COLLECTION_NAME = "rag_chunks"


class VectorStore:
    def __init__(self):
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_PATH)
        )

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "embedding_model": "nomic-ai/nomic-embed-text-v1.5",
                "embedding_dimension": 768,
            },
        )

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: Any,
        metadatas: list[Metadata],
    ):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> QueryResult:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )