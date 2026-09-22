import argparse
from rag.pipeline import run_pipeline
from rag.app.youtube.pipeline import run_youtube_ingestion

# Prepare manual and YouTube indexes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    
    parser.add_argument(
        "--input",
        default="data/markdown",
        help="Prepared Markdown file/directory; OCR is still a placeholder",
    )
    
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force YouTube re-embedding using cached transcripts",
    )
    
    args = parser.parse_args()
    
    try:
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
