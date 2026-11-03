"""Interpret the conversation, retrieve scoped evidence, generate a cited answer."""
from shared.observability import observed
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
from rag.app.generation.grounded import applicable, generate, GeneratedReply, INSUFFICIENT, CLARIFY
from shared.safety import immediate_emergency, policy_risk, videos_allowed, emergency_guidance, RESTRICTED_ANSWER
from rag.app.youtube.retrieval import retrieve_youtube, timestamp_url
from rag.app.youtube.selection import select_videos
from rag.app.retrieval.content import retrieve_content, retrieve_emergency, render_emergency, public_source

MODEL_UNAVAILABLE = "I couldn't complete the answer right now. Please try again shortly."
MANUAL_UNAVAILABLE = "The manual search is temporarily unavailable. Please try again shortly."
EXTERNAL_WARNING = "Verify current legal requirements with the relevant official transport authority."
REFERENCE_CANDIDATE_LIMIT = 8
logger = logging.getLogger(__name__)


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
    # Query-time reranking belongs to visual selection below; paragraph search
    # keeps its hybrid order even when that optional component is enabled.
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
    recommended_guides = []
    useful = False
    cited_labels = []
    relevance = {}
    answer, response_type, route = MODEL_UNAVAILABLE, "generation_error", "rag"
    intent = None
    phase = perf_counter()
    try:
        # Immediate explicit hazards don't wait for a model round trip.
        if immediate_emergency(query):
            intent = Intent(question=query, route="emergency",
                            risk="emergency", specification=False, vehicle_conflict=False,
                            requested_year=None, requested_engine=None, requested_variant=None)
        else:
            intent = await asyncio.to_thread(interpret, query, history, scope, client)
    except Exception as error:
        diagnostics["interpretation_fallback"] = type(error).__name__
        logger.warning("RAG interpretation failed (%s)", type(error).__name__)
        intent = Intent(question=query, search_query=query, route="rag", risk="normal",
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
        elif intent.vehicle_conflict:
            answer, response_type = CLARIFY, "insufficient_information"
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
                return retrieve_manual(embedding, top_k, scope=scope, query=retrieval_query)

            def search_content():
                sources = scope.get('content_sources', [])
                found = retrieve_content(retrieval_query, sources, top_k, query_embedding=embedding)
                if activity_context and activity_context.get('kind') == 'guide':
                    # Keep the selected published guide available without blocking topic changes.
                    from rag.app.retrieval.content import records_for
                    selected = [source for source in sources if source['source_type'] == 'learning_guide'
                                and source['source_id'] == activity_context.get('source_id')]
                    existing = {record.chunk_id for record in found}
                    found.extend(record for record in records_for(selected, include_media=False) if record.chunk_id not in existing)
                return found

            def search_videos():
                if video_ids == [] or embedding is None or not videos_allowed(intent):
                    return []
                return retrieve_youtube(retrieval_query, top_k, query_embedding=embedding,
                                        video_ids=video_ids, guide_video_ids=scope.get('guide_video_ids', []),
                                        diagnostics=video_diagnostics)

            records, published, candidates = await asyncio.gather(
                asyncio.to_thread(search_manuals), asyncio.to_thread(search_content),
                asyncio.to_thread(search_videos), return_exceptions=True)
            manual_failed, content_failed, video_failed = [isinstance(value, Exception) for value in (records, published, candidates)]
            records = [] if manual_failed else records
            manual_failed = manual_failed or bool(scope.get('unavailable_documents'))
            published = [] if content_failed else published
            candidates = [] if video_failed else candidates
            eligible, excluded = applicable(intent.question, records, scope, intent=intent)
            # Give text and visual descriptions separate budgets within one ranked search.
            paragraphs = [r for r in eligible if r.metadata.get("content_type") == "paragraph"][:top_k]
            media_candidates = [r for r in eligible if r.metadata.get("content_type") in {"image", "table"}]
            # Interleave by ordinal rank, without comparing unrelated score scales.
            eligible = sorted(paragraphs + published, key=lambda record: record.rank)
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
            videos = await select_videos(intent.question, candidates, (scope.get("vehicle") or {}).get("code"),
                                         video_diagnostics.get("metric") or "l2", intent=intent)
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
                        references=[{k: v for k, v in item.items() if k not in {'descriptor', 'visual_inputs'}}
                                    for item in reference_candidates], **visual_options)
                answer = generated.text
                cited_labels = generated.cited_labels
                useful = generated.status == "answered"
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
                answer += "\n\n" + MANUAL_UNAVAILABLE
                if not useful and not attachments:
                    response_type = "retrieval_error"
            if video_failed:
                answer += "\n\nVideo recommendations are temporarily unavailable."
            if videos and useful and response_type == "manual_only":
                response_type = "manual_and_video"
            if videos and not useful and response_type == "insufficient_information":
                response_type = "video_only"
            if route == "rag_with_external_warning":
                answer += "\n\n" + EXTERNAL_WARNING
    public_videos = [{"title": v["metadata"].get("video_title", v["metadata"]["video_id"]),
                      "url": timestamp_url(v["metadata"]["video_id"], v["metadata"].get("start_seconds")),
                      "timestamp": v["metadata"].get("start_seconds")} for v in videos]
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
        ranked = rerank(search_query, records)
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
    # Preserve retrieval order within each kind, reserving room for table
    # originals before unrelated illustrations can fill the shortlist.
    for record, identity in sorted(direct + linked, key=lambda item: not item[1].startswith('table-')):
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
                limit = settings.RAG_TABLE_PAGE_LIMIT if kind == 'table' else 3
                if len(budget) >= limit:
                    coverage['omission_reason'] = 'image_limit'
                    break
                try:
                    # Factual pixel-source labels must not also name attachments.
                    image_label = f'V{REFERENCE_CANDIDATE_LIMIT + len(frames) + 1}'
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
                label = f'V{REFERENCE_CANDIDATE_LIMIT + len(frames) + 1}'
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
