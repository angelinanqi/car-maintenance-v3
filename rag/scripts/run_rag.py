import argparse
from rag.app.embedding.embedder import Embedder
from rag.app.embedding.vector_store import VectorStore
from rag.app.generation.ollama import OllamaClient
from rag.app.generation.prompt import build_context, build_prompt
from rag.app.retrieval.search import Searcher

DEFAULT_QUERY = "How do I start the engine?"
DEFAULT_TOP_K = 5


def parse_args():
    parser = argparse.ArgumentParser(description="Run RAG search and LLM generation.")

    parser.add_argument(
        "--query",
        type=str,
        default=DEFAULT_QUERY,
        help="Question to ask the RAG system.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of chunks to retrieve.",
    )

    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Show the retrieved context before the answer.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    embedder = Embedder()
    vector_store = VectorStore()

    searcher = Searcher(
        embedder=embedder,
        vector_store=vector_store,
    )

    ollama = OllamaClient()

    results = searcher.search(
        query=args.query,
        top_k=args.top_k,
    )

    context = build_context(results)

    prompt = build_prompt(
        query=args.query,
        context=context,
    )

    if args.show_context:
        print()
        print("=" * 70)
        print("RETRIEVED CONTEXT")
        print("=" * 70)
        print()
        print(context)
        print()

    answer = ollama.generate(prompt)

    print()
    print("=" * 70)
    print("QUESTION")
    print("=" * 70)
    print()
    print(args.query)

    print()
    print("=" * 70)
    print("ANSWER")
    print("=" * 70)
    print()
    print(answer)
    print()


if __name__ == "__main__":
    main()
