"""Scoped evidence, grounded generation and small deterministic integrity checks."""
from shared.observability import observed
import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from shared.table_evidence import table_literal_text

from rag.app.generation.context import bounded_history, content, prepare_context
from rag.config import settings
from rag.app.generation.answer_prompt import answer_instructions
from shared.safety import RESTRICTED_ANSWER, emergency_guidance, policy_risk, immediate_emergency
from shared.safety import SOURCE_INJECTION, educational_only

INSUFFICIENT = "I couldn't establish an answer from the supplied source material."
REFERENCE_ONLY = ("I couldn't establish a textual answer from the supplied source material. "
                  "The selected original reference material is shown below. Please read its details and notes directly.")
CLARIFY = "Please confirm the vehicle model, year, engine and variant for this question."
INJECTION = SOURCE_INJECTION
INLINE_CITATIONS = re.compile(r'\[([SPVI]\d+(?:\s*,\s*[SPVI]\d+)*)\]')
MODEL_CITATIONS = re.compile(INLINE_CITATIONS.pattern + r'|(?im:^sources:)')


def unrequested_battery_procedure(text, intent):
    """Do not turn a starting-symptom explanation into cable-handling steps."""
    if not intent or intent.instructional:
        return False
    for match in re.finditer(r'\b(disconnect(?:ed|ing)?|connect(?:ed|ing)?|remov(?:e|ed|ing))\b.{0,100}'
                             r'\b(battery|terminal|jumper|negative lead|negative cable)\b', text, re.I):
        prefix = text[max(0, match.start() - 20):match.start()]
        if not re.search(r'\b(?:not|never|avoid)\s+(?:ever\s+)?$', prefix, re.I):
            return True
    return False


def engine_bay_direction(text):
    """Use original component labels instead of unreliable generated side claims."""
    return bool(re.search(r'\b(?:engine (?:bay|compartment)|dipstick|oil (?:level gauge|filler|cap)|'
                          r'(?:washer|coolant|brake fluid) (?:cap|reservoir)|battery)\b', text, re.I)
                and re.search(r'\b(?:left|right)[- ](?:hand|side|corner)\b|'
                              r'\b(?:on|at|to|towards?|from)\s+(?:the\s+)?(?:far\s+)?(?:left|right)\b|'
                              r'\b(?:driver|passenger)(?:\x27s)?[- ]side\b|'
                              r'\b(?:upper|lower|middle)[- ](?:left|right|corner)\b', text, re.I))


@dataclass
class GeneratedReply:
    text: str
    status: str = "insufficient_information"
    cited_labels: list[str] = field(default_factory=list)
    reference_labels: list[str] = field(default_factory=list)
    allow_videos: bool = True
    has_general_information: bool = False
    guide_labels: list[str] = field(default_factory=list)
    video_labels: list[str] = field(default_factory=list)
    answer_sections: list[dict] = field(default_factory=list)


def year_matches(requested, declared):
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", declared)]
    if not years:
        return False
    if len(years) == 1:
        return requested >= years[0] if "current" in declared.lower() else requested == years[0]
    return min(years) <= requested <= max(years)


def table_data(record):
    data = record.metadata.get("table_data") or []
    return json.loads(data) if isinstance(data, str) else data


