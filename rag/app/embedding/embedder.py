from sentence_transformers import SentenceTransformer

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"


class Embedder:
    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed chunk text for storage in the vector database.
        Nomic requires the search_document prefix for documents.
        """
        inputs = [f"search_document: {text}" for text in texts]
        embeddings = self.model.encode(
            inputs,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a user query.
        Nomic requires the search_query prefix for queries.
        """
        text = f"search_query: {query}"

        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
        )
        return embedding.tolist()
