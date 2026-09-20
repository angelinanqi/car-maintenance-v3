from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from rag.app.models.metadata import Metadata


@dataclass
class Node:
    metadata: Metadata = field(default_factory=Metadata)

    parent: Optional["Node"] = field(
        default=None,
        repr=False,
    )

    children: list["Node"] = field(default_factory=list)

    def add_child(self, child: "Node") -> None:
        child.parent = self
        self.children.append(child)

    def traverse(self):
        yield self

        for child in self.children:
            yield from child.traverse()

    def get_text(self) -> str:
        texts = []

        for child in self.children:
            text = child.get_text().strip()

            if text:
                texts.append(text)

        return "\n".join(texts)

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "metadata": self.metadata.to_dict(),
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class Document(Node):
    title: str = ""

    def get_text(self) -> str:
        texts = []

        for child in self.children:
            text = child.get_text().strip()

            if text:
                texts.append(text)

        return "\n\n".join(texts)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["title"] = self.title

        return data


@dataclass
class Section(Node):
    title: str = ""
    level: int = 1

    def get_text(self) -> str:
        parts = []

        if self.title:
            parts.append(self.title)

        for child in self.children:
            text = child.get_text().strip()

            if text:
                parts.append(text)

        return "\n\n".join(parts)

    def to_dict(self) -> dict:
        data = super().to_dict()

        data["title"] = self.title
        data["level"] = self.level

        return data


@dataclass
class Paragraph(Node):
    text: str = ""

    def get_text(self) -> str:
        parts = []

        if self.text.strip():
            parts.append(self.text.strip())

        for child in self.children:
            text = child.get_text().strip()

            if text:
                parts.append(text)

        return "\n".join(parts)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["text"] = self.text

        return data


@dataclass
class Image(Node):
    src: str = ""
    alt_text: str = ""
    caption: str = ""

    def get_text(self) -> str:
        if self.caption:
            return self.caption

        if self.alt_text:
            return self.alt_text

        return ""

    def to_dict(self) -> dict:
        data = super().to_dict()

        data["src"] = self.src
        data["alt_text"] = self.alt_text
        data["caption"] = self.caption

        return data


@dataclass
class Table(Node):
    def get_text(self) -> str:
        texts = []

        for child in self.children:
            text = child.get_text().strip()

            if text:
                texts.append(text)

        return "\n".join(texts)


@dataclass
class Row(Node):
    def get_text(self) -> str:
        cells = []

        for child in self.children:
            text = child.get_text()
            text = text.replace("\n", " ").strip()

            if text:
                cells.append(text)

        return " | ".join(cells)


@dataclass
class Cell(Node):
    def get_text(self) -> str:
        texts = []

        for child in self.children:
            text = child.get_text().strip()

            if text:
                texts.append(text)

        return "\n".join(texts)


@dataclass
class List(Node):
    ordered: bool = False

    def get_text(self) -> str:
        lines = []

        for index, child in enumerate(
            self.children,
            start=1,
        ):
            text = child.get_text().strip()

            if not text:
                continue

            if self.ordered:
                lines.append(f"{index}. {text}")
            else:
                lines.append(f"- {text}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["ordered"] = self.ordered

        return data


@dataclass
class ListItem(Node):
    def get_text(self) -> str:
        texts = []

        for child in self.children:
            text = child.get_text().strip()

            if text:
                texts.append(text)

        return "\n".join(texts)
