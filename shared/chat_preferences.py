"""Small shared output preferences; these never establish automotive facts."""
import re


def originals_only(question):
    return bool(re.search(r'\b(?:original|manual)[ -]only\b|'
                          r'\bonly\s+(?:the\s+)?original\b', question, re.I))


def videos_excluded(question):
    text = question.lower()
    return originals_only(question) or bool(re.search(
        r'\b(?:text[ -]only|original[ -]only|manual[ -]only)\b|'
        r'\bonly\s+(?:the\s+)?(?:original|manual)\b|'
        r'\b(?:no|without)\s+(?:\w+[ ,]+){0,5}videos?\b', text))


def requested_video(question):
    if videos_excluded(question):
        return False
    return bool(re.search(r'\bvideos?\b|\bwatch(?:ing)?\b|'
        r'\bsee\b.{0,35}\b(?:someone|somebody)\b.{0,25}\bdo(?:ing)?\b|'
        r'\b(?:tutorial|demonstration|clip)s?\b|'
        r'\bshow\s+me\s+doing\b|\btengok\s+orang\s+buat\b', question, re.I))


def presentation_followup(question):
    """Only recognise short format changes, never self-contained new topics."""
    text = question.strip(' \t\n.!?').lower()
    return bool(re.fullmatch(
        r'(?:please\s+)?(?:(?:can|could) you\s+)?'
        r'(?:(?:show|give|send)\s+me\s+|(?:explain|say)\s+(?:it|that)\s+)?'
        r'(?:(?:a|the|some)\s+)?'
        r'(?:videos?(?:\s+(?:form|please))?|(?:in\s+)?video form|'
        r'pictures?|diagrams?|images?|(?:in\s+)?(?:simple|simpler)\s+(?:words|terms)|'
        r'more simply|simpler|step by step)(?:\s+please)?', text))


def followup_topic(question, history):
    if not presentation_followup(question):
        return None
    return next((message['content'] for message in reversed(history or [])
                 if message.get('role') == 'user' and message.get('content')
                 and not presentation_followup(message['content'])), None)


def puncture_repair_request(question):
    """Keep a requested puncture repair separate from an explicit wheel change."""
    return bool(re.search(r'\b(?:punctur\w*|flat (?:tyre|tire)|(?:tyre|tire)\b.{0,25}\bnail|nail\b.{0,25}\b(?:tyre|tire))\b', question, re.I)
                and re.search(r'\b(?:fix\w*|repair\w*|plug\w*|patch\w*)\b', question, re.I)
                and not re.search(r'\bspare\b|\bchang\w*\b.{0,20}\b(?:wheel|tyre|tire)\b', question, re.I))


def broad_dashboard_request(question):
    return bool(re.search(r'\b(?:lights|indicators|symbols)\b', question, re.I)
                and (re.search(r'\b(?:dashboard|instrument[ -]panel)\b', question, re.I)
                     or re.search(r'\b(?:all|common|important|different)\s+(?:the\s+)?(?:warning|indicator) lights\b', question, re.I)))
