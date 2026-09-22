import argparse
import asyncio
import json
from pathlib import Path
from rag.app.query import handle_query

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

    parser.add_argument(
        "--document-name", help="Restrict results to this exact manual filename stem."
    )

    parser.add_argument(
        "--history", type=Path, help="JSON list of prior {role, content} messages."
    )

    return parser.parse_args()


def main():
    args = parse_args()

    history = (
        json.loads(args.history.read_text(encoding="utf-8")) if args.history else None
    )

    result = asyncio.run(
        handle_query(
            args.query, history, top_k=args.top_k, document_name=args.document_name
        )
    )

    if result["route"] in {"rag", "rag_with_external_warning"}:
        if not result["context"]:
            print("[Retrieval] No manual content retrieved.")
            
        if not result["videos"]:
            print("[Retrieval] No relevant videos retrieved.")

    if args.show_context:
        print()
        print("=" * 70)
        print("RETRIEVED CONTEXT")
        print("=" * 70)
        print()
        print(f"Route: {result['route']}")
        print(result["context"] or "No manual context for this route/query.")
        print()

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
    print(result["answer"])
    print()


if __name__ == "__main__":
    main()
