import argparse
import json
import re
from pathlib import Path
from filelock import FileLock
from rag.config.settings import YOUTUBE_OUTPUT_DIR as OUTPUT_DIR
from rag.app.youtube.discovery import read_channel, discover_videos
from rag.app.youtube.transcripts import save_json
from rag.app.youtube.ingestion import ingest_videos
from rag.app.youtube.retrieval import open_store
from rag.config.settings import CHROMA_PATH, YOUTUBE_API_KEY


def ingest_guide_videos(videos, output_dir=OUTPUT_DIR, chroma_path=CHROMA_PATH):
    """Register exact embedded videos with the same ingestor, cache and collection."""
    if not videos:
        return []
    chroma_path = Path(chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    warnings = []
    with FileLock(str(chroma_path / '.youtube-ingestion.lock'), timeout=0):
        store = open_store(chroma_path)
        try:
            for video in videos:
                identity = video['video_id']
                existing = store.collection.get(where={'video_id': identity}, include=['metadatas'])
                if existing['ids'] and any(item.get('retrieval_content') == 'transcript'
                                          or not item.get('guide_only') for item in existing['metadatas']):
                    continue  # Reuse channel-indexed videos and videos shared by other guides.
                metadata = dict(video_id=identity, title=video.get('title') or f'YouTube video {identity}',
                                description='', channel_id='', guide_only=True)
                if YOUTUBE_API_KEY:
                    try:
                        from rag.app.youtube.discovery import api_get
                        items = api_get('videos', YOUTUBE_API_KEY, part='snippet', id=identity).get('items', [])
                        snippet = items[0]['snippet'] if items else {}
                        metadata.update(title=snippet.get('title') or metadata['title'],
                                        description=snippet.get('description', ''), channel_id=snippet.get('channelId', ''))
                    except Exception:
                        # Captions can still be fetched when the metadata API is unavailable.
                        pass
                summary = ingest_videos([metadata], Path(output_dir) / 'embedded', store)
                if summary['videos_failed'] or summary['transcripts_failed']:
                    warnings.append(f'YouTube {identity}: transcript unavailable; video remains linked in the guide.')
        finally:
            store.client.close()
    return warnings

# Reusable YouTube ingestion orchestration, separate from user queries


def run_youtube_ingestion(
    output_dir=OUTPUT_DIR, chroma_path=CHROMA_PATH, rebuild=False, *, channel_url=None
):
    # Each channel has its own cache; all channels share the retrieval collection.
    output_dir = Path(output_dir)
    chroma_path = Path(chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    # Serialize replacement writes if CLI ingestion overlaps the worker.
    with FileLock(str(chroma_path / ".youtube-ingestion.lock"), timeout=0):
        discovered = discover_videos(read_channel(channel_url), YOUTUBE_API_KEY)
        channel_id = discovered["channel_id"]
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
            raise ValueError("YouTube returned an invalid channel ID.")
        channel_dir = output_dir / "channels" / channel_id
        # Reuse the old single-channel cache on existing installations.
        legacy_metadata = output_dir / "videos.json"
        if legacy_metadata.is_file():
            previous = json.loads(legacy_metadata.read_text(encoding="utf-8"))
            if previous.get("channel_id") == channel_id:
                channel_dir = output_dir
        save_json(channel_dir / "videos.json", discovered)
        store = open_store(chroma_path)
        try:
            summary = ingest_videos(discovered["videos"], channel_dir, store, rebuild)
        finally:
            store.client.close()
        return {"channel_id": channel_id, "channel_title": discovered["channel_title"], "summary": summary}


def main():
    parser = argparse.ArgumentParser(description="Discover and embed a YouTube channel.")
    parser.add_argument("--channel-url", help="YouTube channel URL; defaults to legacy YOUTUBE_CHANNEL_URL")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--chroma-path", type=Path, default=CHROMA_PATH)
    parser.add_argument("--rebuild", action="store_true", help="Re-embed videos using cached transcripts")
    args = parser.parse_args()
    try:
        result = run_youtube_ingestion(args.output_dir, args.chroma_path, args.rebuild, channel_url=args.channel_url)
        if result["summary"]["videos_failed"]:
            raise RuntimeError("Some videos failed to index. Rerun to retry; see the console output.")
    except Exception as error:
        parser.exit(1, f"YouTube ingestion failed: {error}\n")


if __name__ == "__main__":
    main()
