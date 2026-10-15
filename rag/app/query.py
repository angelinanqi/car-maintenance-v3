"""Document-scoped RAG with configurable grounded answer generation."""
import asyncio
from dataclasses import replace
import logging
import re
import json
from time import perf_counter
from functools import lru_cache
from rag.config import settings
from rag.app.generation.provider import GenerationClient, FALLBACK_NOTICE
from rag.app.generation.grounded import applicable, generate, INSUFFICIENT, CLARIFY
from rag.app.safety import policy_risk, emergency_guidance, RESTRICTED_ANSWER
from rag.app.youtube.retrieval import retrieve_youtube, timestamp_url
from rag.app.retrieval.content import retrieve_content, retrieve_emergency, render_emergency, public_source

NO_MANUAL = INSUFFICIENT
MANUAL_UNAVAILABLE = "The manual search is temporarily unavailable. Please try again shortly."
MODEL_UNAVAILABLE = "I couldn't complete the manual answer right now. Please try again shortly."
EXTERNAL_WARNING = "Manufacturer guidance does not establish current legal requirements. Verify these with the relevant official transport authority."
logger = logging.getLogger(__name__)


def recent_context(history):
    return [{"role": m["role"], "content": m["content"]}
            for m in (history or [])[-settings.CHAT_HISTORY_LIMIT:]
            if m.get("role") in {"user", "assistant"} and isinstance(m.get("content"), str)]


def expand_retrieval_query(query):
    text = query.lower()
    if re.search(r"\b(how often|interval|schedule|due)\b|when.*\b(change|replace|service)\b", text):
        query += " Maintenance schedule service interval"
        if "oil" in text and not any(w in text for w in ("transmission", "gear", "brake", "steering")):
            query += " engine oil oil filter"
    return query


def build_retrieval_query(query, history=None, *, expand=True):
    def reference(message):
        text = message.lower().strip().rstrip("?!.")
        return bool(re.search(r"\b(it|its|they|them|those|there)\b|\b(this|that)$", text)
                    or text in {"how often", "how much", "where", "why", "how"}
                    or text.startswith(("what about", "and ")))
    users = [m["content"] for m in recent_context(history) if m["role"] == "user"]
    substitute = re.fullmatch(r"(?:what about|and)\s+(?:the\s+)?(coolant|engine oil|oil|brake fluid|transmission fluid|tyres?|tires?|battery)\??", query.strip(), re.I)
    if substitute and users:
        previous = users[-1]
        if re.search(r"\b(check|inspect|replace|change|locate|find)\b", previous, re.I):
            resolved = re.sub(r"\b(engine oil|brake fluid|transmission fluid|coolant|oil|tyres?|tires?|battery)\b", substitute.group(1), previous, flags=re.I)
            if resolved != previous:
                return expand_retrieval_query(resolved) if expand else resolved
    messages = [query]
    if reference(query):
        for previous in reversed(users):
            messages.insert(0, previous)
            if not reference(previous):
                break
    return "\nFollow-up: ".join(expand_retrieval_query(m) if expand else m for m in messages)


@lru_cache(maxsize=1)
def query_language_detector():
    from rag.app.cleaning.language_detector import LanguageDetector
    return LanguageDetector()


def casual_response(query):
    text = query.lower().strip(" .!?")
    if re.fullmatch(r"(?:hi|hello|hey|good morning|good afternoon|good evening)(?: there)?", text):
        return "Hello! Ask a car-maintenance question about your selected knowledge scope."
    if re.fullmatch(r"(?:thanks|thank you|thank you very much|cheers|ok|okay)", text):
        return "You're welcome."
    if re.fullmatch(r"(?:bye|goodbye|see you|good night)", text):
        return "Goodbye. Take care!"
    return None


