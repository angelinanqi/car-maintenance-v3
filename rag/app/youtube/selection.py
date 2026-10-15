"""Deterministic supplementary-video selection; transcripts never authorize repairs."""
import re
from rag.app.youtube.retrieval import distance_to_similarity, group_by_video
from rag.app.safety import policy_risk
from rag.app.generation.grounded import topic_matches, INJECTION, words
from rag.config.settings import VIDEO_RELEVANCE_THRESHOLD


def is_instruction_request(question):
    if re.search(r"\b(how often|interval|schedule|due|pressure|torque|capacity)\b", question, re.I):
        return False
    return bool(re.search(r"\b(how (?:do|can|should|to)|instructions|steps|procedure|tutorial|show me|video)\b", question, re.I)
                or re.match(r"(?:please )?(?:check|inspect|replace|change|clean|adjust)\b", question, re.I))


def matches_explicit_variant(question, title, vehicle):
    engines = re.findall(r"\b(\d\.\d)\s*(?:litres?|liters?|l|auto|manual)\b", question, re.I)
    if any(engine not in title for engine in engines):
        return False
    for kind in ("auto", "automatic", "manual transmission", "cvt", "dct"):
        if re.search(r"\b" + kind + r"\b", question, re.I) and not re.search(r"\b" + kind + r"\b", title, re.I):
            return False
    return True


async def select_videos(question, candidates, vehicle, client, diagnostics):
    diagnostics.update(video_llm_calls=0, relevant=False, selected_videos=[])
    if policy_risk(question) in {"high_risk", "emergency", "caution"} or not is_instruction_request(question):
        return []
    selected = []
    metric = diagnostics.get("metric") or "l2"
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
        if not matches_explicit_variant(question, title, vehicle):
            continue
        years = set(re.findall(r"\b(?:19|20)\d{2}\b", question))
        if not years.issubset(set(re.findall(r"\b(?:19|20)\d{2}\b", title))):
            continue
        if distance_to_similarity(candidate["distance"], metric) < VIDEO_RELEVANCE_THRESHOLD:
            continue
        # Exact operation and subject evidence; score alone cannot select a clip.
        operation = re.search(r"\b(check|inspect|replace|change|remove|install|clean|adjust|reset)\b", question, re.I)
        if operation and not words(operation.group(1)) & words(transcript):
            continue
        # Compatibility identifiers have already been checked against the
        # title. They need not be repeated in every timestamped excerpt.
        task = re.sub(r"\b(?:19|20)\d{2}\b|\b\d\.\d\b|\b(auto|automatic|manual|transmission)\b", "", question, flags=re.I)
        if vehicle:
            task = re.sub(r"\b" + re.escape(vehicle) + r"\b", "", task, flags=re.I)
        if not topic_matches(task, transcript):
            continue
        selected.append(candidate)
    selected = group_by_video(selected)
    diagnostics.update(selected_videos=selected, relevant=bool(selected),
                       reason="Assigned clips with matching transcript terms; supplementary only.")
    return selected
