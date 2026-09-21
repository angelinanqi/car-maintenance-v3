import json
from hashlib import sha256
from .chunking import chunk_transcript
from .config import CHUNK_TOKENS, OVERLAP_TOKENS, CHUNK_VERSION
from .transcripts import fetch_transcript, save_json
from .retrieval import create_embedder, replace_video


def ingest_videos(videos, output_dir, store, rebuild=False):
    """Reuse raw JSON; compare expected IDs with Chroma before embedding."""
    summary = dict(
        videos_discovered=len(videos),
        transcripts_retrieved=0,
        transcripts_cached=0,
        transcripts_failed=0,
        videos_failed=0,
        videos_skipped=0,
        chunks_generated=0,
        chunks_embedded=0,
    )
    failures = []
    embedder = None
    settings = {
        "version": CHUNK_VERSION,
        "target": CHUNK_TOKENS,
        "overlap": OVERLAP_TOKENS,
    }
    for video in videos:
        video_id = video["video_id"]
        stage = "transcript"
        try:
            raw_path = output_dir / "transcripts" / f"{video_id}.json"
            chunks_path = output_dir / "chunks" / f"{video_id}.json"
            if raw_path.exists():
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
                summary["transcripts_cached"] += 1
            else:
                raw = fetch_transcript(video_id)
                save_json(raw_path, raw)  # preserve original snippets bf chunking
                summary["transcripts_retrieved"] += 1
            if raw["video_id"] != video_id:
                raise ValueError("Cached transcript video ID mismatch.")
            stage = "chunking/indexing"
            
            # Cache signature includes raw content and metadata so local edits, new titles and chunk-setting changes automatically rebuild chunks.
            signature = sha256(
                json.dumps(
                    [raw, video, settings], sort_keys=True, ensure_ascii=False
                ).encode()
            ).hexdigest()
            cached = None
            if chunks_path.exists() and not rebuild:
                try:
                    cached = json.loads(chunks_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    pass  # A damaged chunk cache is rebuildable from raw JSON.
            if (
                isinstance(cached, dict)
                and cached.get("signature") == signature
                and cached.get("chunks")
            ):
                chunks = cached["chunks"]
            else:
                if embedder is None:
                    embedder = create_embedder()
                chunks = chunk_transcript(
                    video,
                    raw,
                    embedder.model.tokenizer,
                    max_tokens=min(8192, embedder.model.max_seq_length),
                )
                save_json(
                    chunks_path,
                    {"signature": signature, "settings": settings, "chunks": chunks},
                )
                summary["chunks_generated"] += len(chunks)
            stored_ids = set(
                store.collection.get(where={"video_id": video_id}, include=[])["ids"]
            )
            expected_ids = {chunk["id"] for chunk in chunks}
            if not rebuild and stored_ids == expected_ids:
                summary["videos_skipped"] += 1
                continue
            if embedder is None:
                embedder = create_embedder()
            replace_video(store, video_id, chunks, embedder)
            summary["chunks_embedded"] += len(chunks)
            print(f"Indexed {video_id}: {video['title']} ({len(chunks)} chunks)")
        except Exception as error:
            # isolate every video's fetch/cache/chunk/embed/write failures
            reason = " ".join(str(error).split())[:240] or type(error).__name__
            failures.append(
                {
                    "video_id": video_id,
                    "title": video.get("title", ""),
                    "stage": stage,
                    "reason": reason,
                }
            )
            summary["videos_failed"] += 1
            if stage == "transcript":
                summary["transcripts_failed"] += 1
            print(f"Failed {video_id} ({video.get('title', '')}) [{stage}]: {reason}")
    save_json(output_dir / "failures.json", failures)
    save_json(output_dir / "summary.json", summary)
    print(
        "YouTube summary: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )
    return summary
