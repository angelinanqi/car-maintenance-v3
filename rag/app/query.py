"""Interpret the conversation, retrieve scoped evidence, generate a cited answer."""
from shared.observability import observed
from shared.answer_sections import validated_sections
import asyncio
from dataclasses import replace
import json
import logging
import re
from time import perf_counter

from rag.config import settings
from shared.visual_identity import image_identified, source_image_available, image_identity
from shared.table_evidence import table_reference_text
from shared.source_pages import element_page, element_region, page_assets, table_page_parts
from shared.source_elements import element_parts
from rag.app.generation.provider import GenerationClient
from rag.app.generation.intent import Intent, interpret
from rag.app.generation.context import bounded_history
from shared.chat_preferences import requested_video, videos_excluded, followup_topic
from rag.app.generation.grounded import applicable, generate, GeneratedReply, INSUFFICIENT, CLARIFY
from shared.safety import immediate_emergency, policy_risk, videos_allowed, emergency_guidance, RESTRICTED_ANSWER
from rag.app.youtube.retrieval import retrieve_youtube, timestamp_url
from rag.app.youtube.selection import select_videos, recommendation_candidates
from rag.app.retrieval.content import retrieve_content, retrieve_emergency, render_emergency, public_source

MODEL_UNAVAILABLE = "I couldn't complete the answer right now. Please try again shortly."
MANUAL_UNAVAILABLE = "The manual search is temporarily unavailable. Please try again shortly."
EXTERNAL_WARNING = "Verify current legal requirements with the relevant official transport authority."
REFERENCE_CANDIDATE_LIMIT = 8
logger = logging.getLogger(__name__)


def ambiguous_fluid_fill(question, history):
    """An unspecified prospective 'water' fill cannot identify a reservoir."""
    named = r'\b(?:coolant|radiator|windscreen|windshield|washer|wiper|brake|clutch|transmission|battery|oil|fuel|petrol|diesel)\b'
    if (not re.search(r'\b(?:water|fluid)\b', question, re.I)
            or re.search(named, question, re.I)
            or re.search(r'\b(?:already|poured|added|filled)\b|\b(?:have|just|I) put\b', question, re.I)):
        return False
    # Preserve a genuine follow-up to an explicitly named fluid in user history.
    previous = next((m['content'] for m in reversed(history or []) if m.get('role') == 'user'), '')
    if re.search(named, previous, re.I):
        return False
    return bool(re.search(r'\b(?:which|where|scared|afraid|worried|might|should|want|check)\b', question, re.I)
                and re.search(r'\b(?:pour|put|fill|add|check|tank|reservoir)\b|\btop[ -]?up\b', question, re.I))


@observed('query_preparation')
def prepare_retrieval(query):
    from rag.app.embedding.embedder import embed_query
    return embed_query(query)


def retrieve_manual(query_embedding, top_k, *, scope, query):
    if not scope["document_ids"]:
        return []
    from rag.app.embedding.vector_store import VectorStore
    from rag.app.retrieval.hybrid import search
    store = VectorStore(create=False)
    if not store.collection.count():
        raise ValueError("The prepared manual collection is empty")
    # A scoped lexical search still works if the embedding service is unavailable.
    # Keep broad candidates here; joint prose/guide reranking happens after
    # applicability checks, independently of visual selection.
    candidate_limit = max(top_k, settings.RAG_CANDIDATES) * 3
    results = search(store, query, query_embedding, scope["document_ids"], top_k=candidate_limit,
                     mode="lexical" if query_embedding is None else None, use_reranker=False)
    return [replace(r, metadata={**r.metadata, **scope["document_metadata"].get(r.metadata["document_name"], {})})
            for r in results]


