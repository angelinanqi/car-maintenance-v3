from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HTMLNode:
    document_name: str
    tag: str
    attributes: dict = field(default_factory=dict)
    text: Optional[str] = None
    children: list["HTMLNode"] = field(default_factory=list)
    parent: Optional["HTMLNode"] = None
    depth: int = 0
    position: int = 0

    def add_child(self, child: "HTMLNode"):
        child.parent = self
        child.depth = self.depth + 1
        self.children.append(child)

    def to_dict(self):
        return {
            "document_name": self.document_name,
            "tag": self.tag,
            "attributes": self.attributes,
            "depth": self.depth,
            "position": self.position,
            "text": self.text,
            "children": [child.to_dict() for child in self.children],
        }
