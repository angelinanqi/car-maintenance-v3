"""Small, validated contracts for published learning and personal activities."""
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from shared.models import InputModel


class ActivityOption(InputModel):
    id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    text: str = Field(default='', max_length=600)
    feedback: str = Field(default='', max_length=2000)


class LearningActivity(InputModel):
    prompt: str = Field(default='', max_length=2000)
    options: list[ActivityOption] = Field(min_length=2, max_length=5)
    expected_option_id: str = Field(min_length=1, max_length=80)

    @model_validator(mode='after')
    def valid_options(self):
        identities = [option.id for option in self.options]
        if len(set(identities)) != len(identities) or self.expected_option_id not in identities:
            raise ValueError('Use unique option IDs and select an existing expected answer.')
        return self


class ExplorationStep(InputModel):
    id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    section_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    example_html: str = Field(default='', max_length=20000)
    activity: LearningActivity | None = None


class Exploration(InputModel):
    version: Literal[1] = 1
    steps: list[ExplorationStep] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def unique_steps(self):
        if len({step.id for step in self.steps}) != len(self.steps):
            raise ValueError('Exploration step IDs must be unique.')
        return self


class ActivityReference(InputModel):
    kind: Literal['guide', 'plan']
    guide_id: UUID | None = None
    step_id: str | None = Field(default=None, max_length=80)
    plan_id: UUID | None = None
    revision: str = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def valid_reference(self):
        if self.kind == 'guide' and (not self.guide_id or self.plan_id):
            raise ValueError('A guide activity requires a guide ID.')
        if self.kind == 'plan' and (not self.plan_id or self.guide_id or self.step_id):
            raise ValueError('A plan activity requires a plan ID.')
        return self


class ActivityUpdate(InputModel):
    activity: ActivityReference | None = None


class ChatSessionInput(InputModel):
    session_token: str = Field(min_length=32, max_length=128)


class PlanPreviewInput(InputModel):
    vehicle_id: str = Field(min_length=1, max_length=200)


class PlanSaveInput(PlanPreviewInput):
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')


class SavedItemInput(InputModel):
    id: UUID | None = None
    kind: Literal['guide', 'explanation', 'plan', 'notes']
    title: str = Field(min_length=1, max_length=300)
    guide_id: UUID | None = None
    message_id: UUID | None = None
    plan_id: UUID | None = None
    vehicle_id: str | None = Field(default=None, max_length=200)
    text: str = Field(default='', max_length=20000)

    @model_validator(mode='after')
    def reference_for_kind(self):
        if self.id and self.kind != 'notes':
            raise ValueError('Only personal notes accept a client-generated ID.')
        references = [self.guide_id is not None, self.message_id is not None, self.plan_id is not None]
        if self.kind == 'guide' and (not self.guide_id or sum(references) != 1):
            raise ValueError('Select one published guide.')
        if self.kind == 'explanation' and (not self.message_id or sum(references) != 1):
            raise ValueError('Select one saved assistant message.')
        if self.kind == 'plan' and (not self.plan_id or sum(references) != 1):
            raise ValueError('Select one service plan.')
        if self.kind != 'notes' and self.text:
            raise ValueError('Only personal notes accept editable text.')
        if self.kind == 'notes' and (not self.text.strip() or self.guide_id or self.message_id):
            raise ValueError('Provide note text and an optional service plan.')
        return self


class NoteUpdate(InputModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=20000)
