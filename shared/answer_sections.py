"""Optional answer layout can arrange validated text and authorised originals only."""
import re


def validated_sections(answer, sections, attachments):
    """Fall back to plain text if layout changes the answer; drop unavailable media."""
    if not isinstance(sections, list) or not 0 < len(sections) <= 16:
        return []
    if any(not isinstance(section, dict) or not isinstance(section.get('text'), str)
           or not section['text'].strip()
           or not set(section).issubset({'text', 'reference_labels'}) for section in sections):
        return []
    if '\n\n'.join(section['text'] for section in sections) != answer:
        return []
    allowed = {item.get('reference_label') for item in attachments
               if isinstance(item, dict) and isinstance(item.get('reference_label'), str)}
    used = set()
    result = []
    for section in sections:
        references = section.get('reference_labels', [])
        references = references if isinstance(references, list) else []
        selected = []
        for label in references[:5]:
            if (isinstance(label, str) and re.fullmatch(r'V[1-9]\d*', label)
                    and label in allowed and label not in used):
                selected.append(label)
                used.add(label)
        result.append({'text': section['text'], 'reference_labels': selected})
    return result
