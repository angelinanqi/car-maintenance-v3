"""Contract for classifying a chat turn against the published guide catalogue."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EMERGENCY_CLASSIFICATION_TIMEOUT = 18.0
EMERGENCY_ROUTES = frozenset({'emergency', 'roadside_guidance'})


class EmergencyGuideSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    scenario_key: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=200)


class EmergencyDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')

    route: Literal['emergency', 'roadside_guidance', 'general']
    guide_id: str | None
    hazard: Literal['traffic', 'overheating', 'fire_or_fuel'] | None
