"""Small application policy based on the requested action, not component names."""
import re


RISKS = ("normal", "caution", "high_risk", "emergency")
REPAIR = r"\b(repair|rebuild|replace|change|remove|install|service|disassemble|bypass|disable|disconnect|bleed|rewire|fix|modify|deactivate|tamper)\b|\bwork on\b"
RESTRICTED_COMPONENTS = (
    r"\b(airbags?|inflator|srs|supplemental restraint|pretensioner)\b",
    r"\b(brake|braking)\b.*\b(hydraulic|master cylinder|calipers?|lines?|hoses?|system|reservoir|fluid)\b",
    r"\b(steering rack|steering column|steering system|tie rod)\b",
    r"\b(high[- ]voltage|traction battery|hybrid battery|ev battery|orange cable)\b",
    r"\b(fuel|petrol|gasoline)\b.*\b(leak|line|pump|injector|tank|hose)\b",
)
RESTRICTED_ANSWER = (
    "This repair can cause serious injury or compromise vehicle safety. I can't provide "
    "DIY repair steps or repair-video recommendations for it. Have a qualified technician "
    "inspect and repair the system. I can help identify the component or explain its purpose."
)


def immediate_emergency(question):
    """Existing conservative fast path; repair requests require interpretation."""
    text = question.lower()
    explanation = bool(re.match(r"\s*(what (?:is|are|does)|how does|explain)\b", text))
    if not explanation and re.search(r"\b(brakes?|braking)\b.{0,45}\b(failed|fail(?:ing)?|not working|stopped working|don't work|won't work|no longer work)\b", text):
        return True
    if not explanation and re.search(r"\b(overheating|overheated|on fire|fuel leak|leaking fuel|leaking petrol|smell (?:of )?(?:fuel|petrol))\b", text):
        return True
    if not explanation and re.search(r"\bbrake pedal\b.{0,35}\b(goes? to|on|hits?) the floor\b|\b(fuel|petrol|gasoline)\b.{0,20}\bleak(?:ing)?\b", text):
        return True
    return False


def policy_risk(question):
    """Backstop over the resolved request, not excluded actions in raw history."""
    if immediate_emergency(question):
        return "emergency"
    text = question.lower()
    interval = bool(re.search(r"\b(how often|interval|schedule)\b|when.*\b(change|replace|service)\b", text))
    if not interval and re.search(REPAIR, text) and any(re.search(component, text) for component in RESTRICTED_COMPONENTS):
        return "high_risk"
    if re.search(r"\b(repair|rebuild|fix|disable|bypass)\b.*\b(brakes?|braking|steering)\b", text):
        return "high_risk"
    if re.search(r"\b(bleed|bypass|disable)\b.*\b(brakes?|braking|abs)\b", text):
        return "high_risk"
    # Level identification remains normal; handling hot fluids, lifting a car,
    # or working on brakes requires selective review of precautions.
    if re.search(r"\b(jack|lift|torque|brake pads?|brake discs?)\b", text) or (
        re.search(r"\b(change|replace|drain|remove|open)\b", text)
        and re.search(r"\b(coolant|radiator|fuel|battery)\b", text)
    ):
        return "caution"
    return "normal"


def enforce_policy(intent):
    """Produce a consistent route/risk once for all downstream consumers."""
    risks = {policy_risk(intent.question), intent.risk}
    if intent.route == "emergency" or "emergency" in risks:
        intent.route, intent.risk = "emergency", "emergency"
    elif intent.route == "restricted" or "high_risk" in risks:
        intent.route, intent.risk = "restricted", "high_risk"
    elif "caution" in risks:
        intent.risk = "caution"
    return intent


def videos_allowed(intent):
    return bool(intent and intent.route in {"rag", "rag_with_external_warning"}
                and intent.risk == "normal" and intent.instructional and not intent.specification)


def emergency_topics(text):
    """Match existing protocol catalogue topics; this does not authorize actions."""
    text = text.lower().replace('-', ' ')
    result = set()
    if re.search(r'\boverheat\w*', text):
        result.add('overheating')
    if re.search(r'\bfire\b', text):
        result.add('fire')
    if re.search(r'\b(fuel|petrol|gasoline)\b', text) and re.search(r'\b(leak\w*|smell)\b', text):
        result.add('fuel-leak')
    if re.search(r'\bbrakes?\b', text) and re.search(r'\b(fail\w*|floor|not working|stopped working|no longer work|don.t work|won.t work)\b', text):
        result.add('brake-failure')
    return result


def emergency_guidance(question):
    """General safety advice; no diagnosis or vehicle-specific manoeuvre."""
    text = question.lower()
    if "overheat" in text:
        return (
            "General safety advice: stop driving and pull over as soon as it is safe. "
            "Switch off the engine once safely stopped and arrange roadside assistance. "
            "Keep clear of hot coolant and steam; do not open the radiator or coolant cap "
            "while the engine is hot. The cause cannot be established from this message."
        )
    if re.search(r"\b(fire|fuel|petrol|gasoline)\b", text):
        return (
            "General safety advice: stop using the vehicle. If safely possible, stop and "
            "switch off the engine. Move people away from the vehicle and traffic, avoid "
            "flames or sparks, and contact emergency services if there is fire or immediate "
            "danger. Arrange professional assistance; do not attempt a fuel-system repair."
        )
    return (
        "General safety advice: this may be an immediate emergency. Focus on controlling "
        "the vehicle and reaching a safe stopping place if possible. Warn other road users "
        "if safe to do so. Once stopped, do not drive again; arrange roadside recovery. "
        "Contact local emergency services if anyone is in immediate danger. I cannot "
        "diagnose the fault or provide a repair procedure from this message."
    )
