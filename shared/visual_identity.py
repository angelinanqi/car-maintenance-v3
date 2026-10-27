"""Keep reviewed image identity separate from nearby text and generated aids."""
from pydantic import BaseModel, ConfigDict, Field


class VisualIdentity(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=1600)
    uncertainty: str = Field(default='', max_length=800)


def image_identified(element):
    review = element.get('identity_review') or {}
    return (element.get('association_verified') is True or
            bool(review.get('reviewed_by') and element.get('asset_sha256')
                 and review.get('asset_sha256') == element['asset_sha256']
                 and review.get('title')))


def source_image_available(element):
    """Authenticity/availability is independent of semantic identity review."""
    if element.get('asset_available') is False:
        return False
    return bool((element.get('asset_available') is True and element.get('asset_path')
                 and element.get('asset_sha256')) or image_identified(element))


def image_identity(element):
    review = element.get('identity_review')
    if review:
        return review
    generated = element.get('generated_identity') or {}
    if (element.get('asset_sha256') and generated.get('asset_sha256') == element['asset_sha256']
            and generated.get('title')):
        return generated
    return {}


def apply_reviews(manifest, reviews):
    """Reviews are keyed by original asset hash, never a transferable ordinal."""
    for element in manifest['elements']:
        identity = element.get('asset_sha256')
        review = reviews.get(identity)
        if element['kind'] != 'image' or not review:
            continue
        details = VisualIdentity.model_validate({key: review.get(key, '') for key in
                                                ('title', 'description', 'uncertainty')})
        if not review.get('reviewed_by') or not review.get('reviewed_at'):
            raise ValueError('A visual review requires reviewer and timestamp')
        element['identity_review'] = {**details.model_dump(), 'asset_sha256': identity,
            'reviewed_by': review['reviewed_by'], 'reviewed_at': review['reviewed_at']}


def image_search_text(element):
    """Own identity precedes inherited context; generated content stays attributed."""
    parts = []
    review = element.get('identity_review')
    if review:
        # Nearby prose already has its own search records. It must not undo a
        # checked image identity (for example, removal beside installation text).
        parts.extend([review['title'], review['description'], review['uncertainty']])
        if element.get('caption_origin') in {'source_alt', 'source_caption', 'extractor_caption'}:
            parts.append(element.get('caption', ''))
        return '\n'.join(parts)
    generated = image_identity(element)
    if generated:
        parts.extend(['Generated identification (unverified): ' + generated['title'],
                      generated['description'], 'Uncertainty: ' + generated['uncertainty']])
        if element.get('caption_origin') in {'source_alt', 'source_caption', 'extractor_caption'}:
            parts.append(element.get('caption', ''))
        return '\n'.join(parts)
    parts.extend(['Source caption: ' + element.get('caption', ''),
                  'Section (inherited): ' + ' > '.join(element.get('section_path', [])),
                  'Nearby text (association unverified): ' + '\n'.join(element.get('context', []))])
    return '\n'.join(parts)
