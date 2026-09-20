from dataclasses import dataclass
from uuid import UUID


@dataclass
class Metadata:
    document_name: str = ""
    source_tag: str = ""
    source_depth: int = 0
    source_position: int = 0
    id: UUID | None = None
    parent_id: UUID | None = None

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id is not None else None,
            "parent_id": str(self.parent_id) if self.parent_id is not None else None,
            "document_name": self.document_name,
            "source_tag": self.source_tag,
            "source_depth": self.source_depth,
            "source_position": self.source_position,
        }
