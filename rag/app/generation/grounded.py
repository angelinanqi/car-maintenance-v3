"""One natural-language generation pass over scoped, labelled evidence."""
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from shared.observability import observed
from shared.table_evidence import table_literal_text, table_claim_error, MEASUREMENT, canonical_unit
from shared.safety import SOURCE_INJECTION, policy_risk, RESTRICTED_ANSWER, professional_overview
from shared.chat_preferences import videos_excluded, puncture_repair_request
from rag.app.generation.context import content, prepare_context, bounded_history
from rag.app.generation.answer_prompt import ANSWER_PROMPT
from rag.app.generation.provider import GenerationError
from rag.config import settings

logger = logging.getLogger(__name__)
INJECTION = SOURCE_INJECTION
INSUFFICIENT = "I don't have enough relevant evidence to answer that reliably."
CLARIFY = "Please confirm the vehicle model, year, engine and variant."
CITATIONS = re.compile(r'\[([SP]\d+(?:\s*,\s*[SP]\d+)*)\]')


def unrequested_battery_procedure(text, intent, question=''):
    """Do not turn a starting-symptom explanation into cable-handling steps."""
    excluded = re.search(r'\b(?:avoid|without|no|do not|don\x27t)\b.{0,40}\b(?:jump[- ]?start|battery|cables?|terminals?)', question, re.I)
    if not excluded and (not intent or intent.instructional):
        return False
    for match in re.finditer(r'\b(disconnect(?:ed|ing)?|connect(?:ed|ing)?|remov(?:e|ed|ing))\b.{0,100}'
                             r'\b(battery|terminal|jumper|negative lead|negative cable)\b', text, re.I):
        prefix = text[max(0, match.start() - 20):match.start()]
        if not re.search(r'\b(?:not|never|avoid)\s+(?:ever\s+)?$', prefix, re.I):
            return True
    return False


def unrequested_fluid_procedure(text, question):
    requested = re.search(r'\b(?:want to|how (?:do|can|should|to)|steps to|help me)\b.{0,40}'
                          r'\b(?:refill|top[ -]?up|add|change|drain|open|pour)\b|'
                          r'^\s*(?:refill|top[ -]?up|add|change|drain|open|pour)\b', question, re.I)
    if requested:
        return False
    if not re.search(r'\b(?:fluid|coolant|oil|washer|reservoir|antifreeze)\b', question, re.I):
        return False
    pattern = (r'\b(?:unscrew|open|remove|unclip)\w*\s+'
               r'(?:(?:the|a|an|its|pressuri[sz]ed|coolant|radiator|brake|fluid|washer|reservoir|tank|filler|plastic|metal|oil|reserve)\s+){0,5}'
               r'(?:cap|cover|reservoir|tank|bail)\b|'
               r'\b(?:cap|cover|reservoir)\b.{0,60}\b(?:removed|opened|unscrewed|unclipped)\b|'
               r'\b(?:add|pour|fill|mix)\w*\b.{0,50}\b(?:oil|fluid|coolant|antifreeze)\b')
    for match in re.finditer(pattern, text, re.I):
        prefix = text[max(0, match.start() - 40):match.start()]
        if re.search(r'\b(?:not|never|avoid|without)\s+(?:\w+\s+){0,3}$', prefix, re.I):
            continue
        if re.search(r'\b(?:must|should|can)\s+not\b', match[0], re.I):
            continue
        if (re.search(r'\bwasher\s+fluid\b', match[0], re.I)
                and re.search(r'\bwasher\b', question, re.I)
                and re.search(r'\b(?:identify|bottle|reservoir|cap)\b', question, re.I)):
            continue
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


def operational_overview(text):
    """Keep professional education at stage/purpose level, not dismantling steps."""
    pattern = (r'\b(?:bleed\w*|brake lines|torque all|braking distance)\b|'
               r'\bunbolt\w*\b|\bremov\w*\b.{0,60}\b(?:wheels?|calipers?|rotors?)\b|'
               r'\b(?:compress\w*|retract\w*|push\w*|press\w*)\b.{0,40}\bpistons?\b|'
               r'\bdisconnect\w*\b.{0,40}\b(?:batter(?:y|ies)|cables?|terminals?)\b')
    for match in re.finditer(pattern, text, re.I):
        prefix = text[max(0, match.start() - 30):match.start()]
        if not re.search(r'\b(?:not|never|avoid)\s+(?:\w+\s+){0,2}$', prefix, re.I):
            return True
    return False


