"""Text and source references for guide and reviewed emergency media."""
from typing import Literal
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator
from shared.models import InputModel


class TranscriptSegment(InputModel):
    start_seconds: int = Field(ge=0, le=86400)
    text: str = Field(min_length=1, max_length=4000)


class ContentMedia(InputModel):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal['image', 'video']
    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=4000)
    vehicle_context: str = Field(default='', max_length=500)
    source_reference: str = Field(default='', max_length=2000)
    section_id: str | None = Field(default=None, min_length=1, max_length=80)
    reviewed: bool = False
    start_seconds: int = Field(default=0, ge=0, le=86400)
    transcript: list[TranscriptSegment] = Field(default_factory=list, max_length=100)
    asset_id: UUID | None = None
    sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    size_bytes: int | None = Field(default=None, gt=0)
    mime_type: str | None = Field(default=None, max_length=100)

    @field_validator('url')
    @classmethod
    def durable_url(cls, value):
        try:
            parsed = urlsplit(value)
            valid = (parsed.scheme in {'http', 'https'} and parsed.hostname
                     and not parsed.username and not parsed.password
                     and not any(c.isspace() or ord(c) < 32 for c in value))
            parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('Use a complete http(s) media URL without credentials.')
        return value

    @model_validator(mode='after')
    def valid_media(self):
        if self.kind == 'image' and (self.transcript or self.start_seconds):
            raise ValueError('Only videos accept transcripts and timestamps.')
        starts = [segment.start_seconds for segment in self.transcript]
        if starts != sorted(set(starts)):
            raise ValueError('Transcript timestamps must be unique and increasing.')
        if self.reviewed and not self.description:
            raise ValueError('Add a description before marking media reviewed.')
        return self


def unique_media(items):
    if len({item.id for item in items}) != len(items):
        raise ValueError('Media IDs must be unique.')
    return items


def timestamp_url(url, seconds):
    """YouTube uses a query parameter; ordinary video files use a media fragment."""
    parsed = urlsplit(url)
    if not seconds:
        return url
    if parsed.hostname in {'youtu.be', 'youtube.com', 'www.youtube.com', 'm.youtube.com',
                           'youtube-nocookie.com', 'www.youtube-nocookie.com'}:
        query = dict(parse_qsl(parsed.query))
        query.pop('start', None)
        query.pop('t', None)
        if parsed.path.startswith('/embed/'):
            query['start'] = str(seconds)
        else:
            query['t'] = f'{seconds}s'
        return urlunsplit(parsed._replace(query=urlencode(query), fragment=''))
    return urlunsplit(parsed._replace(fragment=f't={seconds}'))