@observed('chat_query', failure_field='response_type', failure_values=('generation_error', 'retrieval_error'))
async def handle_query(query, *, scope, history=None, vehicle_profile=None,
                       maintenance_context=None, activity_context=None, assistance=None, top_k=settings.RAG_TOP_K,
                       admin_trace=None):
    if not query.strip() or top_k < 1:
        raise ValueError("Provide a nonempty query and positive top_k")
    if not scope.get("scope_id") or scope.get("scope_type") not in {"auto", "vehicle", "category"}:
        raise ValueError("Invalid knowledge scope")
    if vehicle_profile and scope["scope_type"] == "vehicle" and str(vehicle_profile["catalogue_id"]) != str(scope["scope_id"]):
        raise ValueError("The personal vehicle profile does not match the knowledge scope")
    if scope['scope_type'] == 'auto':
        selected = scope.get('vehicle')
        if ((selected is None) != (vehicle_profile is None)
                or (selected and str(selected['id']) != str(vehicle_profile['catalogue_id']))):
            raise ValueError('Automatic context does not match the active personal vehicle')
    if maintenance_context and (not vehicle_profile or maintenance_context["vehicle_id"] != vehicle_profile["vehicle_id"]
                               or str(maintenance_context["catalogue_id"]) != str(vehicle_profile["catalogue_id"])):
        raise ValueError("Maintenance context does not match the active personal vehicle")
    start = perf_counter()
    timings, diagnostics = {}, {}
    history = bounded_history(history)
    client = GenerationClient()
    records, eligible, videos, attachments, excluded = [], [], [], [], []
    reference_candidates = []
    answer_sections = []
    recommended_guides = []
    useful = False
    cited_labels = []
    relevance = {}
    answer, response_type, route = MODEL_UNAVAILABLE, "generation_error", "rag"
    intent = None

    def append_note(message):
        nonlocal answer
        answer += '\n\n' + message
        if answer_sections:
            answer_sections.append({'text': message, 'reference_labels': []})
    phase = perf_counter()
    try:
        # Immediate explicit hazards don't wait for a model round trip.
        if immediate_emergency(query):
            intent = Intent(question=query, route="emergency",
                            risk="emergency", specification=False, vehicle_conflict=False,
                            requested_year=None, requested_engine=None, requested_variant=None)
        elif ambiguous_fluid_fill(query, history):
            intent = Intent(question=query, route='rag', risk='normal', specification=False,
                vehicle_conflict=False, requested_year=None, requested_engine=None, requested_variant=None,
                clarification='Do you mean windscreen washer fluid, engine coolant, or another fluid?')
        else:
            intent = await asyncio.to_thread(interpret, query, history, scope, client)
    except Exception as error:
        diagnostics["interpretation_fallback"] = type(error).__name__
        logger.warning("RAG interpretation failed (%s)", type(error).__name__)
        topic = followup_topic(query, history)
        resolved = topic + '\nFollow-up: ' + query if topic else query
        intent = Intent(question=resolved, search_query=topic or query, route="rag", risk="normal",
                        specification=False, vehicle_conflict=False, requested_year=None,
                        requested_engine=None, requested_variant=None)
    timings["interpretation_ms"] = round((perf_counter() - phase) * 1000, 1)
    if intent:
        # Semantic route/risk labels are advice, not permission to search.
        # Keep the existing concrete-action safety backstop and scoped sources.
        action_risk = policy_risk(intent.question)
        route = ("emergency" if immediate_emergency(query) or action_risk == "emergency"
                 else "restricted" if action_risk == "high_risk"
                 else "rag_with_external_warning" if intent.route == "rag_with_external_warning"
                 else "rag")
        diagnostics["interpreted_route"] = intent.route
        if route == "emergency":
            answer = emergency_guidance(intent.question)
            eligible = retrieve_emergency(intent.question, scope.get("content_sources", []))
            if eligible:
                answer += "\n\n" + render_emergency(eligible)
                useful = True
            response_type = "emergency_protocol" if eligible else "emergency"
        elif route == "restricted":
            answer, response_type = RESTRICTED_ANSWER, "restricted"
        elif intent.route in {'chat', 'out_of_scope'}:
            route = response_type = intent.route
            answer = ("I'm here to help with your vehicle. What would you like to know?" if route == 'chat'
                      else 'I can help with car questions, maintenance and roadside guidance.')
        elif intent.vehicle_conflict:
            vehicle = scope.get('vehicle') or {}
            identity = vehicle.get('name') or scope.get('label', 'your saved vehicle')
            if vehicle.get('year'):
                identity += ' (' + str(vehicle['year']) + ')'
            answer = f'Your selected vehicle is {identity}. Are you asking about this car or a different vehicle?'
            response_type = 'clarification'
        elif intent.clarification:
            answer, response_type = intent.clarification, 'clarification'
        else:
            phase = perf_counter()
            retrieval_query = intent.search_query or intent.question
            embedding = None
            video_ids = scope.get("video_ids", [])
            # None means all prepared videos; an empty list keeps document previews isolated.
            search_all_videos = video_ids is None
            if scope["document_ids"] or search_all_videos or video_ids or scope.get("content_sources"):
                try:
                    embedding = await asyncio.to_thread(prepare_retrieval, retrieval_query)
                except Exception as error:
                    logger.warning("Query embedding unavailable; using scoped lexical retrieval (%s)", type(error).__name__)
            timings["embedding_ms"] = round((perf_counter() - phase) * 1000, 1)
            phase = perf_counter()
            video_diagnostics = {}

            def search_manuals():
                found = retrieve_manual(embedding, top_k, scope=scope, query=retrieval_query)
                parts = [part.strip() for part in re.findall(r'[^?]+\?', query)]
                if len(parts) > 1:
                    from rag.app.retrieval.hybrid import fuse
                    for part in parts[:3]:
                        try:
                            part_embedding = prepare_retrieval(part) if embedding is not None else None
                            additional = retrieve_manual(part_embedding, top_k, scope=scope, query=part)
                        except Exception as error:
                            logger.warning('Subquestion retrieval unavailable (%s)', type(error).__name__)
                            continue
                        found = fuse(found, additional)
                return found

            def search_content():
                sources = scope.get('content_sources', [])
                found = retrieve_content(retrieval_query, sources, max(top_k, settings.RAG_CANDIDATES),
                                         query_embedding=embedding)
                if activity_context and activity_context.get('kind') == 'guide':
                    # Keep the selected published guide available without blocking topic changes.
                    from rag.app.retrieval.content import records_for
                    selected = [source for source in sources if source['source_type'] == 'learning_guide'
                                and source['source_id'] == activity_context.get('source_id')]
                    existing = {record.chunk_id for record in found}
                    found.extend(record for record in records_for(selected, include_media=False) if record.chunk_id not in existing)
                return found

            def search_videos():
                # Practical answers can proactively offer a strong match.
                # Exclusions are shared with generation and availability messaging.
                if (videos_excluded(query) or video_ids == [] or embedding is None
                        or not videos_allowed(intent)):
                    return []
                # Manual queries can add the selected model. Keep the resolved
                # user's request for discovery, so an explicitly general
                # tutorial isn't buried beneath unrelated model-specific clips.
                video_query = retrieval_query
                video_embedding = embedding
                # Transcript chunks can repeat one video. Overfetch before
                # deduplicating so metadata-only videos also get considered.
                return retrieve_youtube(video_query, max(40, top_k * 8), query_embedding=video_embedding,
                                        video_ids=video_ids, guide_video_ids=scope.get('guide_video_ids', []),
                                        diagnostics=video_diagnostics)

            records, published, candidates = await asyncio.gather(
                asyncio.to_thread(search_manuals), asyncio.to_thread(search_content),
                asyncio.to_thread(search_videos), return_exceptions=True)
            manual_failed, content_failed, video_failed = [isinstance(value, Exception) for value in (records, published, candidates)]
            if video_failed:
                diagnostics['video_retrieval_error'] = type(candidates).__name__
                logger.warning('Video retrieval unavailable (%s)', type(candidates).__name__)
            records = [] if manual_failed else records
            manual_failed = manual_failed or bool(scope.get('unavailable_documents'))
            published = [] if content_failed else published
            candidates = [] if video_failed else candidates
            eligible, excluded = applicable(intent.question, records, scope, intent=intent)
            # Give text and visual descriptions separate budgets within one ranked search.
            paragraphs = [r for r in eligible if r.metadata.get("content_type") == "paragraph"]
            media_candidates = [r for r in eligible if r.metadata.get("content_type") in {"image", "table"}]
            from rag.app.retrieval.prose import select_prose
            # The resolved question supplies follow-up context; preserve explicit
            # user question boundaries when there are multiple requested parts.
            ranking_question = query if query.count('?') > 1 else intent.question
            eligible = await asyncio.to_thread(select_prose, ranking_question, paragraphs + published,
                                               top_k, diagnostics=diagnostics)
            ranked_media = await asyncio.to_thread(rank_visuals, retrieval_query, media_candidates,
                                                  diagnostics=diagnostics)
            reference_candidates = prepare_references(eligible + ranked_media, diagnostics=diagnostics)
            selected_elements = {(item['descriptor']['document_id'], item['descriptor']['element_id'])
                                 for item in reference_candidates}
            # Resolve validity/deduplication before applying the sole reference budget.
            # Keep retrieved table fragments together with their original reference.
            for record in media_candidates:
                key = (record.metadata.get('document_id', record.metadata['document_name']),
                       record.metadata.get('element_id'))
                if key not in selected_elements or record.metadata.get('content_type') != 'table':
                    continue
                eligible.append(record)
            eligible.sort(key=lambda record: record.rank)
            diagnostics["visual_candidates"] = [
                {"chunk_id": r.chunk_id, "element_id": r.metadata.get("element_id"),
                 "rank": r.rank, "selected":
                 (r.metadata.get('document_id', r.metadata['document_name']),
                  r.metadata.get('element_id')) in selected_elements}
                for r in media_candidates]
            videos = await select_videos(intent.question, candidates, scope.get("vehicle"),
                                         video_diagnostics.get("metric") or "l2", intent=intent,
                                         known_vehicle_codes=scope.get('vehicle_codes', []),
                                         proactive=not (requested_video(query) or requested_video(intent.question)))
            video_candidates = recommendation_candidates(videos)
            for video, candidate in zip(videos, video_candidates):
                video['metadata'] = {**video['metadata'], 'channel_title': candidate['channel_title']}
            diagnostics['video_candidates'] = video_candidates
            diagnostics.update(retrieved=len(records), eligible=len(eligible), excluded=len(excluded),
                               source_exclusions=excluded,
                               unavailable_manual_count=len(scope.get('unavailable_documents', [])))
            timings["retrieval_ms"] = round((perf_counter() - phase) * 1000, 1)
            answer, response_type = INSUFFICIENT + (" " + CLARIFY if excluded and not eligible else ""), "insufficient_information"
            # The same generation call can explain general concepts without a
            # manual. It must explicitly distinguish background from evidence.
            phase = perf_counter()
            try:
                image_candidates = [visual for item in reference_candidates for visual in item.get('visual_inputs', [])]
                visual_options = {}
                if image_candidates:
                    visual_options = {
                        'images': [item['image_input'] for item in image_candidates],
                        'image_sources': [item['image_source'] for item in image_candidates],
                    }
                exact_reference = explicit_reference(query, reference_candidates)
                if exact_reference:
                    generated = GeneratedReply('The requested original reference is shown below.',
                        'reference_only', reference_labels=[exact_reference])
                else:
                    personal_context = intent.personal_context
                    if intent.suggest_service_plan or (activity_context and activity_context.get('kind') == 'plan'):
                        personal_context = 'maintenance'
                    generated = await asyncio.to_thread(
                        generate, intent.question, eligible, client, scope=scope, risk=intent.risk,
                        vehicle_profile=vehicle_profile if personal_context != 'none' else None,
                        maintenance_context=maintenance_context if personal_context == 'maintenance' else None,
                        activity_context=activity_context, assistance=assistance,
                        diagnostics=diagnostics, intent=intent, history=history, latest_message=query,
                        supplementary_videos=video_candidates,
                        references=[{k: v for k, v in item.items() if k not in {'descriptor', 'visual_inputs'}}
                                    for item in reference_candidates], **visual_options)
                answer = generated.text
                answer_sections = generated.answer_sections
                cited_labels = generated.cited_labels
                useful = generated.status == "answered"
                videos = [video for index, video in enumerate(videos, 1)
                          if f'Y{index}' in generated.video_labels][:2]
                diagnostics['selected_videos'] = generated.video_labels
                if useful:
                    recommended_guides = [public_source(record, f'S{index}')
                        for index, record in enumerate(eligible, 1) if f'S{index}' in generated.guide_labels]
                response_type = "manual_only" if useful else generated.status
                if not generated.allow_videos or generated.status == 'reference_only':
                    videos = []
                if generated.status in {'restricted', 'emergency', 'chat', 'out_of_scope'}:
                    route = generated.status
                    videos = []
                attachments = [item["descriptor"] for item in reference_candidates
                               if item["label"] in generated.reference_labels]
                cited = [r for i, r in enumerate(eligible, 1) if f"S{i}" in cited_labels]
                relevance = dict(
                    manual_relevant=any(r.metadata.get("source_type", "manual") == "manual" for r in cited)
                        or any(item['image_input'].label in cited_labels for item in image_candidates),
                    content_relevant=any(r.metadata.get("source_type", "manual") != "manual" for r in cited),
                    profile_relevant="P1" in cited_labels, maintenance_relevant="P2" in cited_labels)
                diagnostics.update(relevance, selected_references=generated.reference_labels)
            except Exception as error:
                logger.warning("RAG generation failed (%s)", type(error).__name__)
                videos = []
                answer_sections = []
                answer, response_type = MODEL_UNAVAILABLE, "generation_error"
                diagnostics["decision_reason"] = "generation_error"
            timings["generation_ms"] = round((perf_counter() - phase) * 1000, 1)
            if useful:
                if generated.has_general_information:
                    response_type = 'mixed_sources' if cited_labels else 'general_information'
                elif relevance.get("maintenance_relevant"):
                    response_type = "mixed_sources" if relevance.get("manual_relevant") else "maintenance_only"
                elif relevance.get("content_relevant"):
                    response_type = "mixed_sources" if relevance.get("manual_relevant") else "published_content"
                elif relevance.get("profile_relevant"):
                    response_type = "profile_and_manual" if relevance.get("manual_relevant") else "profile_only"
            if manual_failed or content_failed:
                append_note(MANUAL_UNAVAILABLE)
                if not useful and not attachments:
                    response_type = "retrieval_error"
            if video_failed:
                append_note("Video recommendations are temporarily unavailable.")
            elif (requested_video(query) and not videos and route in {'rag', 'rag_with_external_warning'}
                  and response_type not in {'generation_error', 'retrieval_error'}
                  and not re.search(r'\bvideo\b', answer, re.I)):
                append_note("I don't have a matching video available for this request.")
            if videos and useful and response_type == "manual_only":
                response_type = "manual_and_video"
            if videos and not useful and response_type == "insufficient_information":
                response_type = "video_only"
            if route == "rag_with_external_warning":
                append_note(EXTERNAL_WARNING)
    public_videos = [{"title": v["metadata"].get("video_title", v["metadata"]["video_id"]),
                      "channel_title": v['metadata'].get('channel_title', ''),
                      "channel_id": v['metadata'].get('channel_id', ''),
                      "url": timestamp_url(v["metadata"]["video_id"],
                          v["metadata"].get("start_seconds") if v["metadata"].get("retrieval_content") == 'transcript'
                          and v.get('retrieval_method') != 'title_keywords' else None),
                      "timestamp": v["metadata"].get("start_seconds") if v["metadata"].get("retrieval_content") == 'transcript'
                          and v.get('retrieval_method') != 'title_keywords' else None,
                      "matched_using": ('title' if v.get('retrieval_method') == 'title_keywords'
                                        else 'title_and_transcript' if v['metadata'].get('retrieval_content') == 'transcript'
                                        else 'title_and_description'),
                      "content_verified": False,
                      "vehicle_match": v.get('vehicle_match', 'generic'),
                      "notice": ("Generic demonstration. " if v.get('vehicle_match') == 'generic' else "External video. ")
                                + "Content and vehicle compatibility have not been verified."}
                     for v in videos]
    sources = []
    if useful:
        for index, record in enumerate(eligible, 1):
            label = f"S{index}"
            if label not in cited_labels and route != "emergency":
                continue
            if record.metadata.get("source_type") in {"learning_guide", "emergency_protocol"}:
                sources.append(public_source(record, label))
            else:
                section_path = record.metadata.get("section_path") or []
                if isinstance(section_path, str):
                    section_path = json.loads(section_path)
                sources.append({"label": label, "source_type": "manual", "chunk_id": record.chunk_id,
                                "document_id": record.metadata.get("document_id", record.metadata.get("document_name")),
                                "source_revision": record.metadata.get("index_revision"),
                                "section_path": section_path})
        if relevance.get("profile_relevant"):
            sources.append({"label": "P1", "source_type": "personal_vehicle_profile", "title": "Saved vehicle profile",
                            "vehicle_id": vehicle_profile["vehicle_id"]})
        if relevance.get("maintenance_relevant"):
            sources.append({"label": "P2", "source_type": "personal_maintenance", "title": "Saved maintenance records",
                            "vehicle_id": vehicle_profile["vehicle_id"], "as_of": maintenance_context["as_of"]})
        for reference in reference_candidates:
            for visual in reference.get('visual_inputs', []):
                if visual['image_input'].label not in cited_labels:
                    continue
                descriptor = reference['descriptor']
                source = {'label': visual['image_input'].label, 'source_type': 'manual',
                    'document_id': descriptor['document_id'], 'source_revision': descriptor['source_revision']}
                if visual['image_source'].get('source_extent') != 'page':
                    source['element_id'] = descriptor['element_id']
                sources.append(source)
    timings["total_ms"] = round((perf_counter() - start) * 1000, 1)
    if admin_trace is not None:
        from rag.app.document_testing import collect_trace
        admin_trace.update(collect_trace(records, eligible, excluded, sources, diagnostics, client, timings["total_ms"]))
    logger.info("rag_query %s", json.dumps({"scope_id": scope["scope_id"], "response_type": response_type,
                "provider": client.provider, "model": client.model, **timings, **diagnostics}))
    return {"route": route, "answer": answer, "videos": public_videos, "attachments": attachments,
            "answer_sections": validated_sections(answer, answer_sections, attachments),
            "recommended_guides": recommended_guides,
            "suggested_activity": 'service_plan' if intent and intent.suggest_service_plan and vehicle_profile
                and route in {'rag', 'rag_with_external_warning'} and response_type not in {'restricted', 'emergency'} else None,
            "external_warning": route == "rag_with_external_warning",
            "manual_relevant": relevance.get("manual_relevant", False), "response_type": response_type, "sources": sources}