def spare_change_steps(text):
    """Detect a substituted wheel-change sequence, not a mention of the option."""
    pattern = (r'\b(?:loosen\w*|tighten\w*|remov\w*)\b.{0,45}\b(?:lug|wheel) nuts\b|'
               r'\b(?:jack\w*|lift\w*|rais\w*)\b.{0,35}\b(?:car|vehicle)\b|'
               r'\b(?:install\w*|mount\w*)\b.{0,25}\bspare\b')
    for match in re.finditer(pattern, text, re.I):
        if not re.search(r'\b(?:not|never|avoid)\s+(?:\w+\s+){0,2}$', text[max(0, match.start()-30):match.start()], re.I):
            return True
    return False


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
def applicable(records, scope, *, intent=None):
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
                    if requested and not re.search(r'(?<!\w)' + re.escape(requested)
                                                   + r'(?!\w|\.\d)', declared, re.I):
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


def normalize_number_formatting(text):
    """Comparison text only; do not infer decimal formats or convert units."""
    text = unicodedata.normalize("NFKC", text).replace('−', '-')

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


def numeric_error(text, source, *, specification=False, question=''):
    """Check exact values, not the wording of ordinary explanations.

    These checks establish numeric/provenance integrity only. They do not prove
    a number belongs to a particular condition or that a sentence is entailed.
    Personal facts retain strict value checking because they must not be recalculated.
    """
    text = normalize_number_formatting(text)
    personal = source["label"].startswith("P")
    numbers = factual_numbers(text, personal=personal)
    measurements = [(m[1], m[2]) for m in MEASUREMENT.finditer(text)]
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
        try:
            table = json.loads(source_text)
            relationship_error = table_claim_error(text, table, question)
        except (ValueError, KeyError, TypeError):
            return 'malformed_table'
        if relationship_error:
            return relationship_error
        # Coordinates/spans are generated metadata, never manufacturer values.
        source_text = table_literal_text(table)
    if (structured_table and numbers and re.search(r'air pressure|torque|capacity|temperature', source_text, re.I)
            and not re.search(r'\b(?:kpa|psi|bar|n[.·]?m|litres?|liters?|ml|kgf)\b|°\s*[cf]', source_text, re.I)):
        return 'missing_table_units'
    source_text = normalize_number_formatting(source_text)
    supported = factual_numbers(source_text + " " + source.get("title", ""), personal=personal)
    if any(number not in supported for number in numbers):
        return "unsupported_number"
    if not personal and exact_value:
        if (source["source_type"] != "manual" or source["document_type"] not in
                {"owners_manual", "maintenance_booklet", "service_manual"} or not source["source_fidelity_verified"]):
            return "unverified_measurement"
    for value, unit in measurements:
        if canonical_unit(unit) == 'l':
            unit_pattern = r"(?:l|litres?|liters?)"
        elif canonical_unit(unit) == 'nm':
            unit_pattern = r'n[.·]?m'
        elif canonical_unit(unit) == 'kgf/cm2':
            unit_pattern = r'kgf\s*/\s*cm[²2]'
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


def clean_prose_artifact(text, sources=()):
    # Small local models can put a closing JSON fragment inside the text string.
    # Remove only an unmistakable trailing delimiter after a complete sentence;
    # do not repair factual claims or relax citation/value validation.
    text = re.sub(r'(?s)(?<=[.!?])[”"]\s*[}\]]\s*,.*$', '', text).strip()
    headings = {f"[{s['label']}] {s.get('title', 'Saved records')} — {source_authority(s)}": f"[{s['label']}]"
                for s in sources}
    lines, intro_seen = [], False
    for line in text.splitlines():
        if line.strip().lower() == 'from the supplied evidence:':
            if intro_seen:
                continue
            intro_seen = True
        lines.append(headings.get(line.strip(), line))
    return '\n'.join(lines).strip()


