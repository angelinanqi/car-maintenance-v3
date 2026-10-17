from rag.config.settings import EMBEDDING_MAX_TOKENS
import json
from hashlib import sha256
from .chunking import chunk_transcript, build_metadata_record
from rag.config.settings import YOUTUBE_CHUNK_TOKENS as CHUNK_TOKENS, YOUTUBE_OVERLAP_TOKENS as OVERLAP_TOKENS
from .transcripts import fetch_transcript, save_json
from .retrieval import create_embedder, replace_video

# save and reuse YouTube data locally to avoid repeating work
# python -m rag.app.youtube.pipeline --rebuild


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
        metadata_only_videos=0,
    )

    embedder = None
    settings = {
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
                try:
                    raw = fetch_transcript(video_id)

                except Exception as error:
                    raw = None
                    reason = " ".join(str(error).split())[:240] or type(error).__name__
                    print(
                        f"[youtube] transcript retrieval for {video_id}: {type(error).__name__}: {reason}"
                    )

                if raw and any(s["text"].strip() for s in raw.get("snippets", [])):
                    save_json(raw_path, raw)  # preserve original snippets bf chunking

                    summary["transcripts_retrieved"] += 1

            if raw and raw["video_id"] != video_id:
                raise ValueError("Cached transcript video ID mismatch.")

            if not raw or not any(s["text"].strip() for s in raw.get("snippets", [])):
                raw = None
                summary["transcripts_failed"] += 1
                print(
                    f"[youtube] transcript unavailable for {video_id}; using title + description fallback"
                )

            else:
                print(
                    f"[youtube] transcript retrieved for {video_id} (fresh or cached)"
                )

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
                if raw:
                    if embedder is None:
                        embedder = create_embedder()
                    chunks = chunk_transcript(
                        video,
                        raw,
                        embedder.model.tokenizer,
                        max_tokens=min(EMBEDDING_MAX_TOKENS, embedder.model.max_seq_length or EMBEDDING_MAX_TOKENS),
                    )

                else:
                    chunks = [build_metadata_record(video)]

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
                if raw is None:
                    summary["metadata_only_videos"] += 1
                continue

            if embedder is None:
                embedder = create_embedder()

            replace_video(store, video_id, chunks, embedder)
            summary["chunks_embedded"] += len(chunks)

            if raw is None:
                summary["metadata_only_videos"] += 1
            print(
                f"[youtube] video {video_id} indexed successfully using {chunks[0]['metadata']['retrieval_content']} ({len(chunks)} records)"
            )

        except Exception as error:
            # isolate every video's fetch/cache/chunk/embed/write failures
            reason = " ".join(str(error).split())[:240] or type(error).__name__
            summary["videos_failed"] += 1

            if stage == "transcript":
                summary["transcripts_failed"] += 1

            print(f"Failed {video_id} ({video.get('title', '')}) [{stage}]: {reason}")

    print(
        "YouTube summary: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )

    return summary
