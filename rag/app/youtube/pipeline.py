import os
from pathlib import Path
from rag.app.youtube.config import CHANNEL_FILE, OUTPUT_DIR
from rag.app.youtube.discovery import read_channel, discover_videos
from rag.app.youtube.transcripts import save_json
from rag.app.youtube.ingestion import ingest_videos
from rag.app.youtube.retrieval import open_store
from dotenv import load_dotenv

# Reusable YouTube ingestion orchestration, separate from user queries


def run_youtube_ingestion(
    output_dir=OUTPUT_DIR, chroma_path=Path("output/embeddings/chroma"), rebuild=False
):
    # discover, cache transcripts, chunk and index the configured channel
    output_dir = Path(output_dir)
    channel = read_channel(CHANNEL_FILE)

    load_dotenv(Path(".env"))
    discovered = discover_videos(channel, os.getenv("YOUTUBE_API_KEY", ""))
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
            f"YouTube ingestion had video failures; see {output_dir / 'failures.json'}. Rerun to retry."
        )

    return summary
