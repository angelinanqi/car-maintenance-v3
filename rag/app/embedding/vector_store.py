from shared.observability import observed
from rag.config.settings import RAG_TOP_K
from pathlib import Path
from typing import Any
from threading import Lock
import chromadb
from chromadb.api.types import Metadata, QueryResult, Where

from rag.config.settings import (
    CHROMA_PATH,
    MANUAL_COLLECTION as COLLECTION_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
)
# Chroma publishes its shared backend before its Rust bindings finish starting.
# Serialize construction only, collection searches can still run in parallel.
_CHROMA_INIT_LOCK = Lock()


class IndexConfigurationError(ValueError):
    """The prepared collection does not match the active embedding settings."""


class VectorStore:
    @observed('vector_open')
    def __init__(
        self,
        database_path: Path = CHROMA_PATH,
        collection_name: str = COLLECTION_NAME,
        *,
        create=True
    ):
        database_path = Path(database_path)
        if create:
            database_path.mkdir(parents=True, exist_ok=True)
        elif not (database_path / "chroma.sqlite3").is_file():
            raise FileNotFoundError(
                "No prepared Chroma index. Process an uploaded document and run python -m rag.index_worker."
            )

        with _CHROMA_INIT_LOCK:
            self.client = chromadb.PersistentClient(path=str(database_path))
            if not create:
                self.collection = self.client.get_collection(name=collection_name)
            else:
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={
                        "embedding_model": EMBEDDING_MODEL,
                        "embedding_dimension": EMBEDDING_DIMENSION,
                    },
                )

        metadata = self.collection.metadata or {}
        if (
            metadata.get("embedding_model") != EMBEDDING_MODEL
            or metadata.get("embedding_dimension") != EMBEDDING_DIMENSION
        ):
            raise IndexConfigurationError(
                f"Collection {collection_name!r} has missing or incompatible embedding "
                "metadata. Verify EMBEDDING_MODEL and EMBEDDING_DIMENSION against "
                "the ingestion settings before querying or replacing records."
            )

    @observed('vector_indexing')
    def replace_document(
        self,
        document_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: Any,
        metadatas: list[Metadata],
    ) -> None:
        """
        Replace one manual, including empty replacements. other manuals stay
        embed before calling. Chroma delete n upsert not atomic
        rerun this replacement if a write fails.
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

        old_ids = set(self.collection.get(where={"document_name": document_name}, include=[])["ids"])

        if ids:
            batch_size = self.client.get_max_batch_size()

            for start in range(0, len(ids), batch_size):
                self.upsert(
                    ids[start : start + batch_size],
                    documents[start : start + batch_size],
                    embeddings[start : start + batch_size],
                    metadatas[start : start + batch_size],
                )
        obsolete = old_ids - set(ids)
        if obsolete:
            self.collection.delete(ids=sorted(obsolete))

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

    @observed('semantic_retrieval')
    def search(
        self,
        query_embedding: list[float],
        top_k: int = RAG_TOP_K,
        document_name: str | None = None,
        car_model: str | None = None,
        *,
        document_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        content_type: str | None = None,
        extra_where: dict | None = None,
    ) -> QueryResult:
        if document_ids is not None:
            from rag.app.retrieval.hybrid import document_filter
            where = document_filter(document_ids)
        elif video_ids is not None:
            if not video_ids:
                raise ValueError("An explicit video scope is required")
            where = {"video_id": {"$in": sorted(set(video_ids))}}
        else:
            where: Where | None = (
            {"document_name": document_name} if document_name is not None else None
            )

        if document_ids is None and video_ids is None and not document_name and car_model:
            where = {"car_model": car_model}
        if content_type:
            where = {'$and': [where, {'content_type': content_type}]} if where else {'content_type': content_type}
        if extra_where:
            where = {'$and': [where, extra_where]} if where else extra_where

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
