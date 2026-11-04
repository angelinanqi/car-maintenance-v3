"""Bound eligible video links; the answer writer selects relevant recommendations."""
import re
import json
from rag.config.settings import YOUTUBE_OUTPUT_DIR
from rag.app.youtube.retrieval import distance_to_similarity, group_by_video
from shared.safety import videos_allowed
from rag.app.generation.grounded import INJECTION
from rag.config.settings import VIDEO_RELEVANCE_THRESHOLD


async def select_videos(question, candidates, vehicle, metric, *, intent=None):
    if not videos_allowed(intent):
        return []
    selected = []
    for candidate in candidates:
        m = candidate["metadata"]
        title = m.get("video_title", "")
        if (not re.fullmatch(r"[A-Za-z0-9_-]{11}", m.get("video_id", ""))
                or not title.strip() or not (m.get("channel_id") or m.get("guide_only"))
                or m.get("retrieval_content") not in {"transcript", "metadata_only"}):
            continue
        if INJECTION.search(title + "\n" + candidate["text"]):
            continue
        if distance_to_similarity(candidate["distance"], metric) < VIDEO_RELEVANCE_THRESHOLD:
            continue
        selected.append(candidate)
    selected = group_by_video(selected)
    return selected[:8]


def recommendation_candidates(videos):
    """Metadata supports discovery only; never send a transcript as answer evidence."""
    channels = {}
    for video in videos:
        channel_id = video['metadata'].get('channel_id', '')
        if channel_id in channels or not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', channel_id):
            continue
        # Existing cached discovery metadata supplies publisher names without
        # reindexing videos or making a YouTube request during chat.
        for path in (YOUTUBE_OUTPUT_DIR / 'channels' / channel_id / 'videos.json',
                     YOUTUBE_OUTPUT_DIR / 'videos.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if data.get('channel_id') == channel_id:
                channels[channel_id] = data.get('channel_title', '')
                break
    return [{"id": f"Y{index}", "title": video["metadata"]["video_title"],
             "channel_title": video['metadata'].get('channel_title') or channels.get(video['metadata'].get('channel_id'), ''),
             "description": (video["text"].split("Description:", 1)[1][:1200]
                             if video["metadata"].get("retrieval_content") == "metadata_only"
                             and "Description:" in video["text"] else ""),
             "matched_using": ("title_and_transcript" if video["metadata"].get("retrieval_content") == "transcript"
                               else "title_and_description"),
             "content_verified": False}
            for index, video in enumerate(videos, 1)]