@observed('evidence_filtering')
def applicable(question, records, scope, *, intent=None):
    """Check source integrity and declared compatibility, never word overlap."""
    eligible, excluded = [], []
    selected = scope.get("vehicle") or {}
    if intent and (intent.vehicle_conflict or (selected and intent.requested_vehicle
                                             and intent.requested_vehicle != selected.get("code"))):
        return [], [{"reason": "Question conflicts with the selected vehicle"}]
    identities = set()
    for record in records:
        metadata = record.metadata
        vehicles = metadata.get("applicable_vehicles", [])
        if isinstance(vehicles, str):
            vehicles = json.loads(vehicles)
        if selected:
            vehicles = [v for v in vehicles if v["id"] == selected["id"]]
        elif intent and intent.requested_vehicle:
            vehicles = [v for v in vehicles if v.get("code") == intent.requested_vehicle]
        reason = None
        identity = None
        if metadata.get("source_quality") in {"corrupt", "incomplete", "unreliable"} or INJECTION.search(content(record)):
            reason = "Unreliable or injected source content"
        elif (metadata.get("content_type", "paragraph") == "paragraph"
              and any(not table.get("parse_valid") for table in table_data(record))):
            reason = "Malformed source table"
        elif (scope.get('scope_type') == 'auto' and not selected
              and not metadata.get('vehicle_independent')):
            reason = 'Select a vehicle before using vehicle-specific evidence'
        elif (scope.get('scope_type') == 'auto' and intent and intent.specification
              and not metadata.get('vehicle_independent')
              and (not selected or not vehicles)):
            reason = 'Exact specifications require a matching vehicle reference'
        elif not metadata.get("vehicle_independent") and len(vehicles) != 1:
            reason = "Vehicle applicability is unresolved"
        elif vehicles:
            vehicle = vehicles[0]
            year = metadata.get("year") or vehicle.get("year", "")
            engine = metadata.get("engine") or vehicle.get("engine", "")
            variant = metadata.get("variant") or vehicle.get("variant", "")
            identity = (vehicle["id"], year, engine, variant)
            if intent and intent.requested_year and not year_matches(intent.requested_year, year):
                reason = "Requested model year is incompatible or unverified"
            if intent:
                for requested, declared in ((intent.requested_engine, engine), (intent.requested_variant, variant)):
                    if requested and requested.casefold() not in declared.casefold():
                        reason = "Requested configuration is unverified"
        if reason:
            excluded.append({"id": record.chunk_id, "reason": reason})
        else:
            eligible.append(record)
            if identity:
                identities.add(identity)
    if len(identities) > 1:
        return [], excluded + [{"reason": "Multiple vehicle configurations; clarification required"}]
    return eligible, excluded


def answer_schema(labels, reference_labels=(), guide_labels=(), video_labels=(), *, education=False):
    return {"type": "object", "properties": {
        "outcome": {"type": "string", "enum": ["answer", "text_answer", "reference_only", "clarification", "insufficient_evidence",
                                                *([] if education else ["restricted"]), "emergency", "chat", "out_of_scope"]},
        "blocks": {"type": "array", "maxItems": 8,
        "description": "Ordered readable sections. Separate identification and its picture from the procedure. Separate general guidance from exact source-specific values so independent claims survive validation.",
        "items": {"type": "object", "properties": {
            "text": {"type": "string", "description": "One coherent section in natural English. Use a brief Markdown heading for a substantial section, bullets for comparisons or numbered procedure steps."},
            "references": {"type": "array", "maxItems": min(5, len(reference_labels)),
                           "description": "Display these selected V references immediately after this block. Also select them in top-level references.",
                           "items": {"type": "string", **({"enum": list(reference_labels)} if reference_labels else {})}},
            "basis": {"type": "string", "enum": ["source", "general", "limitation"]},
            "table_context_sufficient": {"type": "boolean", "description":
                "True only if any table-based claims have all required visible rows, headers, conditions and notes. "
                "False when necessary context is missing or unresolved; use a limitation instead."},
            "sources": {"type": "array", "minItems": 0, "maxItems": len(labels),
                        "items": {"type": "string", **({"enum": labels} if labels else {})}}},
            "required": ["text", "sources", "basis", "table_context_sufficient", "references"], "additionalProperties": False}},
        "references": {"type": "array", "maxItems": 5 if reference_labels else 0,
                       "items": {"type": "string", **({"enum": list(reference_labels)} if reference_labels else {})}},
        "recommended_guides": {"type": "array", "maxItems": min(2, len(guide_labels)),
                               "items": {"type": "string", **({"enum": list(guide_labels)} if guide_labels else {})}},
        "recommended_videos": {"type": "array", "maxItems": min(2, len(video_labels)),
                               "items": {"type": "string", **({"enum": list(video_labels)} if video_labels else {})}},
        "clarification": {"description": "A focused follow-up question, required for outcome clarification; "
                          "also allowed after an answer. Otherwise null. Do not put the answer here.",
                          "anyOf": [{"type": "string", "minLength": 1, "maxLength": 300}, {"type": "null"}]}},
        "required": ["outcome", "blocks", "references", "clarification", "recommended_guides", "recommended_videos"], "additionalProperties": False}


