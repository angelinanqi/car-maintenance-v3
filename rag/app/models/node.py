from __future__ import annotations
from dataclasses import dataclass, field
from rag.app.models.metadata import Metadata


@dataclass
class Node:
    metadata: Metadata = field(default_factory=Metadata)

    children: list["Node"] = field(default_factory=list)

    def add_child(self, child: "Node") -> None:
        self.children.append(child)

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "metadata": self.metadata.to_dict(),
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class Document(Node):
    title: str = ""

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["title"] = self.title

        return data


@dataclass
class Section(Node):
    title: str = ""
    level: int = 1

    def to_dict(self) -> dict:
        data = super().to_dict()

        data["title"] = self.title
        data["level"] = self.level

        return data


@dataclass
class Paragraph(Node):
    text: str = ""

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["text"] = self.text

        return data


@dataclass
class Image(Node):
    src: str = ""
    alt_text: str = ""
    caption: str = ""

    def to_dict(self) -> dict:
        data = super().to_dict()

        data["src"] = self.src
        data["alt_text"] = self.alt_text
        data["caption"] = self.caption

        return data


@dataclass
class Table(Node):
    pass


@dataclass
class Row(Node):
    pass


@dataclass
class Cell(Node):
    rowspan: int = 1
    colspan: int = 1

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(rowspan=self.rowspan, colspan=self.colspan)
        return data


@dataclass
class List(Node):
    ordered: bool = False
    start: int = 1

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["ordered"] = self.ordered
        data["start"] = self.start

        return data


@dataclass
class ListItem(Node):
    pass
