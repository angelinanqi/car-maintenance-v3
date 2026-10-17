import argparse
from pathlib import Path
from rag.config.settings import YOUTUBE_OUTPUT_DIR as OUTPUT_DIR
from rag.app.youtube.discovery import read_channel, discover_videos
from rag.app.youtube.transcripts import save_json
from rag.app.youtube.ingestion import ingest_videos
from rag.app.youtube.retrieval import open_store
from rag.config.settings import CHROMA_PATH, YOUTUBE_API_KEY

# Reusable YouTube ingestion orchestration, separate from user queries


def run_youtube_ingestion(
    output_dir=OUTPUT_DIR, chroma_path=CHROMA_PATH, rebuild=False
):
    # discover, cache transcripts, chunk and index the configured channel
    output_dir = Path(output_dir)
    channel = read_channel()

    discovered = discover_videos(channel, YOUTUBE_API_KEY)
    metadata_path = (
        output_dir / "videos.json"
    )  # one predefined channel per cache, prevent accidental mixing

    if metadata_path.exists():
        import json

        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        if previous["channel_id"] != discovered["channel_id"]:
            raise ValueError(
                "Channel changed: use separate --output-dir and --chroma-path for another channel."
            )

    store = open_store(chroma_path)
    indexed_channels = store.collection.get(include=["metadatas"])["metadatas"]

    if any(
        m.get("channel_id") != discovered["channel_id"]
        for m in (indexed_channels or [])
        if m is not None
    ):
        raise ValueError(
            "YouTube index contains another channel; use a separate --chroma-path."
        )

    save_json(metadata_path, discovered)
    summary = ingest_videos(discovered["videos"], output_dir, store, rebuild)

    if summary["videos_failed"]:
        raise RuntimeError(
            "YouTube ingestion had video failures; see the console output. Rerun to retry."
        )

    return summary


def main():
    parser = argparse.ArgumentParser(description="Ingest the YouTube channel configured in .env.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--chroma-path", type=Path, default=CHROMA_PATH)
    parser.add_argument("--rebuild", action="store_true", help="Re-embed videos using cached transcripts")
    args = parser.parse_args()
    try:
        run_youtube_ingestion(args.output_dir, args.chroma_path, args.rebuild)
    except Exception as error:
        parser.exit(1, f"YouTube ingestion failed: {error}\n")


if __name__ == "__main__":
    main()