def normalize_number_formatting(text):
    """Comparison text only; do not infer decimal formats or convert units."""
    text = unicodedata.normalize("NFKC", text)

    def normalize(match):
        value = match.group()
        # Match a whole numeric token, so mixed separators such as 1,000.5
        # stay literal. Sentence punctuation is outside the numeric token.
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", value):
            return value.replace(",", "")
        return value

    return re.sub(r"\d+(?:[.,]\d+)*", normalize, text)


def factual_numbers(text, *, personal=False):
    text = normalize_number_formatting(text)
    # Ordered-list markers are presentation, not manufacturer values.
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    numbers = re.findall(r"\d+(?:[.,]\d+)*", text)
    # Saved monetary values serialize as decimals (e.g. 120.00); ordinary
    # presentation as RM 120 or RM 120.0 must compare as the same amount.
    if not personal:
        return numbers
    normalized = []
    for value in numbers:
        if re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', value):
            value = value.replace(',', '')
        if re.fullmatch(r'\d+(?:\.\d+)?', value):
            value = format(Decimal(value), 'f')
            if '.' in value:
                value = value.rstrip('0').rstrip('.')
        normalized.append(value)
    return normalized


def numeric_error(text, source, *, specification=False):
    """Check exact values, not the wording of ordinary explanations.

    These checks establish numeric/provenance integrity only. They do not prove
    a number belongs to a particular condition or that a sentence is entailed.
    Personal facts retain strict value checking because they must not be recalculated.
    """
    text = normalize_number_formatting(text)
    personal = source["label"].startswith("P")
    numbers = factual_numbers(text, personal=personal)
    measurements = re.findall(r"(?<![\w.,])(\d+(?:[.,]\d+)*)(?![\d.,])\s*(kpa|psi|nm|litres?|liters?)\b", text, re.I)
    exact_value = bool(measurements) or (specification and bool(numbers))
    if source.get('source_type') == 'general':
        # Ordinary explanations must not quietly invent a service interval or
        # other measured requirement just because intent.specification is false.
        other_measurement = re.search(
            r'(?<![\w.,])\d+(?:[.,]\d+)*(?![\d.,])\s*'
            r'(?:km|kilomet(?:er|re)s?|miles?|mm|cm|bar|ml|'
            r'kgf\s*/\s*cm[²2]|seconds?|minutes?|hours?|days?|weeks?|months?|years?|°\s*[cf])\b',
            text, re.I)
        return 'unverified_measurement' if exact_value or other_measurement else None
    if source.get('pixels_supplied') is True:
        # Pixels are model-inspected evidence, not a deterministic OCR transcript.
        # Exact specifications retain the existing manufacturer verification rule.
        if exact_value and (source['document_type'] not in
                {'owners_manual', 'maintenance_booklet', 'service_manual'} or not source['source_fidelity_verified']):
            return 'unverified_measurement'
        return None
    source_text = source['content']
    structured_table = source.get('evidence_type') in {'table_cells_v1', 'table_cells_v2'}
    if structured_table:
        table = json.loads(source_text)
        # Coordinates/spans are generated metadata, never manufacturer values.
        source_text = table_literal_text(table)
    source_text = normalize_number_formatting(source_text)
    supported = factual_numbers(source_text + " " + source.get("title", ""), personal=personal)
    if any(number not in supported for number in numbers):
        return "unsupported_number"
    if not personal and exact_value:
        if (source["source_type"] != "manual" or source["document_type"] not in
                {"owners_manual", "maintenance_booklet", "service_manual"} or not source["source_fidelity_verified"]):
            return "unverified_measurement"
    for value, unit in measurements:
        if unit.lower().startswith(('litre', 'liter')):
            unit_pattern = r"(?:l|litres?|liters?)"
        else:
            unit_pattern = re.escape(unit)
        if structured_table:
            # Units often live in explicit column headers rather than value cells.
            # This checks literal support only; generation must establish applicability.
            matched = re.search(r'\b' + unit_pattern + r'\b', source_text, re.I)
        else:
            matched = re.search(r"(?<![\w.,])" + re.escape(value) + r"\s*" + unit_pattern + r"\b", source_text, re.I)
        if not matched:
            return "number_unit_mismatch"
    return None


