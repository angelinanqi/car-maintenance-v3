import chromadb


CHROMA_PATH = "output/embeddings/chroma"
COLLECTION_NAME = "rag_chunks"


def main():
    client = chromadb.PersistentClient(
        path=CHROMA_PATH
    )

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    print(f"Collection: {collection.name}")
    print(f"Number of chunks: {collection.count()}")

    result = collection.get(
        limit=3,
        include=["documents", "metadatas"],
    )

    for i in range(len(result["ids"])):
        print("\n" + "=" * 60)
        print(f"ID: {result['ids'][i]}")
        print(f"Metadata: {result['metadatas'][i]}")
        print(f"\nText:\n{result['documents'][i]}")


if __name__ == "__main__":
    main()