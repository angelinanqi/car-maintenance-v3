from app.models.node import (
    Document,
    Paragraph,
    Cell,
    ListItem,
)

from app.normalization.converters import (
    build_metadata,
    convert_node,
)


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

        return document

    def _build_children(
        self,
        html_node: dict,
        semantic_parent,
        document_name: str,
    ) -> None:

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
