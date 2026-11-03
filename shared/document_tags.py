"""Consistent document labels, including legacy case/whitespace variants."""


def clean_tag(value):
    return ' '.join(value.split())


def tag_key(value):
    return clean_tag(value).casefold()


def normalize_tags(values):
    result, seen = [], set()
    for value in values:
        label = clean_tag(value)
        key = tag_key(label)
        if key and key not in seen:
            result.append(label)
            seen.add(key)
    return result
