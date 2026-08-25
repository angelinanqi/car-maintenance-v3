from pathlib import Path
import chromadb

CHROMA_PATH = Path("output/embeddings/chroma")
COLLECTION_NAME = "rag_chunks"


class VectorStore:
    def __init__(self):
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))

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
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        embedding: list[float],
        n_results: int = 5,
    ):
        return self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )
