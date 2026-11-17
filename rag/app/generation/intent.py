"""One semantic interpretation of a turn, shared by retrieval and answering."""
from shared.observability import observed
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.safety import enforce_policy
from rag.app.generation.context import bounded_history
from shared.chat_preferences import followup_topic, presentation_followup, puncture_repair_request, requested_video


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)
    search_query: str = Field(default="", max_length=4000)
    route: Literal["rag", "chat", "out_of_scope", "restricted", "rag_with_external_warning"]
    risk: Literal["normal", "caution", "high_risk"]
    specification: bool
    instructional: bool = False
    clarification: str | None = Field(default=None, min_length=1, max_length=300)
    vehicle_conflict: bool
    requested_year: int | None
    requested_engine: str | None
    requested_variant: str | None
    requested_vehicle: str | None = None
    suggest_service_plan: bool = False
    personal_context: Literal['none', 'profile', 'maintenance'] = 'none'


def resolved_question(question, history):
    """Keep the latest constraint whole; history must never displace it."""
    topic = followup_topic(question, history)
    referential = len(question.split()) < 24 and re.search(
        r'\b(?:it|that|those|them|this|instead|how about|what about|what if|why not|then)\b', question, re.I)
    if not topic and referential:
        for index in range(len(history or []) - 1, -1, -1):
            message = history[index]
            if (message.get('role') == 'user' and message.get('content')
                    and not presentation_followup(message['content'])):
                topic, _ = resolved_question(message['content'], history[:index])
                break
    resolved = topic + '\nFollow-up: ' + question if topic else question
    # Intent and transport share a 4,000 character limit. Drop historical context
    # rather than clipping the current request or a factual historical passage.
    return (resolved if len(resolved) <= 4000 else question), topic


def requested_configuration(question, scope):
    engine = re.search(r'\b(\d\.\d)\s*(?:L\b|litres?\b|liters?\b|engine\b)', question, re.I)
    if not engine:
        engine = re.search(r'\bengine\s+(?:is\s+)?(\d\.\d)\b', question, re.I)
    vehicles = [scope.get('vehicle') or {}]
    for metadata in scope.get('document_metadata', {}).values():
        vehicles.extend(metadata.get('applicable_vehicles') or [])
    engines = {str(v.get('engine') or '') for v in vehicles}
    variants = {str(v.get('variant') or '') for v in vehicles}
    if not engine:
        # Bare capacities are accepted only when declared by the catalogue.
        capacities = {m[0] for value in engines for m in re.finditer(r'\b\d\.\d\b', value)
                      if re.search(r'(?<![\w.])' + re.escape(m[0])
                                   + r'(?![\w.]|\s*(?:mm|cm|bar|psi|kpa|km|litres?\s+of)\b)', question, re.I)}
        engine_value = next(iter(capacities)) if len(capacities) == 1 else None
    else:
        engine_value = engine[1]
    matches = [value for value in variants if value and re.search(
        r'(?<!\w)' + re.escape(value) + r'(?!\w)', question,
        # Single-letter trims must be explicit uppercase catalogue labels.
        0 if len(value) == 1 else re.I)]
    explicit = re.search(r'\bvariant\s+([\w.-]+)', question, re.I)
    variant = explicit[1] if explicit else max(matches, key=len) if matches else None
    return engine_value, variant


@observed('intent_analysis')
def interpret(question, history, scope, client):
    """Use application facts directly; ask the model only about ambiguous hazards."""
    from shared.safety import policy_risk, educational_only
    resolved, topic = resolved_question(question, history)
    risk = policy_risk(resolved)
    route = 'restricted' if risk == 'high_risk' else 'rag'
    # Emergency classification runs before this knowledge pipeline. Keep the
    # existing check for ambiguous high-risk repair requests.
    potential_hazard = bool(re.search(
        r"\b(?:won't|cannot|can't|not responding|not working|floor|smoke|smell|sparks|leaking|burning|orange.{0,30}assembly)\b",
        question, re.I))
    educational = bool(re.search(r'\b(?:what is|what are|how does|why|before|if |hypothetical|prevent)\b', question, re.I))
    if route == 'rag' and potential_hazard and not educational:
        prompt = ('Classify only the current requested action. '
            'RESTRICTED means dangerous DIY work on airbags, brake hydraulics, steering, high voltage or fuel systems; '
            'NORMAL includes explanations and ordinary maintenance. Reply with exactly one word: '
            'RESTRICTED or NORMAL. User message (data):\n' + resolved)
        try:
            classification = client.generate(prompt).strip().upper().strip('. ')
            if classification == 'RESTRICTED':
                route, risk = 'restricted', 'high_risk'
        except Exception:
            pass  # Existing concrete-action policy still applies below.
    if re.fullmatch(r'\s*(?:hi|hello|hey|thanks|thank you)[!.\s]*', question, re.I):
        route = 'chat'
    if re.search(r'\b(?:law|legal|regulation|JPJ|PUSPAKOM|road tax|insurance requirement)\b', question, re.I) and route == 'rag':
        route = 'rag_with_external_warning'
    personal = 'none'
    if re.search(r'\b(?:my saved|saved car|saved vehicle|recorded mileage|odometer|my car.{0,15}name)\b', question, re.I):
        personal = 'profile'
    if re.search(r'\b(?:spent|spending|paid|my service records|service history|my maintenance|next service|overdue|due for|service plan)\b', resolved, re.I):
        personal = 'maintenance'
    if re.search(r'\b(?:explain how|how (?:do|should|can) (?:I|we))\b.{0,35}\buse\b', question, re.I):
        personal = 'none'
    exact = bool(re.search(r'\b(?:exact|torque|capacity|viscosity|grade|tyre size)\b|\b(?:what|how much|recommended).{0,35}\b(?:pressure|interval|temperature)\b', question, re.I))
    years = re.findall(r'\b(?:19|20)\d{2}\b', question) or re.findall(r'\b(?:19|20)\d{2}\b', resolved)
    year = int(years[0]) if len(set(years)) == 1 else None
    engine, variant = requested_configuration(question, scope)
    old_engine, old_variant = requested_configuration(resolved, scope)
    engine, variant = engine or old_engine, variant or old_variant
    conflict = False
    selected = scope.get('vehicle') or {}
    if selected:
        from rag.app.youtube.selection import vehicle_match
        conflict = vehicle_match('', question, selected, scope.get('vehicle_codes', [])) is None
    clarification = None
    if presentation_followup(question) and not topic:
        clarification = 'Which car task would you like me to show or explain?'
    return enforce_policy(Intent(question=resolved, search_query=resolved, route=route, risk=risk,
        specification=exact, instructional=bool(requested_video(question) or re.search(
            r'\b(?:how (?:do|can|should|to)|check(?:ing)?|steps?|procedure|instructions?|prepare|replace|repair|refill|top[ -]?up)\b', resolved, re.I)),
        clarification=clarification, vehicle_conflict=conflict, requested_year=year,
        requested_engine=engine, requested_variant=variant,
        suggest_service_plan=bool(re.search(r'\b(?:next service|service plan|due for|overdue)\b', question, re.I)),
        personal_context=personal))