def source_text(source):
    """Readable evidence without JSON coordinates or application identifiers."""
    if source.get('evidence_type') in {'table_cells_v1', 'table_cells_v2'}:
        table = json.loads(source['content'])
        cells = table['cells']
        if 'cell_fields' in table:
            cells = [dict(zip(table['cell_fields'], cell)) for cell in cells]
        rows = {}
        for cell in sorted(cells, key=lambda c: (c['row'], c['column'])):
            rows.setdefault(cell['row'], []).append(cell['text'])
        text = '\n'.join(' | '.join(values) for values in rows.values())
        notes = '\n'.join(table.get('notes', []))
        if re.search(r'Associated source unit heading:\s*kPa\s*\(kgf/cm2,\s*psi\)', notes, re.I):
            # Spell out the printed column-unit order; do not ask a small model
            # to infer which of three parenthesised values has which unit.
            text = re.sub(r'(?<![\w.])(\d+(?:\.\d+)?)\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)',
                lambda m: f'{m[1]} kPa ({m[2]} kgf/cm², {m[3]} psi)', text)
        return ('Extracted table (do not infer missing units or header relationships):\n'
                + text + '\n' + notes)
    return source['content']


def source_authority(source):
    """An uploaded PDF is not necessarily a manufacturer instruction."""
    if source.get('source_type') == 'manual':
        if source.get('document_type') in {'owners_manual', 'service_manual', 'maintenance_booklet'}:
            return ('Applicable manufacturer source' if source.get('source_fidelity_verified')
                    else 'Manufacturer document; extraction unverified for exact values')
        return 'General reference; not manufacturer instructions'
    return source.get('source_type') or source.get('document_type', 'Reference')


def excerpt_matches(question, source):
    """Require substantive task overlap before displaying a fallback passage."""
    stop = set(('a an the is are was were be been being i we you my your our it its this that those '
                'how what when where why which can could do does should would will to for of in on '
                'at by with from and or but if then about please check checking inspect inspection '
                'explain tell show give use using steps procedure instructions level recommended '
                'follow up car vehicle manual source help exact really together').split())
    def words(text):
        # Match technical compounds just as the lexical retriever does. A query
        # about engine-oil must match literal manufacturer wording "engine oil".
        text = re.sub(r'(?<=[A-Za-z])[-/](?=[A-Za-z])', ' ', text)
        return {word.lower().rstrip('s') for word in re.findall(r'[A-Za-z][A-Za-z0-9/-]*', text)
                if word.lower() not in stop and len(word) > 2}
    requested = words(question)
    found = words(source['content'] + ' ' + source.get('title', ''))
    return bool(requested and len(requested & found) >= min(2, len(requested)))


def extracted_reply(sources, reason, diagnostics=None, *, prefix=None, question='', intent=None):
    """A factual fallback, never a second model rewrite or a guessed citation."""
    if diagnostics is not None:
        diagnostics.update(answer_mode='source_excerpt', fallback_reason=reason,
                           decision_reason='source_excerpt')
    prose = [s for s in sources if s.get('content_type', 'paragraph') == 'paragraph'
             and s.get('evidence_type') != 'ingestion_image_description' and not s['label'].startswith('P')]
    if not prose:
        return GeneratedReply(prefix or INSUFFICIENT)
    chosen = [s for s in prose if excerpt_matches(question, s)
              and not unrequested_battery_procedure(s['content'], intent, question)
              and not unrequested_fluid_procedure(s['content'], question)
              and not (puncture_repair_request(question) and spare_change_steps(s['content']))
              and numeric_error(s['content'], {'document_type': 'other_reference',
                  'source_fidelity_verified': False, **s},
                  specification=bool(intent and intent.specification)) is None]
    if professional_overview(question):
        chosen = [s for s in chosen if not operational_overview(s['content'])]
    preferred = [s for s in chosen if s.get('source_type') == 'learning_guide'
                 or (s.get('source_type') == 'manual' and s.get('source_fidelity_verified')
                     and s.get('document_type') in {'owners_manual', 'service_manual', 'maintenance_booklet'})]
    if preferred:
        chosen = preferred
    # Keep a complete short procedure, rather than cutting its last precautions.
    sections = []
    selected = []
    size = 0
    for source in chosen:
        text = source['content']
        if len(text) > 2400 or size + len(text) > 4000:
            continue
        sections.append(text + ' [' + source['label'] + ']')
        selected.append(source)
        size += len(text)
        if len(selected) == 2:
            break
    if not sections:
        return GeneratedReply(prefix or INSUFFICIENT)
    labels = [s['label'] for s in selected]
    intro = prefix or "I couldn't verify a complete answer. These matching source passages may help:"
    if diagnostics is not None:
        diagnostics['excerpt_source_labels'] = labels
    return GeneratedReply(intro + '\n\n' + '\n\n'.join(sections), 'source_excerpt', cited_labels=labels,
        guide_labels=[s['label'] for s in selected if s.get('source_type') == 'learning_guide'])