def rank_visuals(search_query, records, *, diagnostics=None):
    """Order retrieved visual records before budgets, without rejecting evidence."""
    if not settings.RAG_RERANK or len(records) < 2:
        return records
    from rag.app.retrieval.hybrid import rerank
    started = perf_counter()
    try:
        # Generated crop descriptions can omit the component name (e.g. an
        # engine-oil gauge becomes just "Oil Level Gauge"). Restore the indexed
        # section as a search aid, never as factual evidence about the image.
        search_records = []
        for record in records:
            path = record.metadata.get('section_path') or []
            if isinstance(path, str):
                path = json.loads(path)
            text = record.text
            if 'Generated identification (unverified):' in text:
                text = 'Section: ' + ' > '.join(path)[:240] + '\n' + text
            search_records.append(replace(record, text=text))
        originals = {record.chunk_id: record for record in records}
        ranked = [replace(originals[record.chunk_id], rank=record.rank)
                  for record in rerank(search_query, search_records)]
    except Exception as error:
        logger.warning('Visual reranking unavailable; retaining hybrid order (%s)', type(error).__name__)
        if diagnostics is not None:
            diagnostics['visual_reranking'] = 'unavailable'
        return records
    if diagnostics is not None:
        diagnostics['visual_reranking'] = 'applied'
        diagnostics['visual_reranking_ms'] = round((perf_counter() - started) * 1000, 1)
        diagnostics['visual_rerank_order'] = [record.chunk_id for record in ranked]
    return ranked


