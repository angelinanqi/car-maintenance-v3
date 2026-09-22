import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from rag.app.models.node import Document, Paragraph, Cell, ListItem, Section, Node
from rag.app.normalization.converters import (
    build_metadata,
    convert_node,
)


def assign_node_ids(document: Document) -> None:
    namespace = uuid5(
        NAMESPACE_URL, f"vehicle-manual:{document.metadata.document_name}"
    )

    def visit(node: Node, path: str, parent_id=None) -> None:
        node.metadata.id = uuid5(namespace, f"{path}:{type(node).__name__}")
        node.metadata.parent_id = parent_id
        for index, child in enumerate(node.children):
            visit(child, f"{path}/{index}", node.metadata.id)

    visit(document, "0")


class SemanticBuilder:
    def build(
        self,
        html_tree: dict,
        document_name: str,
    ) -> Document:

        document = convert_node(
            html_tree,
            document_name,
        )

        if not isinstance(document, Document):
            raise ValueError("Root HTML node must be a document.")

        document.title = document_name

        self._build_children(
            html_tree,
            document,
            document_name,
        )

        assign_node_ids(document)
        return document

    def _build_children(
        self,
        html_node: dict,
        semantic_parent,
        document_name: str,
    ) -> None:

        if "content" in html_node:
            if isinstance(semantic_parent, Paragraph) and html_node.get("tag") == "p":
                semantic_parent.text = ""
            children = html_node.get("children", [])
            visited = set()
            for part in html_node["content"]:
                if isinstance(part, str):
                    if isinstance(semantic_parent, Section) and html_node.get(
                        "tag"
                    ) in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                        continue
                    if not part.strip():
                        continue
                    if (
                        isinstance(semantic_parent, Paragraph)
                        and not semantic_parent.children
                    ):
                        semantic_parent.text += part
                    else:
                        semantic_parent.add_child(
                            Paragraph(
                                text=part.strip(),
                                metadata=build_metadata(html_node, document_name),
                            )
                        )
                else:
                    self._build_child(children[part], semantic_parent, document_name)
                    visited.add(part)
            for index, child in enumerate(children):
                if index not in visited:
                    self._build_child(child, semantic_parent, document_name)
            return

        self._add_direct_text(
            html_node,
            semantic_parent,
            document_name,
        )

        for child in html_node.get(
            "children",
            [],
        ):
            semantic_child = convert_node(
                child,
                document_name,
            )

            if semantic_child is not None:
                semantic_parent.add_child(semantic_child)

                self._build_children(
                    child,
                    semantic_child,
                    document_name,
                )

            else:
                self._build_children(
                    child,
                    semantic_parent,
                    document_name,
                )

    def _build_child(self, child, semantic_parent, document_name):
        semantic_child = convert_node(child, document_name)
        if semantic_child is not None:
            semantic_parent.add_child(semantic_child)
        self._build_children(child, semantic_child or semantic_parent, document_name)

    def _add_direct_text(
        self,
        html_node: dict,
        semantic_parent,
        document_name: str,
    ) -> None:

        text = html_node.get("text")

        if not text or not text.strip():
            return

        if isinstance(
            semantic_parent,
            (Paragraph, Document),
        ):
            return

        if isinstance(
            semantic_parent,
            (Cell, ListItem),
        ):
            semantic_parent.add_child(
                Paragraph(
                    text=text.strip(),
                    metadata=build_metadata(
                        html_node,
                        document_name,
                    ),
                )
            )


def normalize_file(
    input_file: Path,
    output_file: Path,
) -> None:

    with input_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        html_tree = json.load(file)

    document_name = input_file.stem.removesuffix("_html_tree")

    builder = SemanticBuilder()

    document = builder.build(
        html_tree,
        document_name,
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            document.to_dict(),
            file,
            indent=4,
            ensure_ascii=False,
        )
