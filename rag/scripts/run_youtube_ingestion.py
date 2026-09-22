# python -m rag.scripts.run_youtube_ingestion
import argparse
from pathlib import Path
from rag.app.youtube.config import OUTPUT_DIR
from rag.app.youtube.pipeline import run_youtube_ingestion


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally ingest the configured YouTube channel."
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--chroma-path", type=Path, default=Path("output/embeddings/chroma")
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Regenerate text records and embeddings, reusing saved transcripts. Does not purge data.",
    )

    args = parser.parse_args()

    try:
        run_youtube_ingestion(args.output_dir, args.chroma_path, args.rebuild)
    except Exception as error:
        parser.exit(1, f"YouTube ingestion failed: {error}\n")


if __name__ == "__main__":
    main()