def validate_prose(text, sources, *, question='', specification=False):
    """Check ID integrity and literal values. This is not an entailment judge."""
    labels = {s['label']: s for s in sources}
    if text.lstrip().startswith('{') or re.search(r'"(?:blocks|sources|text)"\s*:', text):
        return 'generation_format', []
    cited = list(dict.fromkeys(label.strip() for group in CITATIONS.findall(text) for label in group.split(',')))
    if any(label not in labels for label in cited):
        return 'unknown_citation', cited
    if re.search(r'https?://|www\.', text):
        return 'unverified_link', cited
    if not cited:
        return 'missing_citations', cited
    # Each paragraph/list uses its own citations where supplied. A final citation
    # can cover a contiguous list; source IDs are excluded from number checking.
    for paragraph in re.split(r'\n\s*\n', text):
        local = [label.strip() for group in CITATIONS.findall(paragraph) for label in group.split(',')]
        supporting = [labels[label] for label in (local or cited)]
        literal = CITATIONS.sub('', paragraph)
        if re.search(r'\b(?:manufacturer|owner[\x27’]?s manual|service manual)\s+'
                     r'(?:recommends?|requires?|specifies?|instructs?|states?|says?)\b|'
                     r'\baccording to (?:the |your |this )?(?:manufacturer|owner[\x27’]?s manual|service manual)\b', literal, re.I):
            if not any(s.get('source_type') == 'manual' and s.get('source_fidelity_verified')
                       and s.get('document_type') in {'owners_manual', 'service_manual', 'maintenance_booklet'}
                       for s in supporting):
                return 'unsupported_manufacturer_attribution', cited
        for condition in re.finditer(r'\b(?:below|above|under|over)\s+(?:the\s+)?[“"\x27‘]?([FL])[”"\x27’]?(?=\W|$)', literal):
            if not any(re.search(re.escape(condition[0]), s['content'], re.I) for s in supporting):
                return 'unsupported_marker_condition', cited
        literal = re.sub(r'(?m)^\s*(?:\d+[.)]|[-*])\s+', '', literal)
        for sentence in re.split(r'(?<=[.!?])\s+|\n', literal):
            if not sentence.strip():
                continue
            # Counts, step numbers and the application's selected model year
            # are not safety-critical measurements. Check actual measured values
            # and personal figures, rather than deleting prose for any digit.
            money = bool(re.search(r'\b(?:RM|MYR)\s*\d|\d(?:[\d.,]*\d)?\s*(?:RM|MYR)\b', sentence, re.I))
            ratio = bool(re.search(r'\b\d+(?:\.\d+)?\s*[:/]\s*\d+(?:\.\d+)?\b', sentence))
            personal_money = money and (any(s['label'] == 'P2' for s in sources)
                or re.search(r'\b(?:you|your|my|spent|paid|recorded|total)\b', sentence, re.I))
            if personal_money:
                personal_support = [source for source in supporting if source['label'] == 'P2']
                if not personal_support:
                    return 'missing_personal_citation', cited
                if all(numeric_error(sentence, source) for source in personal_support):
                    return 'unsupported_value', cited
            measured = money or re.search(r'\d\s*(?:kpa|psi|bar|n[.·]?m|kgf|mm|cm|km|litres?|liters?|ml|'
                r'seconds?|minutes?|hours?|days?|weeks?|months?|years?|%|°\s*[cf])\b|'
                r'\b\d+\s*[wW][-/]?\s*\d+\b|\b\d{3}/\d{2}[rR]\d+\b|\bRM\s*\d', sentence, re.I)
            personal = any(s['label'].startswith('P') for s in supporting)
            if (measured or ratio or MEASUREMENT.search(sentence) or personal or specification) and all(numeric_error(
                    sentence, source, specification=specification or ratio, question=question) for source in supporting):
                return 'unsupported_value', cited
    return None, cited