def original_page_cited(source, block_labels, sources, references):
    """A crop or OCR citation needs a corresponding supplied full-page citation."""
    for label in block_labels:
        page = sources[label]
        if not page.get('pixels_supplied') or page.get('source_extent') != 'page':
            continue
        if source['label'] == label:
            return True
        for reference in references:
            evidence = reference.get('evidence_labels', [])
            if source['label'] not in evidence or label not in evidence:
                continue
            if source.get('pixels_supplied'):
                # Detail crops may belong to a related section page rather than
                # the initially retrieved table. Require that crop's own page.
                if source.get('physical_page') is not None and source['physical_page'] == page.get('physical_page'):
                    return True
            elif any(item.get('source_label') == label and item.get('role', 'table') == 'table'
                     for item in reference.get('visual_coverage', {}).get('page_inputs', [])):
                return True
    return False


@observed('answer_generation')
def generate(question, records, client, *, scope, risk, vehicle_profile=None,
             maintenance_context=None, diagnostics=None, intent=None, history=None,
             references=None, latest_message=None, images=None, image_sources=None,
             activity_context=None, assistance=None, supplementary_videos=None,
             _validation_feedback=None):
    references = references or []
    # Context packing removes internal join keys and bounds the image shortlist.
    # A correction must start from the caller's evidence, not that packed output.
    original_references, original_images, original_image_sources = references, images, image_sources
    selected_references = []
    allow_videos = True
    raw = None

    def correction(reply, reason):
        """One evidence-preserving correction; validation is never relaxed."""
        recoverable = {'model_wrote_citations', 'invalid_citation', 'invalid_citation_basis',
                       'unverified_values', 'table_context', 'no_supporting_answer'}
        if _validation_feedback is not None or raw is None or reason not in recoverable:
            return reply
        repair_diagnostics = {}
        try:
            repaired = generate(question, records, client, scope=scope, risk=risk,
                vehicle_profile=vehicle_profile, maintenance_context=maintenance_context,
                diagnostics=repair_diagnostics, intent=intent, history=history,
                references=original_references, latest_message=latest_message, images=original_images,
                image_sources=original_image_sources, activity_context=activity_context, assistance=assistance,
                supplementary_videos=supplementary_videos,
                _validation_feedback={'reason': reason})
        except Exception:
            if diagnostics is not None:
                diagnostics['correction_result'] = 'unavailable'
            return reply
        residual = any(repair_diagnostics.get(key) for key in
                       ('withheld_value_reasons', 'table_original_withheld', 'table_context_withheld', 'discarded_block_reasons'))
        accepted = repaired.status == 'answered' and not residual
        if diagnostics is not None:
            diagnostics['correction_attempted'] = reason
            diagnostics['correction_result'] = 'accepted' if accepted else 'original_retained'
            if accepted:
                diagnostics.update(repair_diagnostics)
        return repaired if accepted else reply

    # Defence at the generation boundary as well as the public query route.
    # Never let supplied manual text authorize a prohibited repair request.
    action_risk = policy_risk(question)
    if immediate_emergency(latest_message or question) or action_risk == "emergency":
        return GeneratedReply(emergency_guidance(latest_message or question), "emergency")
    if action_risk == "high_risk":
        return GeneratedReply(RESTRICTED_ANSWER, "restricted")

    def reject(reason, message=INSUFFICIENT):
        if diagnostics is not None:
            diagnostics["decision_reason"] = reason
        if selected_references:
            reply = GeneratedReply(REFERENCE_ONLY, "reference_only", reference_labels=selected_references,
                                   allow_videos=allow_videos)
        else:
            reply = GeneratedReply(message, allow_videos=allow_videos)
        return correction(reply, reason)

    available_image_labels = {image.label for image in images or []}
    image_sources = [source for source in image_sources or [] if source['label'] in available_image_labels]
    context = prepare_context(records, references, vehicle_profile, maintenance_context,
                              image_sources=image_sources)
    sources, references = context.sources, context.references
    supplied_image_labels = {source['label'] for source in sources if source.get('pixels_supplied')}
    images = [image for image in images or [] if image.label in supplied_image_labels]
    if diagnostics is not None:
        diagnostics.update(supplied_sources=len(sources),
                           evidence_chars=sum(len(s["content"]) for s in sources),
                           omitted_source_labels=context.omitted_sources,
                           incomplete_section_labels=context.incomplete_section_labels,
                           omitted_reference_labels=context.omitted_references)
    prompt = (
        answer_instructions(sources)
        # The search rewrite can lose uncertainty or turn a fear into an incident.
        # Give the writer the actual user message and history, not a second,
        # competing version of what the user supposedly asked.
        + json.dumps({"activity_context": activity_context, "assistance": assistance,
                      "latest_message": latest_message or question,
                      "knowledge_scope": scope["label"], "risk": risk,
                      "selected_vehicle": scope.get("vehicle"),
                      "history": bounded_history(history), "sources": sources, "references": references,
                      "context_incomplete": context.incomplete,
                      "validation_feedback": _validation_feedback,
                      "supplementary_videos": supplementary_videos or []}, ensure_ascii=False)
    )
    allowed_guides = {source['label'] for source in sources if source.get('source_type') == 'learning_guide'}
    allowed_videos = {video['id'] for video in supplementary_videos or [] if video.get('id')}
    options = {'schema': answer_schema([s['label'] for s in sources], [r['label'] for r in references],
                                       sorted(allowed_guides), sorted(allowed_videos),
                                       education=educational_only(question) and action_risk == 'normal')}
    if (_validation_feedback and _validation_feedback.get('reason') in {'unverified_values', 'table_context'}
            and intent and not intent.specification):
        # A general follow-up must remain useful without borrowing an exact
        # target from history. Regenerate whole prose; never strip a number
        # out of the rejected sentence and assume the remainder is valid.
        text_schema = options['schema']['properties']['blocks']['items']['properties']['text']
        text_schema['pattern'] = r'^[^0-9]*$'
        text_schema['description'] += ' Correction of general guidance: no digits, quantities or spelled-out measurements. Use bullets rather than numbered steps; refer to the manufacturer label for any target.'
    if images:
        options['images'] = images
    raw = client.generate(prompt, **options)
    answer = json.loads(raw)
    # Production clients expose this explicit capability; minimal standalone
    # adapters may supply already reviewed answers through generate alone.
    # Both the draft and reviewed output still pass the integrity checks below.
    if (settings.RAG_GROUNDING_REVIEW and sources and isinstance(answer, dict)
            and answer.get('outcome') in {'answer', 'text_answer'} and answer.get('blocks')
            and getattr(type(client), 'review_grounding', None) is not None):
        reviewed = client.review_grounding(draft=answer, question=latest_message or question,
            sources=sources, schema=options['schema'], images=images or None)
        raw = reviewed
        answer = json.loads(reviewed)
        if diagnostics is not None:
            diagnostics['grounding_review'] = 'completed'
    if (not isinstance(answer, dict)
            or not {"outcome", "blocks", "clarification", "references"}.issubset(answer)
            or not set(answer).issubset({"outcome", "blocks", "clarification", "references",
                                       "recommended_guides", "recommended_videos"})
            or not isinstance(answer["blocks"], list)):
        return reject("invalid_answer_schema")
    video_labels = answer.get('recommended_videos', [])
    if (not isinstance(video_labels, list) or len(video_labels) > 2
            or any(not isinstance(label, str) or label not in allowed_videos for label in video_labels)):
        return reject('invalid_video_recommendation')
    guide_labels = answer.get('recommended_guides', [])
    if (not isinstance(guide_labels, list) or len(guide_labels) > 2
            or any(not isinstance(label, str) or label not in allowed_guides for label in guide_labels)):
        return reject('invalid_guide_recommendation')
    outcome = answer["outcome"]
    if outcome not in ("answer", "text_answer", "reference_only", "clarification", "insufficient_evidence",
                       "restricted", "emergency", "chat", "out_of_scope"):
        return reject("invalid_outcome")
    if diagnostics is not None:
        diagnostics["generation_outcome"] = outcome
    if (outcome == 'text_answer' and video_labels
            and not re.search(r'\b(?:text.only|no videos?|without videos?|original.only|manual.only)\b',
                              latest_message or question, re.I)):
        # Candidates are request-gated by the query route. A mistaken delivery
        # enum must not hide the link that was actually requested and selected.
        outcome = 'answer'
    allow_videos = outcome != 'text_answer'
    chosen = answer["references"]
    allowed_references = {r["label"] for r in references}
    if (not isinstance(chosen, list) or len(chosen) > 5
            or any(not isinstance(label, str) or label not in allowed_references for label in chosen)):
        return reject("invalid_reference")
    if len(answer["blocks"]) > 8:
        return reject("invalid_answer_length")
    clarification = answer["clarification"]
    if clarification is not None:
        if not isinstance(clarification, str) or not 0 < len(clarification.strip()) <= 300:
            return reject('invalid_outcome_fields')
        clarification = clarification.strip()
        if MODEL_CITATIONS.search(clarification):
            return reject('model_wrote_citations')
    if outcome == "clarification":
        if answer["blocks"] or chosen or clarification is None:
            return reject("invalid_outcome_fields")
        if diagnostics is not None:
            diagnostics["decision_reason"] = "clarification_required"
        return GeneratedReply(clarification.strip(), "clarification")
    if clarification is not None and outcome not in {'answer', 'text_answer'}:
        return reject("invalid_outcome_fields")
    if outcome in {'restricted', 'emergency', 'chat', 'out_of_scope'}:
        if answer['blocks'] or chosen:
            return reject('invalid_outcome_fields')
        messages = {
            'restricted': RESTRICTED_ANSWER,
            'emergency': emergency_guidance(latest_message or question),
            'chat': "I'm here to help with your vehicle. What would you like to know?",
            'out_of_scope': 'I can help with car questions, maintenance and roadside guidance.',
        }
        if diagnostics is not None:
            diagnostics['decision_reason'] = outcome
        return GeneratedReply(messages[outcome], outcome)
    if outcome == 'reference_only' or (outcome == 'answer' and not answer['blocks'] and chosen):
        if answer['blocks']:
            return reject('invalid_outcome_fields')
        # A display request has no factual-answer requirement. A valid source
        # selection survives either known non-clarification outcome label.
        selected_references = list(dict.fromkeys(chosen))
        if diagnostics is not None:
            diagnostics['decision_reason'] = 'requested_references' if selected_references else 'insufficient_evidence'
        if selected_references:
            return GeneratedReply('The requested original reference material is shown below.',
                                  'reference_only', reference_labels=selected_references)
        return reject('insufficient_evidence')
    if (outcome in {'answer', 'text_answer'} and not answer["blocks"]) or (
            outcome == "insufficient_evidence" and any(
                not isinstance(block, dict) or block.get('basis') != 'limitation' for block in answer['blocks'])):
        return reject("invalid_outcome_fields")
    selected_references = [] if outcome == 'text_answer' else list(dict.fromkeys(chosen))
    if outcome == "insufficient_evidence" and not answer['blocks']:
        return reject("insufficient_evidence")
    labels = {s["label"]: s for s in sources}
    paragraphs, citations, sections = [], [], []

    def append_section(text, block=None):
        if text in paragraphs:
            return
        placements = (block or {}).get('references', [])
        if not isinstance(placements, list):
            placements = []
        placed = {label for section in sections for label in section['reference_labels']}
        placements = [label for label in placements[:5]
                      if isinstance(label, str) and label in selected_references and label not in placed]
        paragraphs.append(text)
        sections.append({'text': text, 'reference_labels': list(dict.fromkeys(placements))})
    withheld_values = False
    withheld_direction = False
    withheld_basis = False
    has_general_information = False
    for block in answer["blocks"]:
        # Older saved responses omit basis; they remain source-only blocks.
        if (not isinstance(block, dict) or not {'text', 'sources'}.issubset(block)
                or not set(block).issubset({'text', 'sources', 'basis', 'table_context_sufficient', 'references'})
                or not isinstance(block["text"], str)
                or ('table_context_sufficient' in block and not isinstance(block['table_context_sufficient'], bool))
                or block.get('basis', 'source') not in {'source', 'general', 'limitation'}
                or not isinstance(block["sources"], list)
                or len(block["sources"]) > len(labels)
                or any(not isinstance(label, str) or label not in labels for label in block["sources"])):
            return reject("invalid_citation")
        basis = block.get('basis', 'source')
        text = block["text"].strip()
        if not text:
            continue
        if (basis == 'source' and not block['sources']) or (basis == 'limitation' and block['sources']):
            # A malformed block is not evidence for its claims, but cannot
            # invalidate independent correctly cited instructions. Never promote
            # an uncited source block into general knowledge automatically.
            if diagnostics is not None:
                diagnostics.setdefault('discarded_block_reasons', []).append('invalid_citation_basis')
            withheld_basis = True
            continue
        declared_labels = list(dict.fromkeys(block['sources']))
        # A general block cannot acquire source authority through an accidental
        # citation array. Keep it general and apply the same numeric restrictions.
        block_labels = [] if basis == 'general' else declared_labels
        if MODEL_CITATIONS.search(text):
            inline = [label.strip() for group in INLINE_CITATIONS.findall(text) for label in group.split(',')]
            if (inline and set(inline).issubset(declared_labels)
                    and not re.search(r'(?im)^sources:', text)):
                # The structured IDs remain authoritative. Duplicate inline
                # markers are presentation noise, not a reason to erase a
                # correctly grounded answer. Unknown/mismatched IDs still fail.
                text = INLINE_CITATIONS.sub('', text).strip()
            else:
                return reject("model_wrote_citations")
        if unrequested_battery_procedure(text, intent):
            if diagnostics is not None:
                diagnostics.setdefault('discarded_block_reasons', []).append('unrequested_battery_procedure')
            continue
        if engine_bay_direction(text):
            withheld_direction = True
            if diagnostics is not None:
                diagnostics.setdefault('discarded_block_reasons', []).append('engine_bay_direction')
            continue
        uses_table = any(labels[label].get('content_type') == 'table' or labels[label].get('contains_table')
                         for label in block_labels)
        table_refs = [reference for reference in references if reference.get('kind') == 'table'
                      and set(block_labels).intersection(reference.get('evidence_labels', []))]
        if basis == 'source' and uses_table:
            # Page citations validate evidence; Gemini chooses which individual
            # originals help the user. Do not attach every table sharing a page.
            required = [labels[label] for label in block_labels if labels[label].get('requires_page_images')]
            if block.get('table_context_sufficient') is True:
                # Complete provenance from exact source-element/page joins. The
                # model already receives these originals and attests that the
                # relevant table context is visible. Omitting a duplicate page
                # ID must not erase a valid answer. Never add an unavailable or
                # merely adjacent page, or infer inspection when the flag is false.
                for source in required:
                    if original_page_cited(source, block_labels, labels, table_refs):
                        continue
                    for label, page in labels.items():
                        if (page.get('pixels_supplied') and page.get('source_extent') == 'page'
                                and original_page_cited(source, [source['label'], label], labels, table_refs)):
                            if label not in block_labels:
                                block_labels.append(label)
            missing_pages = any(not original_page_cited(source, block_labels, labels, table_refs)
                                for source in required)
            if missing_pages:
                limitation = ("I couldn't confirm the table details needed for this part. "
                              "Please check the original table and its notes before using those values.")
                append_section(limitation)
                if diagnostics is not None:
                    diagnostics['table_original_withheld'] = True
                continue
        if basis == 'source' and uses_table and block.get('table_context_sufficient') is not True:
            limitation = ("I couldn't confirm which table conditions apply to this part. "
                          "Please check its headings and notes before using those values.")
            append_section(limitation)
            if diagnostics is not None:
                diagnostics['table_context_withheld'] = True
            continue
        if basis in {'general', 'limitation'}:
            if basis == 'general':
                error = numeric_error(text, {'label': 'G', 'source_type': 'general'},
                                      specification=bool(intent and intent.specification))
                if error:
                    withheld_values = True
                    if diagnostics is not None:
                        diagnostics.setdefault('withheld_value_reasons', []).append(error)
                    continue
                # The answer explains general guidance naturally; keep provenance
                # in metadata instead of prepending a disclaimer to every block.
                has_general_information = True
            append_section(text, block)
            continue
        # One cited passage must independently support all values and their
        # provenance. Combining citations must not pool unrelated numbers or
        # borrow verification from a source that does not contain the values.
        errors = [numeric_error(text, labels[label], specification=bool(intent and intent.specification))
                  for label in block_labels]
        if all(errors):
            reason = "unverified_measurement" if "unverified_measurement" in errors else errors[0]
            withheld_values = True
            if diagnostics is not None:
                diagnostics.setdefault('withheld_value_reasons', []).append(reason)
            continue
        paragraph = text + " " + " ".join(f"[{label}]" for label in block_labels)
        if paragraph not in paragraphs:
            append_section(paragraph, block)
            citations.extend(block_labels)
    if withheld_values:
        append_section("I couldn't confirm one or more exact values in this answer, so those claims have been left out.")
    if withheld_direction:
        append_section("I can't confidently describe this part's left/right position. Please check the original illustration rather than relying on a guessed direction.")
    if not paragraphs:
        return reject("no_supporting_answer")
    if clarification and clarification not in '\n\n'.join(paragraphs):
        append_section(clarification)
    if diagnostics is not None:
        cited = [records[int(label[1:]) - 1] for label in citations if label.startswith("S")]
        diagnostics.update(decision_reason="answered", cited_labels=list(dict.fromkeys(citations)),
                           manual_relevant=any(r.metadata.get("source_type", "manual") == "manual" for r in cited),
                           content_relevant=any(r.metadata.get("source_type", "manual") != "manual" for r in cited),
                           profile_relevant="P1" in citations, maintenance_relevant="P2" in citations,
                           has_general_information=has_general_information)
    supported = bool(citations) or has_general_information
    if diagnostics is not None and not supported:
        diagnostics['decision_reason'] = 'insufficient_evidence'
    if (not supported and video_labels and allow_videos and not selected_references
            and not withheld_values and not withheld_basis and not withheld_direction
            and all(block.get('basis') == 'limitation' for block in answer['blocks'])):
        # Link availability is application state, not a model-generated factual
        # claim. Use one consistent notice for a validated link-only delivery.
        text = 'A related external video is included. Its content and vehicle compatibility have not been verified.'
        return GeneratedReply(text, 'video_only', video_labels=list(dict.fromkeys(video_labels)),
                              answer_sections=[{'text': text, 'reference_labels': []}])
    reply = GeneratedReply("\n\n".join(paragraphs), "answered" if supported else "insufficient_information",
                          list(dict.fromkeys(citations)), selected_references,
                          allow_videos=allow_videos and (supported or bool(video_labels)),
                          has_general_information=has_general_information,
                          guide_labels=list(dict.fromkeys(guide_labels)) if supported and outcome != 'text_answer' else [],
                          video_labels=list(dict.fromkeys(video_labels)) if allow_videos else [],
                          answer_sections=sections)
    reason = ('unverified_values' if withheld_values else 'table_context'
              if diagnostics is not None and (diagnostics.get('table_original_withheld') or diagnostics.get('table_context_withheld'))
              else 'invalid_citation_basis' if withheld_basis else None)
    return correction(reply, reason) if reason else reply
