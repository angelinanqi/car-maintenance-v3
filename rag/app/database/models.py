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

    @classmethod
    def from_tree_dict(
        cls,
        data: dict,
        parent_id=None,
    ) -> "DocumentNode":
        metadata = data.get(
            "metadata",
            {},
        )

        node = cls(
            id=metadata["id"],
            document_name=data["document_name"],
            doctype=data["type"],
            parent_id=(
                metadata.get("parent_id") if metadata.get("parent_id") else parent_id
            ),
            source_tag=metadata["source_tag"],
            source_depth=metadata["source_depth"],
            source_position=metadata["source_position"],
            title=data.get("title"),
            level=data.get("level"),
            text=data.get("text"),
            src=data.get("src"),
            alt=data.get("alt"),
            caption=data.get("caption"),
            ordered=data.get("ordered"),
            children=[],
        )

        node.children = [
            cls.from_tree_dict(
                child,
                parent_id=node.id,
            )
            for child in data.get(
                "children",
                [],
            )
        ]

        return node