def unsupported_vehicle_configuration(text, question, scope):
    """Do not turn an optional transmission into a confirmed saved-car feature."""
    selected = scope.get('vehicle') or {}
    declared = ' '.join(str(selected.get(key) or '') for key in ('transmission', 'variant'))
    for kind in ('automatic', 'manual'):
        if (re.search(r'\b' + kind + r'\b', declared, re.I)
                or re.search(r'\b(?:my|our|this)\s+' + kind + r'\s+(?:transmission|gearbox|car|vehicle)\b|'
                    r'\b(?:my|our|this)\s+(?:car|vehicle)\s+(?:is|uses|has)\s+(?:an?\s+)?' + kind + r'\b', question, re.I)):
            continue
        for sentence in re.split(r'(?<=[.!?])\s+|\n', text):
            if re.search(r'\b(?:if|whether|may|might|depending)\b', sentence, re.I):
                continue
            if re.search(r'\b(?:your|this|selected)\s+(?:(?:car|vehicle)(?:[’\x27]s)?\s+)?'
                         + kind + r'\s+transmission\b', sentence, re.I):
                return True
    return False


def repair_table_citations(text, sources):
    """Repair only uniquely supported literal rows, not merely related documents."""
    labels = {s['label']: s for s in sources}
    sentences = re.split(r'((?<=[.!?])\s+)', text)
    for index in range(0, len(sentences), 2):
        sentence = sentences[index]
        size = re.search(r'\b\d{3}/\d{2}R\d+\b', sentence, re.I)
        if not size:
            continue
        cited = [label.strip() for group in CITATIONS.findall(sentence) for label in group.split(',')]
        literal = CITATIONS.sub('', sentence)
        if not cited or any(label not in labels for label in cited):
            continue
        if any(numeric_error(literal, labels[label]) is None for label in cited):
            continue
        candidates = [s for s in sources if s.get('evidence_type') in {'table_cells_v1','table_cells_v2'}
            and s.get('source_fidelity_verified') and size[0] in s['content']
            and numeric_error(literal, s) is None]
        if len(candidates) == 1:
            sentences[index] = literal.strip() + ' [' + candidates[0]['label'] + ']'
    return ''.join(sentences)


def manufacturer_procedure(question, sources, records):
    """Preserve a whole verified, relevant passage with a complete numbered list.

    Never join fragments by similarity or promote a generated image description
    to a manufacturer procedure. Applicability was checked before generation.
    """
    from rag.app.retrieval.prose import query_facets
    if len(query_facets(question)) > 1 or question.count('?') > 1:
        return None
    if professional_overview(question) or not re.search(
            r'\b(?:how (?:do|can|should|to)|explain how|steps?|procedure|sequence|instructions?|check|checking|prepare)\b', question, re.I):
        return None
    for source in sources:
        if (source.get('source_type') != 'manual'
                or source.get('document_type') not in {'owners_manual','service_manual','maintenance_booklet'}
                or not source.get('source_fidelity_verified')
                or source.get('content_type') != 'paragraph'
                or source.get('evidence_type') == 'ingestion_image_description'
                or not excerpt_matches(question, source)):
            continue
        index = int(source['label'][1:]) - 1
        metadata = records[index].metadata
        if (metadata.get('section_chunk_count', 1) != 1
                or metadata.get('source_quality') in {'incomplete','corrupt','unreliable'}
                or metadata.get('relevance_score', 0) < -1):
            continue
        numbers = [int(n) for n in re.findall(r'(?m)^\s*(\d+)[.)]\s+', source['content'])]
        if len(numbers) >= 2 and numbers == list(range(1, len(numbers) + 1)):
            return source
    return None


