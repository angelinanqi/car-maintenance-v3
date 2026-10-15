from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

Vehicle = str
DocumentType = Literal["owners_manual", "maintenance_booklet", "service_manual", "other_reference"]
DocumentStatus = Literal["uploaded", "processing", "awaiting_index", "processed", "failed"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceAttachmentReference(BaseModel):
    """Private RAG descriptors; display content is resolved by the backend."""
    model_config = ConfigDict(extra='forbid')
    kind: Literal['table', 'image']
    element_id: str = Field(pattern=r'^(table|image)-\d{5,}$', max_length=80)
    document_id: UUID
    source_revision: UUID
    source_fidelity_verified: bool = False


class DocumentEdit(InputModel):
    name: str = Field(min_length=1)
    car_model: Vehicle = "general"
    tags: list[str] = Field(default_factory=list)
    year: str = ""
    engine: str = ""
    variant: str = ""
    vehicle_independent: bool = False
    source_fidelity_verified: bool = False
    document_type: DocumentType = "other_reference"


class Document(DocumentEdit):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    original_filename: str
    source_type: Literal["pdf", "md"]
    storage_path: str
    size_bytes: int
    status: DocumentStatus
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None = None
    processed_at: datetime | None = None
    chunk_count: int = 0
    mobile_visible: bool = False
    source_revision: UUID
    extraction_storage_path: str | None = None
    extraction_completed_at: datetime | None = None
    indexed_revision: UUID | None = None
    indexed_at: datetime | None = None
    published: bool = False
    replacement_for_id: UUID | None = None
    superseded_by_id: UUID | None = None


class Manual(BaseModel):
    id: UUID
    name: str
    car_model: Vehicle
    source_type: Literal["pdf", "md"]
    size_bytes: int
    updated_at: datetime


class ProcessBatch(InputModel):
    ids: list[UUID] = Field(min_length=1)
    force: bool = False


class CategoryInput(InputModel):
    name: str = Field(min_length=1)
    description: str = ""
    display_order: int = Field(default=0, ge=0)
    published: bool = True


class Category(CategoryInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_at: datetime
    updated_at: datetime


class GuideInput(InputModel):
    title: str = Field(min_length=1)
    category_id: UUID | None = None
    content: str = "<p></p>"
    status: Literal["draft", "published"] = "draft"
    description: str = ""
    reading_minutes: int | None = Field(default=None, gt=0)
    related_lesson_ids: list[UUID] = Field(default_factory=list)
    maintenance_item_ids: list[UUID] = Field(default_factory=list)


class Guide(GuideInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class Step(InputModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    imageUrl: str = ""

    @field_validator("imageUrl")
    @classmethod
    def image_url(cls, value):
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Image URL must use http or https")
        return value


class PlaybookInput(InputModel):
    title: str = Field(min_length=1)
    steps: list[Step] = Field(default_factory=list)
    scenario_key: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    source: str = ""
    status: Literal["draft"] | None = None
    category: str = ""
    description: str = ""
    safety_warnings: str = ""

    @field_validator("steps")
    @classmethod
    def unique_steps(cls, value):
        if len({step.id for step in value}) != len(value):
            raise ValueError("Step IDs must be unique")
        return value


class Playbook(PlaybookInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_at: datetime
    updated_at: datetime
    status: Literal["draft", "published"] = "draft"
    reviewed_at: datetime | None = None


class ReviewConfirmation(InputModel):
    confirm_review: Literal[True]


class ContactInput(InputModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=3, pattern=r"^[+\d\s().-]+$")

    @field_validator("phone")
    @classmethod
    def phone_digits(cls, value):
        if sum(character.isdigit() for character in value) < 3:
            raise ValueError("Phone number must contain at least three digits")
        return value


class Contact(ContactInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_at: datetime
    updated_at: datetime


class DocumentPatch(InputModel):
    name: str | None = Field(default=None, min_length=1)
    car_model: Vehicle | None = None
    tags: list[str] | None = None
    mobile_visible: bool | None = None
    year: str | None = None
    engine: str | None = None
    variant: str | None = None
    vehicle_independent: bool | None = None
    source_fidelity_verified: bool | None = None
    document_type: DocumentType | None = None
    published: Literal[False] | None = None

    @field_validator("*")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class GuidePatch(InputModel):
    title: str | None = Field(default=None, min_length=1)
    category_id: UUID | None = None
    content: str | None = None
    status: Literal["draft", "published"] | None = None
    description: str | None = None
    reading_minutes: int | None = Field(default=None, gt=0)
    related_lesson_ids: list[UUID] | None = None
    maintenance_item_ids: list[UUID] | None = None

    @field_validator("title", "content", "status", "description", "related_lesson_ids", "maintenance_item_ids")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class GuideImage(BaseModel):
    id: UUID
    guide_id: UUID
    storage_path: str
    url: str
    created_at: datetime


class ProcessResult(BaseModel):
    id: UUID
    status: DocumentStatus | None = None
    queued: bool = False
    error: str | None = None


class DocumentCounts(BaseModel):
    total: int = 0
    uploaded: int = 0
    processing: int = 0
    awaiting_index: int = 0
    processed: int = 0
    failed: int = 0


class GuideCounts(BaseModel):
    total: int = 0
    draft: int = 0
    published: int = 0


class Dashboard(BaseModel):
    documents: DocumentCounts
    guides: GuideCounts
    playbooks: int
    steps: int
    contacts: int