async def classify_query(query, history=None, *, diagnostics=None):
    resolved = build_retrieval_query(query, history, expand=False)
    risk = policy_risk(resolved)
    if diagnostics is not None:
        diagnostics.update(risk=risk, routing_llm_calls=0)
    if risk == "emergency":
        return "emergency"
    if risk == "high_risk":
        return "restricted"
    if casual_response(query):
        return "chat"
    if re.search(r"\b(poem|poetry|shakespeare|hamlet|yo mama|warp|teleport|flight mode|sorting function|write (?:a |some )?(?:code|python)|politics|recipe)\b", query, re.I):
        return "out_of_scope"
    if query_language_detector().is_confident_malay(query):
        return "out_of_scope"
    if re.search(r"\b(legal|legally|law|laws|regulation|regulatory|licensing|compliance)\b", resolved, re.I):
        return "rag_with_external_warning"
    return "rag"


def prepare_retrieval(query):
    from rag.app.embedding.embedder import embed_query
    return embed_query(query)


def retrieve_manual(query_embedding, top_k, *, scope,
                    query=None, diagnostics=None):
    from rag.app.embedding.vector_store import VectorStore
    from rag.app.retrieval.hybrid import search
    ids = scope["document_ids"]
    if not ids:
        return []
    store = VectorStore(create=False)
    if not store.collection.count():
        from rag.app.embedding.vector_store import IndexConfigurationError
        raise IndexConfigurationError("The prepared manual collection is empty")
    # Independent budgets keep source descriptions from displacing passages.
    results = search(store, query or "", query_embedding, ids, top_k=top_k,
                     diagnostics=diagnostics, content_type='paragraph')
    for kind, limit in (('table', 2), ('image', 3)):
        results += search(store, query or '', query_embedding, ids, top_k=limit, content_type=kind)
    if scope:
        results = [replace(r, metadata={**r.metadata, **scope["document_metadata"].get(r.metadata["document_name"], {})})
                   for r in results]
    if diagnostics is not None:
        diagnostics.update(status="ok", collection=store.collection.name,
                           metric=(store.collection.configuration.get("hnsw") or {}).get("space", "l2"),
                           threshold=None, indexed_chunks=store.collection.count(),
                           chunks=[{"id": r.chunk_id, "rank": r.rank, "distance": r.distance,
                                    "text": r.text, "metadata": r.metadata} for r in results])
    return results




