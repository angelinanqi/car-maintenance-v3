import argparse
import os
from pathlib import Path
from rag.app.youtube.config import CHANNEL_FILE, OUTPUT_DIR
from rag.app.youtube.discovery import read_channel, discover_videos
from rag.app.youtube.transcripts import save_json
from rag.app.youtube.ingestion import ingest_videos
from rag.app.youtube.retrieval import open_store

# python -m rag.scripts.run_youtube_ingestion

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
        channel = read_channel(CHANNEL_FILE)
        from dotenv import load_dotenv

        load_dotenv(Path(".env"))
        discovered = discover_videos(channel, os.getenv("YOUTUBE_API_KEY", ""))
        # one predefined channel per cache/index. prevent accidental mixing
        metadata_path = args.output_dir / "videos.json"
        if metadata_path.exists():
            import json

            previous = json.loads(metadata_path.read_text(encoding="utf-8"))
            if previous["channel_id"] != discovered["channel_id"]:
                raise ValueError(
                    "Channel changed: use separate --output-dir and --chroma-path for another channel."
                )
        store = open_store(args.chroma_path)
        indexed_channels = (
            store.collection.get(include=["metadatas"]).get("metadatas") or []
        )
        if any(
            m.get("channel_id") != discovered["channel_id"] for m in indexed_channels
        ):
            raise ValueError(
                "YouTube index contains another channel; use a separate --chroma-path."
            )
        save_json(metadata_path, discovered)
        summary = ingest_videos(
            discovered["videos"], args.output_dir, store, args.rebuild
        )
    except Exception as error:
        parser.exit(1, f"YouTube ingestion failed: {error}\n")
    if summary["videos_failed"]:
        parser.exit(
            1,
            "Completed with video failures; see output directory failures.json. Rerun to retry.\n",
        )


if __name__ == "__main__":
    main()
