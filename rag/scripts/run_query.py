import argparse
import asyncio
import json
from pathlib import Path
from rag.app.query import handle_query
from rag.app.query_diagnostics import print_diagnostics

# run the complete routed chatbot query against prepared indexes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--document-name", help="Exact manual filename stem")
    parser.add_argument(
        "--history", type=Path, help="JSON array of user/assistant messages"
    )
    parser.add_argument(
        "--show-context", action="store_true", help="Include internal diagnostics"
    )

    args = parser.parse_args()

    conversation = (
        json.loads(args.history.read_text(encoding="utf-8")) if args.history else None
    )

    result = asyncio.run(
        handle_query(
            args.query,
            conversation,
            top_k=args.top_k,
            document_name=args.document_name,
            debug=args.show_context,
        )
    )

    if args.show_context:
        print("RETRIEVAL AND GENERATION DIAGNOSTICS")
        print_diagnostics(result)

    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"context", "diagnostics"}
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
