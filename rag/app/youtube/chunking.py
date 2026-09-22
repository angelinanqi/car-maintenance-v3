from hashlib import sha256
import json
import math

from .config import CHUNK_TOKENS, OVERLAP_TOKENS


def chunk_transcript(
    video,
    transcript,
    tokenizer,
    target=CHUNK_TOKENS,
    overlap=OVERLAP_TOKENS,
    max_tokens=8192,
):
    if not 0 <= overlap < target:
        raise ValueError("Require 0 <= overlap < target tokens.")
    snippets = []
    previous_start = -1
    for snippet in transcript["snippets"]:
        text = " ".join(snippet["text"].split())
        start, duration = float(snippet["start"]), float(snippet["duration"])
        if (
            not all(math.isfinite(n) and n >= 0 for n in (start, duration))
            or start < previous_start
        ):
            raise ValueError(
                "Transcript timestamps must be finite, nonnegative and ordered."
            )
        previous_start = start
        if text:
            snippets.append({"text": text, "start": start, "duration": duration})
    if not snippets:
        raise ValueError("Transcript contains no nonblank snippets.")

    def tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False))

    chunks = []
    first = 0
    while first < len(snippets):
        end = first
        texts = []
        while end < len(snippets):
            candidate = " ".join(texts + [snippets[end]["text"]])
            # todo: include prefix and special tokens in the actual runtime limit
            length = len(
                tokenizer.encode(
                    f"search_document: Title: {video['title']}\nTranscript: {candidate}",
                    add_special_tokens=True,
                )
            )
            if length > max_tokens:
                if not texts:
                    raise ValueError(
                        "One atomic transcript snippet exceeds the embedding context limit."
                    )
                break
            texts.append(snippets[end]["text"])
            end += 1
            if tokens(candidate) >= target:
                break
        metadata = {
            "source_type": "youtube",
            "retrieval_content": "transcript",
            "video_id": video["video_id"],
            "video_title": video["title"],
            "channel_id": video["channel_id"],
            "start_seconds": snippets[first]["start"],
            "end_seconds": snippets[end - 1]["start"] + snippets[end - 1]["duration"],
            "language": transcript["language"],
            "is_generated": transcript["is_generated"],
        }
        chunk = {
            "text": f"Title: {video['title']}\nTranscript: {' '.join(texts)}",
            "metadata": metadata,
        }
        digest = sha256(
            json.dumps(chunk, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        chunk["id"] = f"youtube_{video['video_id']}_{first}_{digest}"
        chunks.append(chunk)
        if end == len(snippets):
            break
        next_first = end
        # approximately overlap tokens; always advance at least one snippet, and leave room for new content in next window
        while overlap and next_first > first + 1:
            tail = " ".join(s["text"] for s in snippets[next_first - 1 : end])
            if tokens(tail) > overlap:
                break
            next_first -= 1
        first = next_first
    return chunks


def build_metadata_record(video):
    title = (video.get("title") or "").strip()
    description = (video.get("description") or "").strip()

    if not title and not description:
        raise ValueError("No usable title or description for metadata fallback.")

    text = "\n".join(
        part
        for part in (
            f"Title: {title}" if title else "",
            f"Description: {description}" if description else "",
        )
        if part
    )

    record = {
        "text": text,
        "metadata": {
            "source_type": "youtube",
            "video_id": video["video_id"],
            "video_title": title,
            "channel_id": video["channel_id"],
            "retrieval_content": "metadata_only",
        },
    }

    digest = sha256(
        json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    record["id"] = f"youtube_{video['video_id']}_metadata_{digest}"

    return record
