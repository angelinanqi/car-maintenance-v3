import chromadb

from rag.app.embedding.embedder import Embedder

CHROMA_PATH = "output/embeddings/chroma"
COLLECTION_NAME = "rag_chunks"


def main():
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    collection = client.get_collection(name=COLLECTION_NAME)

    embedder = Embedder()

    query = "What should I do when parking the vehicle on a slope?"

    query_embedding = embedder.embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5,
    )

    for i in range(len(results["ids"][0])):
        print("\n" + "=" * 70)

        print(f"Rank: {i + 1}")
        print(f"ID: {results['ids'][0][i]}")
        print(f"Distance: {results['distances'][0][i]}")

        print(f"\nMetadata:\n" f"{results['metadatas'][0][i]}")

        print(f"\nText:\n" f"{results['documents'][0][i]}")


if __name__ == "__main__":
    main()
