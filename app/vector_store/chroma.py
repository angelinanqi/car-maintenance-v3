from pathlib import Path
import chromadb

COLLECTION_NAME = "vehicle_manual_chunks"


class ChromaStore:
    def __init__(self, database_path: Path):
        self.client = chromadb.PersistentClient(path=str(database_path))

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def count(self) -> int:
        return self.collection.count()
