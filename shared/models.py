"""Validated data exchanged between the backend and private RAG service."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MechanicQuestion(InputModel):
    question: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=300)


class MechanicQuestionDraft(InputModel):
    concern_summary: str = Field(min_length=1, max_length=600)
    questions: list[MechanicQuestion] = Field(min_length=3, max_length=5)


class PersonalVehicleProfile(InputModel):
    """Private, database-loaded context; never accepted from a mobile client."""
    vehicle_id: str = Field(min_length=1, max_length=200)
    catalogue_id: UUID
    name: str = Field(max_length=200)
    plate_number: str = Field(max_length=40)
    mileage_km: int = Field(ge=0, le=2147483647)
    catalogue_name: str
    manufacturer: str | None = None
    model: str | None = None
    year: str
    engine: str
    variant: str
    powertrain: Literal['petrol', 'diesel']
    updated_at: datetime


class SavedMaintenanceService(InputModel):
    title: str
    date: datetime
    mileage_km: int = Field(ge=0)


class MaintenanceStatus(InputModel):
    label: str
    nextKm: int | None = None
    remainingKm: int | None = None
    nextDate: date | None = None


class MaintenanceTaskSummary(InputModel):
    task_id: str
    title: str
    category: str
    action: Literal['inspect', 'replace', 'service']
    schedule_source: Literal['none', 'custom', 'manufacturer']
    status: MaintenanceStatus
    latest_service: SavedMaintenanceService | None = None


class PersonalMaintenanceContext(InputModel):
    """Private server-loaded evidence; never part of the public chat input."""
    vehicle_id: str
    catalogue_id: UUID
    as_of: date
    total_tasks: int = Field(ge=0)
    tasks: list[MaintenanceTaskSummary] = Field(default_factory=list, max_length=50)
    total_standalone_services: int = Field(ge=0)
    standalone_services: list[SavedMaintenanceService] = Field(default_factory=list, max_length=50)
    service_plan: dict | None = None


class SourceAttachmentReference(BaseModel):
    """Private RAG descriptors; display content is resolved by the backend."""
    model_config = ConfigDict(extra='forbid')
    kind: Literal['table', 'image']
    element_id: str = Field(pattern=r'^(table|image)-\d{5,}$', max_length=80)
    document_id: UUID
    source_revision: UUID
    source_fidelity_verified: bool = False
    reference_label: str | None = Field(default=None, pattern=r'^V[1-9]\d*$', max_length=20)
