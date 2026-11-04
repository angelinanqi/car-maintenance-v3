"""Bound eligible video links; the answer writer selects relevant recommendations."""
import re
import json
import asyncio
import logging
from rag.config.settings import YOUTUBE_OUTPUT_DIR
from rag.app.youtube.retrieval import distance_to_similarity, group_by_video
from shared.safety import videos_allowed
from rag.app.generation.grounded import INJECTION
from rag.config.settings import VIDEO_RELEVANCE_THRESHOLD
from shared.chat_preferences import puncture_repair_request

# Used only to recognise declared vehicle names in untrusted video titles.
# Compatibility is never inferred from a match; the cards remain unverified.
MAKES = ('perodua', 'proton', 'toyota', 'honda', 'nissan', 'mazda', 'subaru',
         'suzuki', 'mitsubishi', 'isuzu', 'daihatsu', 'hyundai', 'kia', 'ford',
         'chevrolet', 'volkswagen', 'audi', 'bmw', 'mercedes benz', 'volvo',
         'peugeot', 'renault', 'lexus', 'tesla', 'byd', 'chery', 'gwm', 'mini',
         'porsche', 'land rover', 'jeep', 'fiat', 'skoda', 'seat')


def vehicle_match(question, title, vehicle, known_vehicle_codes=(), *, intent=None, proactive=False):
    """Reject declared conflicts before the writer selects IDs. Unknown is not proof."""
    from rag.app.generation.grounded import year_matches
    def normalise(text):
        return re.sub(r'[-_/]+', ' ', str(text or '').lower())
    def contains(text, name):
        return bool(re.search(r'\b' + re.escape(name) + r'\b', text))
    selected = vehicle if isinstance(vehicle, dict) else {'code': vehicle or ''}
    target = normalise(question + ' ' + (getattr(intent, 'question', '') or '') + ' '
                       + ' '.join(str(selected.get(k) or '') for k in ('code','name','engine','variant')))
    declared = normalise(title)
    models = {re.sub(r'\s+\d{4}$', '', normalise(code)).split(' ', 1)[-1]
              for code in (*known_vehicle_codes, selected.get('code', '')) if code}
    title_models = {model for model in models if contains(declared, model)}
    title_makes = {make for make in MAKES if contains(declared, make)}
    # Titles outside the manual catalogue may still name a make and model.
    for make in MAKES:
        for match in re.finditer(r'\b' + re.escape(make) + r'\s+([a-z0-9]+)\b', declared):
            model = match.group(1)
            if model not in {'how', 'car', 'cars', 'auto', 'engine', 'brake', 'brakes'}:
                title_models.add(model)
    if title_models and any(not contains(target, model) for model in title_models):
        return None
    if title_makes and not title_models and not any(contains(target, make) for make in title_makes):
        return None
    target_year = getattr(intent, 'requested_year', None) or selected.get('year')
    declared_years = re.findall(r'\b(?:19|20)\d{2}\b', declared)
    if target_year and declared_years and not year_matches(int(target_year), declared):
        return None
    declared_engines = set(re.findall(r'\b\d\.\d\b', declared))
    target_engines = set(re.findall(r'\b\d\.\d\b', target))
    if declared_engines and ((target_engines and not declared_engines & target_engines)
                             or (proactive and not target_engines)):
        return None
    return 'named_model' if title_models or title_makes else 'generic'


def operation_conflict(question, title):
    """A related component must not substitute another procedure or hazardous extra."""
    if puncture_repair_request(question):
        if not re.search(r'\b(?:punctur\w*|plug\w*|patch\w*|flat (?:tyre|tire))\b', title, re.I):
            return True
        if re.search(r'\bchang\w*\b.{0,25}\b(?:tyre|tire|wheel)\b', title, re.I):
            return True
    return bool(re.search(r'\bbrake pads?\b', question, re.I)
                and re.search(r'\bbleed\w*\b|\bbrake fluid\b.{0,15}\b(?:flush|chang\w*)\b', title, re.I))


def confident_proactive(question, candidates):
    """Optional unsolicited links need stronger evidence of task relevance.

    Reuse the already configured local text reranker. Positive logits are a
    conservative heuristic, not a calibrated probability; explicit requests
    retain broader discovery because this model misses some useful tutorials.
    """
    from rag.config.settings import RAG_RERANK
    if not RAG_RERANK or not candidates:
        return []
    try:
        from rag.app.retrieval.hybrid import reranker, _rerank_lock
        descriptions = recommendation_candidates(candidates)
        pairs = [(question, item['title'] + '\n' + item.get('description', '')[:600]) for item in descriptions]
        with _rerank_lock:
            scores = reranker().predict(pairs)
        return [candidate for score, candidate in sorted(zip(scores, candidates), key=lambda pair: -float(pair[0]))
                if float(score) > 0]
    except Exception as error:
        logging.getLogger(__name__).warning('Proactive video relevance unavailable (%s)', type(error).__name__)
        return []  # Optional discovery must not interrupt the supported answer.


async def select_videos(question, candidates, vehicle, metric, *, intent=None, proactive=False, known_vehicle_codes=()):
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
        match = vehicle_match(question, title, vehicle, known_vehicle_codes, intent=intent, proactive=proactive)
        if match is None or operation_conflict(question, title):
            continue
        if (candidate.get('retrieval_method') != 'title_keywords'
                and (candidate.get('distance') is None
                     or distance_to_similarity(candidate['distance'], metric) < VIDEO_RELEVANCE_THRESHOLD)):
            continue
        selected.append({**candidate, 'vehicle_match': match})
    selected = group_by_video(selected)
    selected = selected[:8]
    return await asyncio.to_thread(confident_proactive, question, selected) if proactive else selected


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
             "matched_using": ('title' if video.get('retrieval_method') == 'title_keywords'
                               else "title_and_transcript" if video["metadata"].get("retrieval_content") == "transcript"
                               else "title_and_description"),
             "vehicle_match": video.get('vehicle_match', 'generic'),
             "content_verified": False}
            for index, video in enumerate(videos, 1)]