@observed('answer_generation')
def generate(question, records, client, *, scope, risk, vehicle_profile=None,
             maintenance_context=None, diagnostics=None, intent=None, history=None,
             references=None, latest_message=None, images=None, image_sources=None,
             activity_context=None, assistance=None, supplementary_videos=None,
             _validation_feedback=None):
    """One prose call; application policy and independent media do the rest."""
    actual = latest_message or question
    action_risk = policy_risk(actual)
    if action_risk == 'high_risk':
        return GeneratedReply(RESTRICTED_ANSWER, 'restricted')
    explain_media = bool(re.search(r'\b(?:diagram|image|picture|illustration|table|figure)\b', actual, re.I))
    # Preserve labels against the caller's records, including omitted media slots.
    context = prepare_context(records, references or [], vehicle_profile, maintenance_context)
    if not explain_media:
        context.sources = [s for s in context.sources if s.get('evidence_type') != 'ingestion_image_description']
    context.sources = [s for s in context.sources
                       if not unrequested_battery_procedure(s['content'], intent, actual)
                       and not (s.get('source_type') == 'manual'
                                and s.get('document_type') == 'other_reference'
                                and unrequested_fluid_procedure(s['content'], actual))]
    if intent and intent.specification:
        verified = [s for s in context.sources if s['label'].startswith('P')
                    or s.get('source_type') == 'learning_guide'
                    or (s.get('source_type') == 'manual' and s.get('source_fidelity_verified')
                        and s.get('document_type') in {'owners_manual', 'maintenance_booklet', 'service_manual'})]
        if diagnostics is not None:
            diagnostics['unverified_reference_exclusions'] = [s['label'] for s in context.sources if s not in verified]
        context.sources = verified
    sources = context.sources
    if diagnostics is not None:
        diagnostics.update(answer_mode='natural_prose', supplied_sources=len(sources),
            supplied_source_labels=[s['label'] for s in sources],
            evidence_chars=sum(len(s['content']) for s in sources),
            evidence_truncated=context.incomplete, omitted_source_labels=context.omitted_sources)
    if not sources:
        if diagnostics is not None:
            diagnostics['failure_kind'] = 'missing_knowledge'
        return GeneratedReply(INSUFFICIENT)
    if re.search(r'\baftermarket\b', question, re.I) and re.search(r'\b(?:torque|pressure|capacity|specification)\b', question, re.I):
        if not any(re.search(r'\baftermarket\b', s['content'], re.I) for s in sources):
            return GeneratedReply("I don't have a specification for that aftermarket component in the available references. "
                "Use the kit manufacturer's instructions or ask a qualified installer; factory values for other components do not establish it.")
    overview = professional_overview(actual)
    if overview:
        component = r'brake|pads?|rotors?' if re.search(r'\bbrake', question, re.I) else r'alternator'
        procedural = any(re.search(component, s['content'] + ' ' + s.get('title', ''), re.I)
            and re.search(r'\b(?:remov\w*|install\w*|refit\w*|reassembl\w*)\b', s['content'], re.I)
            for s in sources if not s['label'].startswith('P')
            and s.get('evidence_type') != 'ingestion_image_description')
        if not procedural:
            focused = []
            for source in sources:
                paragraphs = [part for part in re.split(r'\n\s*\n', source['content'])
                              if re.search(r'\b(?:pads?|rotors?)\b' if 'brake' in component else component, part, re.I)]
                if paragraphs:
                    focused.append({**source, 'content': '\n\n'.join(paragraphs)})
            return extracted_reply(focused, 'missing_procedure', diagnostics,
                question=question, intent=intent,
                prefix="I found warnings and inspection advice, but not evidence describing the replacement stages or why each stage matters.")
    procedure = manufacturer_procedure(question, sources, records)
    if procedure:
        # Render the complete retrieved passage, including its preparation and
        # warnings, before any optional explanatory prose. Never ask Gemma to
        # rewrite the steps. Media attachment remains independent in query.py.
        answer = "From the applicable manufacturer's manual:\n\n" + procedure['content'] + ' [' + procedure['label'] + ']'
        if diagnostics is not None:
            diagnostics.update(answer_mode='manufacturer_procedure',
                decision_reason='complete_numbered_passage_preserved', procedure_label=procedure['label'])
        if re.search(r'\b(?:what (?:does|do).{0,60}mean|meaning|unfamiliar|technical terms?|explain.{0,25}(?:term|word))\b', question, re.I):
            explanation_prompt = (ANSWER_PROMPT + '\nThe application already displays this manufacturer procedure verbatim. '
                'Explain only the unfamiliar terms asked about, briefly. Do not give, repeat, add or change procedural steps. '
                'Use only the supplied evidence and cite it.\nEVIDENCE:\n[' + procedure['label'] + '] '
                + procedure['content'] + '\nQUESTION: ' + question)
            try:
                explanation = client.generate(explanation_prompt).strip()
                reason, _ = validate_prose(explanation, [procedure])
                if not reason and not re.search(r'(?m)^\s*(?:\d+[.)]|[-*])\s+', explanation):
                    answer += '\n\n' + explanation
            except (GenerationError, TimeoutError, ValueError):
                pass  # Explanatory failure cannot erase the preserved procedure.
        return GeneratedReply(answer, 'answered', cited_labels=[procedure['label']])
    evidence = '\n\n'.join(f"[{s['label']}] {s.get('title', 'Saved records')} — "
        + source_authority(s)
        + ('; ingestion image description, not verified specifications' if s.get('evidence_type') == 'ingestion_image_description' else '')
        + '\n' + source_text(s) for s in sources)
    vehicle = scope.get('vehicle') or {}
    identity = ' '.join(str(vehicle.get(k) or '') for k in ('name', 'year', 'engine', 'variant')).strip()
    conversation = '\n'.join(m['role'] + ': ' + m['content'] for m in bounded_history(history))
    prompt = ANSWER_PROMPT + ('\nSelected vehicle: ' + identity if identity else '')
    if context.incomplete:
        prompt += '\nSome retrieved passages were omitted for size. Assess the supplied evidence for each requested part and identify any unsupported part.\n'
    if overview:
        prompt += '\nExplain professional stages and purpose only, without dismantling or operational repair instructions.\n'
    prompt += '\nEVIDENCE:\n' + evidence
    if conversation:
        prompt += '\n\nCONVERSATION (not evidence):\n' + conversation
    prompt += '\n\nQUESTION: ' + question
    try:
        text = client.generate(prompt).strip()
    except (GenerationError, TimeoutError, ValueError):
        if diagnostics is not None:
            diagnostics['failure_kind'] = 'generation_failure'
        return extracted_reply(sources, 'generation_unavailable', diagnostics, question=question, intent=intent)
    text = re.sub(r'^```(?:markdown|text)?\s*|\s*```$', '', text).strip()
    text = clean_prose_artifact(text, sources)
    # Accept standard grouped citations; keep their positions and readable prose.
    text = re.sub(r'\[(S\d+(?:\s*,\s*S\d+)*)\]',
        lambda m: ' '.join('[' + label.strip() + ']' for label in m[1].split(',')), text)
    text = repair_table_citations(text, sources)
    reason, cited = validate_prose(text, sources, question=question,
                                 specification=bool(intent and intent.specification))
    if unsupported_vehicle_configuration(text, question, scope):
        reason = 'unverified_vehicle_configuration'
    if overview and operational_overview(text):
        reason = 'unsafe_overview'
    if unrequested_battery_procedure(text, intent, actual):
        reason = 'unrequested_battery_procedure'
    if unrequested_fluid_procedure(text, actual):
        reason = 'unrequested_fluid_procedure'
    if puncture_repair_request(question) and spare_change_steps(text):
        reason = 'task_substitution'
    if reason:
        if diagnostics is not None:
            diagnostics['failure_kind'] = 'validation_failure'
        return extracted_reply(sources, reason, diagnostics, question=question, intent=intent)
    if diagnostics is not None:
        diagnostics['decision_reason'] = 'answered'
    return GeneratedReply(text, 'answered', cited_labels=cited,
        guide_labels=[s['label'] for s in sources if s['label'] in cited and s.get('source_type') == 'learning_guide'])
