from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID
import json
from pathlib import Path


@dataclass
class DocumentNode:
    id: UUID
    document_name: str
    doctype: str
    parent_id: UUID | None
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
    rowspan: int = 1
    colspan: int = 1
    children: list[DocumentNode] = field(default_factory=list)

    @classmethod
    def from_tree_dict(cls, data: dict) -> DocumentNode:
        """
        load normalized tree without creating IDs or changing child order.
        Ids must have been persisted by normalization.
        """
        seen: set[UUID] = set()

        def load(
            item: dict, parent_id: UUID | None, document_name: str
        ) -> DocumentNode:
            metadata = item["metadata"]
            if not metadata.get("id"):
                raise ValueError(
                    "Tree has no persisted node IDs. Reprocess the document through the indexing worker."
                )
            node_id = UUID(str(metadata["id"]))
            if node_id in seen:
                raise ValueError(f"Duplicate node ID: {node_id}")
            seen.add(node_id)

            stored_parent = metadata.get("parent_id")
            stored_parent = UUID(str(stored_parent)) if stored_parent else None
            if stored_parent != parent_id:
                raise ValueError(
                    f"Parent ID does not match tree structure for node {node_id}"
                )

            name = metadata.get("document_name") or item.get("document_name")
            if not name or name != document_name:
                raise ValueError(f"Inconsistent document name for node {node_id}")
            children = item.get("children", [])
            if not isinstance(children, list):
                raise ValueError(f"Invalid children for node {node_id}")

            node = cls(
                id=node_id,
                document_name=name,
                doctype=item["type"],
                parent_id=stored_parent,
                source_tag=metadata["source_tag"],
                source_depth=metadata["source_depth"],
                source_position=metadata["source_position"],
                title=item.get("title"),
                level=item.get("level"),
                text=item.get("text"),
                src=item.get("src"),
                alt=item.get("alt_text", item.get("alt")),
                caption=item.get("caption"),
                ordered=item.get("ordered"),
                rowspan=item.get("rowspan", 1),
                colspan=item.get("colspan", 1),
            )
            node.children = [load(child, node_id, document_name) for child in children]
            return node

        name = data.get("metadata", {}).get("document_name") or data.get(
            "document_name"
        )
        if data.get("type") != "Document" or not name:
            raise ValueError("Expected a Document root with a document name.")
        return load(data, None, name)


def load_document(
    path: Path,
) -> DocumentNode:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return DocumentNode.from_tree_dict(data)