async def handle_query(query, *, scope, history=None, vehicle_profile=None, top_k=settings.RAG_TOP_K):
    if not query.strip() or top_k < 1:
        raise ValueError("Provide a nonempty query and positive top_k")
    if not scope.get("scope_id") or scope.get("scope_type") not in {"vehicle", "category"}:
        raise ValueError("Invalid knowledge scope")
    if (vehicle_profile and scope['scope_type'] == 'vehicle'
            and str(vehicle_profile['catalogue_id']) != str(scope['scope_id'])):
        raise ValueError('The personal vehicle profile does not match the knowledge scope')
    history = recent_context(history)
    start = perf_counter()
    timings, routing, manual, youtube, generation = {}, {}, {}, {}, {}
    route = await classify_query(query, history, diagnostics=routing)
    timings["routing"] = round((perf_counter() - start) * 1000, 1)
    question = build_retrieval_query(query, history, expand=False)
    videos, records, eligible = [], [], []
    useful = False
    attachments = []
    response_type = route
    if route == "chat":
        answer = casual_response(query)
    elif route == "out_of_scope":
        answer = "I support English-language car-maintenance questions within your selected knowledge scope."
    elif route == "emergency":
        answer = emergency_guidance(question)
        eligible = retrieve_emergency(question, scope.get('content_sources', []))
        if eligible:
            answer += '\n\n' + render_emergency(eligible)
            useful = True
            generation.update(manual_relevant=False, content_relevant=True)
            response_type = 'emergency_protocol'
    elif route == "restricted":
        answer = RESTRICTED_ANSWER
    elif not (scope["document_ids"] or scope.get('content_sources') or vehicle_profile):
        answer, response_type = NO_MANUAL, "insufficient_information"
    else:
        retrieval_query = build_retrieval_query(query, history)
        routing["retrieval_query"] = retrieval_query
        started = perf_counter()
        embedding = None
        embedding_error = None
        if scope['document_ids'] or scope.get('video_ids'):
            try:
                embedding = await asyncio.to_thread(prepare_retrieval, retrieval_query)
            except Exception as error:
                # Published content uses lexical retrieval and can still answer
                # when the optional manual/video embedding service is unavailable.
                embedding_error = error
                logger.warning('Query embedding failed (%s)', type(error).__name__)
        timings["embedding"] = round((perf_counter() - started) * 1000, 1)

        def timed(name, function, *args, **kwargs):
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                timings[name] = round((perf_counter() - started) * 1000, 1)

        def search_manuals():
            if not scope['document_ids']:
                return []
            if embedding_error is not None:
                raise embedding_error
            return retrieve_manual(embedding, max(top_k, settings.RAG_CANDIDATES),
                                   scope=scope, query=retrieval_query, diagnostics=manual)

        def search_videos():
            if not scope.get('video_ids'):
                return []
            if embedding_error is not None:
                raise embedding_error
            return retrieve_youtube(retrieval_query, top_k, query_embedding=embedding,
                                    video_ids=scope['video_ids'], diagnostics=youtube)

        records, candidates = await asyncio.gather(
            asyncio.to_thread(timed, "manual_retrieval", search_manuals),
            asyncio.to_thread(timed, "youtube_retrieval", search_videos),
            return_exceptions=True)
        manual_failed, video_failed = isinstance(records, Exception), isinstance(candidates, Exception)
        if manual_failed:
            manual.update(status="error", error_type=type(records).__name__)
            records = []
        if video_failed:
            youtube.update(status="error", error_type=type(candidates).__name__)
            candidates = []
        eligible, excluded = applicable(question, records, scope)
        media = [r for r in eligible if r.metadata.get('content_type') in {'table', 'image'}]
        eligible = [r for r in eligible if r.metadata.get('content_type') == 'paragraph'][:top_k]
        attachments = resolve_attachments(media, eligible, question=question)
        eligible += retrieve_content(retrieval_query, scope.get('content_sources', []), top_k)
        generation.update(excluded_sources=excluded, generation_llm_calls=0, evidence_llm_calls=0)
        from rag.app.youtube.selection import select_videos
        vehicle_code = (scope.get("vehicle") or {}).get("code")
        videos = await select_videos(question, candidates, vehicle_code, None, youtube)
        started = perf_counter()
        answer = NO_MANUAL + (" " + CLARIFY if excluded else "")
        if eligible or vehicle_profile:
            generator = GenerationClient()
            try:
                answer, useful = await asyncio.to_thread(generate, question, eligible, generator,
                                                         scope=scope, risk=routing["risk"],
                                                         vehicle_profile=vehicle_profile, diagnostics=generation)
            except Exception as error:
                answer = MODEL_UNAVAILABLE
                generation.update(error_type=type(error).__name__, decision_reason="generation_error")
            if isinstance(generator, GenerationClient):
                generation.update(provider=generator.provider, model=generator.model,
                                  fallback_reason=generator.fallback_reason)
                if generator.provider == "ollama" and generator.fallback_reason:
                    answer += "\n\n" + FALLBACK_NOTICE
        timings["generation"] = round((perf_counter() - started) * 1000, 1)
        if manual_failed:
            attachments = []
            answer = answer + '\n\n' + MANUAL_UNAVAILABLE if useful else MANUAL_UNAVAILABLE
        elif attachments:
            if not useful:
                answer = 'Relevant source material is shown below. Check the original source, vehicle configuration, units, legends and notes before using table values or symbols.'
            if any(a['kind'] == 'table' for a in attachments):
                answer += '\n\nThe attached tables preserve extracted source content. Extraction fidelity and nearby note associations may require verification against the original manual.'
        if videos:
            answer += "\n\nSupplementary educational videos; these do not establish specifications or repair safety:\n"
            for video in videos:
                m = video["metadata"]
                answer += f"\n- {m.get('video_title', m['video_id'])}: {timestamp_url(m['video_id'], m.get('start_seconds'))}"
        if video_failed:
            answer += "\n\nVideo recommendations are temporarily unavailable."
        if route == "rag_with_external_warning":
            answer += "\n\n" + EXTERNAL_WARNING
        response_type = ('source_attachments' if attachments and not useful else ("manual_and_video" if videos else "manual_only") if useful else ("video_only" if videos else "insufficient_information"))
        if useful and generation.get('profile_relevant'):
            response_type = 'profile_and_manual' if generation.get('manual_relevant') else 'profile_only'
        if useful and generation.get('content_relevant'):
            response_type = 'mixed_sources' if generation.get('manual_relevant') or generation.get('profile_relevant') else 'published_content'
        if generation.get("decision_reason") == "generation_error":
            response_type = "generation_error"
        elif manual_failed and not videos and not useful:
            response_type = "retrieval_error"
    manual_relevant = generation.get('manual_relevant', useful)
    generation["manual_relevant"] = manual_relevant
    public_videos = [{"title": v["metadata"].get("video_title", v["metadata"]["video_id"]),
                      "url": timestamp_url(v["metadata"]["video_id"], v["metadata"].get("start_seconds")),
                      "timestamp": v["metadata"].get("start_seconds")} for v in videos]
    result = {"route": route, "answer": answer, "videos": public_videos, 'attachments': attachments,
              "external_warning": route == "rag_with_external_warning", "manual_relevant": manual_relevant,
              "response_type": response_type,
              "sources": [(public_source(r, f'S{i}') if r.metadata.get('source_type') in {'learning_guide', 'emergency_protocol'}
                           else {"label": f"S{i}", "source_type": "manual", "chunk_id": r.chunk_id,
                                 "document_id": r.metadata.get("document_id", r.metadata.get("document_name"))})
                          for i, r in enumerate(eligible, 1) if f"[S{i}]" in answer] if useful else []}
    timings["total"] = round((perf_counter() - start) * 1000, 1)
    logger.info("rag_query scope=%s type=%s provider=%s model=%s total_ms=%s",
                scope["scope_id"], response_type, generation.get("provider"), generation.get("model"), timings["total"])
    return result


