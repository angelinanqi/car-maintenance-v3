from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentNodeCreate(BaseModel):
    document_name: str

    doctype: str

    parent_id: UUID | None = None

    source_tag: str
    source_depth: int
    source_position: int

    title: str | None = None
    level: int | None = None
    text: str | None = None
    src: str | None = None
    alt: str | None = None
    caption: str | None = None
    ordered: bool | None = None


class DocumentNode(BaseModel):
    id: UUID

    document_name: str

    doctype: str

    parent_id: UUID | None = None

    source_tag: str
    source_depth: int
    source_position: int

    title: str | None = None
    level: int | None = None
    text: str | None = None
    src: str | None = None
    alt: str | None = None
    caption: str | None = None
    ordered: bool | None = None

    children: list["DocumentNode"] = Field(default_factory=list)
