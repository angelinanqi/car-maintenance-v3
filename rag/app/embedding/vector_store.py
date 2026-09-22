from pathlib import Path
from typing import Any
from threading import Lock
import chromadb
from chromadb.api.types import Metadata, QueryResult, Where

CHROMA_PATH = Path("output/embeddings/chroma")
COLLECTION_NAME = "rag_chunks"
# Chroma publishes its shared backend before its Rust bindings finish starting.
# Serialize construction only; collection searches can still run in parallel.
_CHROMA_INIT_LOCK = Lock()


class VectorStore:
    def __init__(
        self, database_path: Path = CHROMA_PATH, collection_name: str = COLLECTION_NAME
    ):

        database_path.mkdir(parents=True, exist_ok=True)

        with _CHROMA_INIT_LOCK:
            self.client = chromadb.PersistentClient(path=str(database_path))
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "embedding_model": "nomic-ai/nomic-embed-text-v1.5",
                    "embedding_dimension": 768,
                },
            )

    def replace_document(
        self,
        document_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: Any,
        metadatas: list[Metadata],
    ) -> None:
        """Replace one manual, including empty replacements; other manuals stay.

        Embed/validate before calling. Chroma delete + upsert is not atomic;
        rerun this replacement if a write fails. Do not run concurrent writers.
        """
        if not document_name or not (
            len(ids) == len(documents) == len(embeddings) == len(metadatas)
        ):
            raise ValueError("Invalid document replacement")

        if len(set(ids)) != len(ids) or any(
            metadata.get("document_name") != document_name for metadata in metadatas
        ):
            raise ValueError(
                "Replacement IDs must be unique and metadata must match the document"
            )

        self.collection.delete(where={"document_name": document_name})

        if ids:
            batch_size = self.client.get_max_batch_size()

            for start in range(0, len(ids), batch_size):
                self.upsert(
                    ids[start : start + batch_size],
                    documents[start : start + batch_size],
                    embeddings[start : start + batch_size],
                    metadatas[start : start + batch_size],
                )

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: Any,
        metadatas: list[Metadata],
    ) -> None:
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
        document_name: str | None = None,
    ) -> QueryResult:
        where: Where | None = (
            {"document_name": document_name} if document_name is not None else None
        )

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )
