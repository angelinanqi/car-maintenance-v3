import argparse
import json
from rag.pipeline import process_documents, run_pipeline
from rag.app.youtube.pipeline import run_youtube_ingestion

# Prepare manual and YouTube indexes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", default="data/markdown", help="Prepared Markdown file/directory"
    )
    parser.add_argument(
        "--pdf",
        nargs="+",
        help="Process uploaded PDFs instead of prepared Markdown (manual ingestion only)",
    )
    parser.add_argument("--mineru-executable", help="Path to MinerU executable")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force YouTube re-embedding using cached transcripts",
    )

    args = parser.parse_args()

    try:
        if args.pdf:
            results = process_documents(
                args.pdf, mineru_executable=args.mineru_executable
            )

            print(json.dumps(results, indent=2))

            if not all(result["success"] for result in results):
                parser.exit(1)

            return
        run_pipeline(args.input)
        run_youtube_ingestion(rebuild=args.rebuild)

    except Exception as error:
        parser.exit(
            1,
            f"Ingestion failed: {error}\nCompleted stages are retained; rerun to retry.\n",
        )
    print("Manual and YouTube ingestion completed.")


if __name__ == "__main__":
    main()