def ordered_visual_parts(element, records, document_name):
    """Keep linked originals together; prioritize exact retrieved rows after headers."""
    parts = element_parts(element)
    if len(parts) < 2 or not all(part.get('structure_valid') for part in parts):
        return parts
    counts = [max((cell['row'] + cell['rowspan'] for cell in part.get('cells', [])), default=0)
              for part in parts]
    total = max((cell['row'] + cell['rowspan'] for cell in element.get('cells', [])), default=0)
    if not all(counts) or sum(counts) != total:
        return parts  # No established mapping from combined rows to parts.
    ranges = []
    for record in records:
        metadata = record.metadata
        if (metadata.get('document_name') == document_name and metadata.get('element_id') == element['element_id']
                and metadata.get('evidence_type') == 'table_cells_v1'):
            fragment = json.loads(metadata['source_content'])
            ranges.append(fragment['row_range'])
    preferred = [0]
    start = 0
    for index, count in enumerate(counts):
        if index and any(left < start + count and right >= start for left, right in ranges):
            preferred.append(index)
        start += count
    preferred.extend(index for index in range(len(parts)) if index not in preferred)
    return [parts[index] for index in preferred]


def prepare_references(records, *, diagnostics=None):
    """Build a bounded shortlist, independently of pixel and display limits."""
    manifests, selected, pages_by_document, frames, document_types = {}, {}, {}, {}, {}
    limited = {}
    unverified_images = {}
    direct, linked = [], []
    for record in records:
        metadata = record.metadata
        if metadata.get("source_type", "manual") not in {"manual", "learning_guide"}:
            continue
        if metadata.get('source_type') == 'learning_guide' and metadata.get('content_type') != 'table':
            continue  # Guide image descriptions return the original through content_media.
        if metadata.get("element_id"):
            direct.append((record, metadata["element_id"]))
        ids = metadata.get("source_element_ids") or []
        if isinstance(ids, str):
            ids = json.loads(ids)
        linked.extend((record, identity) for identity in ids)
    # Preserve relevance across kinds. Promoting every table above illustrations
    # displaced oil-check diagrams with unrelated schedules and warranty tables.
    # Selected tables still receive their independent original-page budget below.
    for record, identity in direct + linked:
        metadata = record.metadata
        name = metadata["document_name"]
        if (name, identity) in selected:
            continue
        if name not in manifests:
            path = settings.OUTPUT_DIR / "sources" / f"{name}.json"
            if path.parent.resolve() != (settings.OUTPUT_DIR / "sources").resolve():
                raise ValueError("Invalid source manifest name")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("format_version") != 2:
                raise ValueError("Incompatible source manifest")
            manifests[name] = {element["element_id"]: element for element in manifest["elements"]}
            document_types[name] = manifest.get('source_type')
            pages_by_document[name] = page_assets(manifest)
        element = manifests[name].get(identity)
        if element is None:
            raise ValueError("Indexed source element is missing")
        kind = element["kind"]
        if element.get('asset_available') is False and kind == 'image':
            continue
        # Source fidelity and image/topic association are different checks.
        # An inherited heading cannot establish what an illustration depicts.
        if kind == "image" and not source_image_available(element):
            unverified_images[(name, identity)] = True
            continue
        # Unverified nearby-prose links cannot establish relevance for an
        # unreviewed image. Its own directly retrieved identity can.
        if (kind == 'image' and not image_identified(element)
                and metadata.get('element_id') != identity):
            continue
        if (len(selected) >= REFERENCE_CANDIDATE_LIMIT
                or (kind == 'table' and sum(item['kind'] == 'table' for item in selected.values()) >= 5)):
            limited[(name, identity)] = kind
            continue
        label = f"V{len(selected) + 1}"
        review = image_identity(element)
        if kind == 'table':
            description = table_reference_text(element) or 'Table: ' + ' > '.join(element.get('section_path', []))
        elif review:
            description = '\n'.join([review['description'], review['uncertainty']]).strip()
        else:
            description = element.get('description', '')
        descriptor = {"kind": kind, "element_id": identity,
            "document_id": metadata.get("document_id", name), "source_revision": metadata.get("index_revision"),
            "source_fidelity_verified": metadata.get("source_fidelity_verified", False),
            "reference_label": label}
        selected[(name, identity)] = {"label": label, "kind": kind,
            "document_name": name, "element_id": identity,
            'source_label': (element.get('caption', '') if element.get('caption_origin') in
                             {'source_alt', 'source_caption', 'extractor_caption'} else ''),
            "title": review.get('title') or
                     " > ".join(element.get("section_path", [])) or element.get("caption", ""),
            # Literal table previews identify originals. Only structured source
            # fragments establish row/column relationships for factual answers.
            "description": description[:1600],
            "pages": element.get("pages", []), "descriptor": descriptor, 'visual_inputs': []}
        if kind == 'table':
            # Private parent evidence comes from the exact source manifest, never
            # caption similarity. Context packing removes it from reference JSON.
            selected[(name, identity)]['table_element'] = element
            selected[(name, identity)]['requires_page_images'] = document_types[name] == 'pdf'
    # Load table pages before illustration pixels. Each table keeps its related
    # section pages as context without claiming they are one logical table.
    table_frames, illustration_frames = set(), set()
    for (name, identity), reference in sorted(selected.items(), key=lambda item: item[1]['kind'] != 'table'):
        element = manifests[name][identity]
        kind = element['kind']
        metadata = next(record.metadata for record in records if record.metadata.get('document_name') == name)
        if metadata.get('source_type') == 'learning_guide':
            # Authored HTML tables have original cells; guide images are processed at ingestion.
            reference['visual_coverage'] = {'expected_pages': [], 'unmapped_parts': 0, 'page_inputs': []}
            continue
        own_parts = ordered_visual_parts(element, records, name)
        parts = [(part, 'table' if kind == 'table' else 'image') for part in own_parts]
        if kind == 'table':
            parts.extend((part, role) for part, role in table_page_parts(element, list(manifests[name].values()))
                         if role == 'section_context')
        reference['pixel_source_labels'] = []
        reference['visual_coverage'] = {
            'expected_pages': sorted({element_page(part) for part, _ in parts if element_page(part) is not None}),
            'unmapped_parts': sum(element_page(part) is None for part, _ in parts), 'page_inputs': []}
        for part, role in parts:
            number = element_page(part)
            coverage = {'page': number, 'role': role, 'source_label': None, 'extent': 'unavailable',
                        'omission_reason': 'original_unavailable', 'context_omitted': False}
            reference['visual_coverage']['page_inputs'].append(coverage)
            if not settings.RAG_VISUAL_INPUTS:
                coverage['omission_reason'] = 'visual_inputs_disabled'
                continue
            from rag.app.generation.visual import original_image
            page = pages_by_document[name].get(number)
            options = []
            if page:
                options.append(('page', page['asset_sha256']))
            if part.get('asset_sha256'):
                options.append(('crop', part['asset_sha256']))
            for extent, digest in options:
                key = (name, extent, number if extent == 'page' else None, digest)
                if key in frames:
                    visual = frames[key]
                    image_label = visual['image_input'].label
                    if kind == 'table':
                        visual['image_source']['contains_table'] = True
                    coverage.update(source_label=image_label, extent=extent, omission_reason=None)
                    if image_label not in reference['pixel_source_labels']:
                        reference['pixel_source_labels'].append(image_label)
                    if extent == 'page':
                        region = element_region(part)
                        if region is not None:
                            item = {'source_label': image_label, 'bbox_1000': region}
                            if len(parts) == 1:
                                reference['page_region'] = item
                            else:
                                reference.setdefault('page_regions', []).append(item)
                    break
                budget = table_frames if kind == 'table' else illustration_frames
                # Supply originals for the bounded illustration shortlist. A
                # separate three-page limit left useful lower-ranked diagrams
                # visible only as generated descriptions, which cannot establish
                # their appearance or component location.
                limit = settings.RAG_TABLE_PAGE_LIMIT if kind == 'table' else REFERENCE_CANDIDATE_LIMIT
                if len(budget) >= limit:
                    coverage['omission_reason'] = 'image_limit'
                    break
                try:
                    # Factual pixel-source labels must not also name attachments.
                    image_label = f'I{len(frames) + 1}'
                    image = original_image(settings.OUTPUT_DIR / 'assets' / name / digest, digest, image_label)
                except (OSError, ValueError):
                    logger.warning('Original %s unavailable for generation: %s/%s', extent, name, identity)
                    coverage['omission_reason'] = 'invalid_or_missing_original'
                    continue
                image_source = {
                    'label': image_label, 'title': (f'Original manual PDF page {number}' if extent == 'page'
                                             else reference['title']),
                    'source_type': 'manual', 'document_type': metadata.get('document_type', 'other_reference'),
                    'source_fidelity_verified': metadata.get('source_fidelity_verified', False),
                    'content_type': kind, 'pixels_supplied': True, 'source_extent': extent,
                    'contains_table': kind == 'table',
                    'requires_page_images': reference.get('requires_page_images', False),
                    'content': ('Original PDF page supplied; it can contain several references, headings and legends.'
                                if extent == 'page' else 'Original crop supplied. Its description alone is not evidence.'),
                }
                if kind == 'table':
                    image_source['continuation_coverage'] = 'See reference visual_coverage; extracted rows do not prove visual coverage.'
                if extent == 'page':
                    image_source['physical_page'] = number
                    region = element_region(part)
                    if region is not None:
                        item = {'source_label': image_label, 'bbox_1000': region}
                        if len(parts) == 1:
                            reference['page_region'] = item
                        else:
                            reference.setdefault('page_regions', []).append(item)
                visual = {'image_input': image, 'image_source': image_source}
                reference['visual_inputs'].append(visual)
                reference['pixel_source_labels'].append(image_label)
                coverage.update(source_label=image_label, extent=extent, omission_reason=None)
                frames[key] = visual
                budget.add(key)
                break
    # A few original table crops supplement full pages for dense symbols. Full
    # pages are loaded first so detail images cannot displace legends or notes.
    detail_count = 0
    for (name, identity), reference in selected.items():
        if reference['kind'] != 'table' or not settings.RAG_VISUAL_INPUTS:
            continue
        for part, _ in table_page_parts(manifests[name][identity], list(manifests[name].values())):
            number, digest = element_page(part), part.get('asset_sha256')
            coverage = next((page for page in reference['visual_coverage']['page_inputs']
                             if page['page'] == number and page['extent'] == 'page'), None)
            if not digest or not coverage or detail_count >= 3:
                continue
            key = (name, 'crop', None, digest)
            visual = frames.get(key)
            if visual is None:
                label = f'I{len(frames) + 1}'
                try:
                    image = original_image(settings.OUTPUT_DIR / 'assets' / name / digest, digest, label)
                except (OSError, ValueError):
                    continue  # Detail is optional; the full page remains available.
                parent = frames[(name, 'page', number, pages_by_document[name][number]['asset_sha256'])]
                visual = {'image_input': image, 'image_source': {
                    **parent['image_source'], 'label': label, 'source_extent': 'crop',
                    'title': f'Original table detail, PDF page {number}',
                    'content': 'Enlarged original table crop. Inspect its full-page source for headers and notes.'}}
                frames[key] = visual
                reference['visual_inputs'].append(visual)
                detail_count += 1
            if visual['image_input'].label not in reference['pixel_source_labels']:
                reference['pixel_source_labels'].append(visual['image_input'].label)
    if diagnostics is not None:
        diagnostics["unverified_image_omissions"] = [
            {"document_name": name, "element_id": identity}
            for name, identity in unverified_images]
        diagnostics["reference_limit_omissions"] = [
            {"document_name": name, "element_id": identity, "kind": kind}
            for (name, identity), kind in limited.items()]
    return list(selected.values())


def explicit_reference(question, references):
    """Resolve a pure request for an exact printed figure/table number."""
    requested = re.fullmatch(r'\s*(?:please\s+)?(?:show|display)\s+(?:me\s+)?(?:the\s+)?'
                             r'(figure|fig\.?|table)\s*(\d+(?:[.-]\d+)*[a-z]?)\s*[.!?]?\s*',
                             question, re.I)
    if not requested:
        return None
    kind = 'table' if requested[1].lower() == 'table' else 'image'
    prefix = 'table' if kind == 'table' else r'(?:figure|fig\.?)'
    pattern = re.compile(r'^\s*' + prefix + r'\s*' + re.escape(requested[2]) + r'(?![\w.-])', re.I)
    matches = [item['label'] for item in references if item.get('kind') == kind
               and pattern.search(item.get('source_label', ''))]
    return matches[0] if len(matches) == 1 else None
