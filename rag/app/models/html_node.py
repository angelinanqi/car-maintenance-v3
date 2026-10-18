from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HTMLNode:
    document_name: str
    tag: str
    attributes: dict = field(default_factory=dict)
    text: Optional[str] = None
    children: list["HTMLNode"] = field(default_factory=list)
    depth: int = 0
    position: int = 0
    content: list = field(default_factory=list)

    def add_child(self, child: "HTMLNode"):
        child.depth = self.depth + 1
        self.children.append(child)

    def set_depth(self, depth: int = 0):
        self.depth = depth
        for child in self.children:
            child.set_depth(depth + 1)

    def to_dict(self):
        return {
            "document_name": self.document_name,
            "tag": self.tag,
            "attributes": self.attributes,
            "depth": self.depth,
            "position": self.position,
            "text": self.text,
            "content": self.content,
            "children": [child.to_dict() for child in self.children],
        }
