from rag.app.models.metadata import Metadata
from rag.app.models.node import (
    Node,
    Document,
    Section,
    Paragraph,
    Image,
    Table,
    Row,
    Cell,
    List,
    ListItem,
)


def build_metadata(
    html_node: dict,
    document_name: str,
) -> Metadata:
    return Metadata(
        document_name=document_name,
        source_tag=html_node.get("tag", ""),
        source_depth=html_node.get("depth", 0),
        source_position=html_node.get("position", 0),
    )


def convert_node(
    html_node: dict,
    document_name: str,
) -> Node | None:
    tag = html_node.get("tag", "").lower()

    metadata = build_metadata(
        html_node,
        document_name,
    )

    if tag == "document":
        return Document(
            metadata=metadata,
        )

    if tag in {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }:
        return Section(
            title=(html_node.get("text") or "").strip(),
            level=int(tag[1]),
            metadata=metadata,
        )

    if tag == "p":
        return Paragraph(
            text=(html_node.get("text") or "").strip(),
            metadata=metadata,
        )

    if tag == "img":
        attributes = html_node.get(
            "attributes",
            {},
        )

        return Image(
            src=attributes.get("src", ""),
            alt_text=attributes.get("alt", ""),
            metadata=metadata,
        )

    if tag == "table":
        return Table(
            metadata=metadata,
        )

    if tag == "tr":
        return Row(
            metadata=metadata,
        )

    if tag in {"td", "th"}:
        attributes = html_node.get("attributes", {})
        rowspan = int(attributes.get("rowspan", 1))
        colspan = int(attributes.get("colspan", 1))
        if rowspan < 1 or colspan < 1:
            raise ValueError("Table cell spans must be positive")
        return Cell(
            metadata=metadata,
            rowspan=rowspan,
            colspan=colspan,
        )

    if tag == "ul":
        return List(
            ordered=False,
            metadata=metadata,
        )

    if tag == "ol":
        return List(
            ordered=True,
            start=int(html_node.get("attributes", {}).get("start", 1)),
            metadata=metadata,
        )

    if tag == "li":
        return ListItem(
            metadata=metadata,
        )

    return None