def resolve_attachments(media, passages, *, question=None):
    """Resolve only backend-indexed IDs. Never ask the generator for assets."""
    selected = {}
    for record in media:
        selected[(record.metadata['document_name'], record.metadata['element_id'])] = record
    # A relevant passage can discover otherwise unlabelled nearby diagrams.
    for record in passages:
        ids = record.metadata.get('source_element_ids') or []
        if isinstance(ids, str):
            ids = json.loads(ids)
        for identity in ids:
            selected.setdefault((record.metadata['document_name'], identity), record)
    attachments = []
    counts = {'table': 0, 'image': 0}
    for (name, identity), record in selected.items():
        path = settings.OUTPUT_DIR / 'sources' / f'{name}.json'
        if path.parent.resolve() != (settings.OUTPUT_DIR / 'sources').resolve():
            raise ValueError('Invalid source manifest name')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if manifest.get('format_version') != 2:
            raise ValueError('Incompatible source manifest')
        element = next((e for e in manifest['elements'] if e['element_id'] == identity), None)
        if element is None:
            raise ValueError('Indexed source element is missing')
        kind = element['kind']
        direct = record.metadata.get('element_id') == identity
        if not direct and kind == 'table':
            from rag.app.generation.grounded import topic_matches, media_topic
            if not question or not topic_matches(media_topic(question), element['description'], strict=True):
                continue  # A source neighbour must also match the requested topic.
        if counts[kind] >= (2 if kind == 'table' else 3):
            continue
        counts[kind] += 1
        attachments.append({'kind': kind, 'element_id': identity,
                            'document_id': record.metadata.get('document_id', name),
                            'source_revision': record.metadata.get('index_revision'),
                            'source_fidelity_verified': record.metadata.get('source_fidelity_verified', False)})
    return attachments
