from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class ChunkMetadata:
    document_name: str

    node_id: UUID
    parent_id: UUID | None

    node_type: str

    section_path: list[str]

    source_tag: str
    source_depth: int
    source_position: int

    src: str | None = None


@dataclass
class Chunk:
    text: str
    metadata: ChunkMetadata
