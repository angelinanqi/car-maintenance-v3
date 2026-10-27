"""Deterministic supplementary-video selection; transcripts never authorize repairs."""
import re
from rag.app.youtube.retrieval import distance_to_similarity, group_by_video
from rag.app.safety import videos_allowed
from rag.app.generation.grounded import INJECTION
from rag.config.settings import VIDEO_RELEVANCE_THRESHOLD


async def select_videos(question, candidates, vehicle, metric, *, intent=None):
    if not videos_allowed(intent):
        return []
    selected = []
    for candidate in candidates:
        m = candidate["metadata"]
        title = m.get("video_title", "")
        if m.get("retrieval_content") != "transcript" or "Transcript:" not in candidate["text"]:
            continue
        transcript = candidate["text"].split("Transcript:", 1)[1]
        if len(set(re.findall(r"\w+", transcript))) < 8 or INJECTION.search(transcript):
            continue
        if vehicle and not re.search(r"\b" + re.escape(vehicle) + r"\b", title, re.I):
            continue
        if any(value and value.casefold() not in title.casefold()
               for value in (intent.requested_engine, intent.requested_variant)):
            continue
        if intent.requested_year and str(intent.requested_year) not in title:
            continue
        if distance_to_similarity(candidate["distance"], metric) < VIDEO_RELEVANCE_THRESHOLD:
            continue
        selected.append(candidate)
    selected = group_by_video(selected)
    return selected
