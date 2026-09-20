import argparse
from rag.app.embedding.embedder import Embedder
from rag.app.embedding.vector_store import VectorStore
from rag.app.retrieval.search import Searcher

DEFAULT_QUERY = "What should I do when parking the vehicle on a slope?"
DEFAULT_TOP_K = 5


def parse_args():
    parser = argparse.ArgumentParser(description="Search the RAG vector store.")

    parser.add_argument(
        "--query",
        type=str,
        help="Question to search for.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of results to return. Default: {DEFAULT_TOP_K}",
    )

    parser.add_argument(
        "--document-name", help="Restrict results to this exact manual filename stem."
    )
    return parser.parse_args()


def print_results(
    query: str,
    results,
) -> None:
    print("=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    for result in results:
        print()
        print(f"[{result.rank}]")
        print(f"Chunk ID: {result.chunk_id}")
        print(f"Distance: {result.distance:.4f}")

        metadata = result.metadata

        print(f"Document: " f"{metadata.get('document_name', 'N/A')}")

        print(f"Section: " f"{metadata.get('section_path', 'N/A')}")

        print(f"Node type: " f"{metadata.get('node_type', 'N/A')}")

        print()
        print(result.text)

        print("-" * 70)


def main() -> None:
    args = parse_args()

    query = args.query or DEFAULT_QUERY

    embedder = Embedder()
    vector_store = VectorStore()

    searcher = Searcher(
        embedder=embedder,
        vector_store=vector_store,
    )

    results = searcher.search(
        query=query,
        top_k=args.top_k,
        document_name=args.document_name,
    )

    print_results(
        query=query,
        results=results,
    )


if __name__ == "__main__":
    main()
