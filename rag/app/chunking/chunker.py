from __future__ import annotations
from shared.observability import observed
from pathlib import Path
import json
from rag.app.models.document_tree import DocumentNode
from rag.app.models.chunk import Chunk, ChunkMetadata

from rag.config.settings import CHUNK_SIZE


def build_section_path(
    node: DocumentNode,
    section_path: list[str],
) -> list[str]:
    current_path = section_path.copy()

    if node.doctype == "Section" and node.title and node.title.strip():
        current_path.append(node.title.strip())

    return current_path


def collect_text(
    node: DocumentNode,
) -> str:
    """
    recursively collect text from a node. Used for lists and cells where meaningful text may be stored in descendants.
    """

    parts: list[str] = [node.text.strip()] if node.text and node.text.strip() else []

    for child in node.children:
        child_text = collect_text(child)

        if child_text:
            parts.append(child_text)

    return " ".join(parts)


def format_image_reference(
    node: DocumentNode,
) -> str:
    """
    Represent an image inside the surrounding semantic chunk rather than creating a standalone meaningless embedding
    """

    parts: list[str] = []

    if node.caption and node.caption.strip():
        parts.append(f"Caption: {node.caption.strip()}")

    if node.alt and node.alt.strip():
        parts.append(f"Description: {node.alt.strip()}")

    if node.src:
        parts.append(f"Image source: {node.src}")

    if not parts:
        return "[Image associated with this section.]"

    return "[Image]\n" + "\n".join(parts)


def format_list(
    node: DocumentNode,
) -> str:
    items: list[str] = []
    for index, child in enumerate(node.children, start=node.start):
        if child.doctype != "ListItem":
            continue

        marker = f"{index}. " if node.ordered else "- "
        parts = [render_content_node(part) for part in child.children]
        if child.text:
            parts.insert(0, child.text)
        text = "\n".join(part for part in parts if part.strip())
        if text:
            lines = text.splitlines()
            items.append(
                marker
                + lines[0]
                + "".join("\n" + " " * len(marker) + line for line in lines[1:])
            )

    if not items:
        return ""

    return "\n".join(items)


def render_content_node(
    node: DocumentNode,
) -> str:
    """
    Convert a semantic content node into text suitable for an LLM.
    This function does not decide chunk boundaries, only renders the node.
    """

    if node.doctype == "Paragraph":
        parts: list[str] = []

        if node.text and node.text.strip():
            parts.append(node.text.strip())

        for child in node.children:
            parts.append(render_content_node(child))

        return "\n".join(parts)

    if node.doctype == "Table":
        raise ValueError('Table reached prose chunking; classify it as a source element first')

    if node.doctype == "List":
        return format_list(node)

    if node.doctype == "Image":
        return format_image_reference(node)

    return collect_text(node)


def is_content_node(
    node: DocumentNode,
) -> bool:
    return node.doctype in {
        "Paragraph",
        "Table",
        "List",
        "Image",
    }


def collect_section_content(
    section: DocumentNode,
) -> tuple[list[str], list[DocumentNode]]:
    """
    Collect content that directly belongs to this section.
    Nested Sections are intentionally not included because each subsection gets its own semantic chunk group.
    """

    content_parts: list[str] = []
    source_nodes: list[DocumentNode] = []

    for child in section.children:
        if child.doctype == "Section":
            continue

        if not is_content_node(child):
            continue

        content = render_content_node(child)

        if not content.strip():
            continue

        content_parts.append(content.strip())
        source_nodes.append(child)

    return content_parts, source_nodes


def build_context_text(
    document_name: str,
    section_path: list[str],
    content: str,
) -> str:
    parts = [
        f"Document: {document_name}",
    ]

    if section_path:
        parts.append("Section: " + " > ".join(section_path))

    parts.append(f"Content:\n{content.strip()}")

    return "\n\n".join(parts)


def get_metadata_source(
    source_nodes: list[DocumentNode],
) -> DocumentNode:
    """
    Select the first contributing node as the primary metadata owner.
    The complete list of contributing node IDs is also stored in ChunkMetadata.
    """

    return source_nodes[0]


def collect_image_sources(node: DocumentNode) -> list[str]:
    sources = [node.src] if node.src else []
    for child in node.children:
        sources.extend(collect_image_sources(child))
    return sources


def create_chunk(
    document_name: str,
    section_path: list[str],
    content: str,
    source_nodes: list[DocumentNode],
) -> Chunk:
    primary_node = get_metadata_source(source_nodes)

    def node_ids(node):
        values = [node.id]
        for child in node.children:
            values.extend(node_ids(child))
        return values

    metadata = ChunkMetadata(
        document_name=document_name,
        node_ids=list(dict.fromkeys(identity for node in source_nodes for identity in node_ids(node))),
        parent_id=primary_node.parent_id,
        node_type=primary_node.doctype,
        section_path=section_path.copy(),
        source_tag=primary_node.source_tag,
        source_depth=primary_node.source_depth,
        source_position=primary_node.source_position,
        src=list(
            dict.fromkeys(
                src for node in source_nodes for src in collect_image_sources(node)
            )
        ),
    )

    text = build_context_text(
        document_name=document_name,
        section_path=section_path,
        content=content,
    )

    return Chunk(
        text=text,
        metadata=metadata,
        source_content=content,
    )


def split_section_content(
    content_parts: list[str],
    source_nodes: list[DocumentNode],
    chunk_size: int,
) -> list[tuple[str, list[DocumentNode]]]:
    """
    Pack complete source blocks in order, using chunk_size as a soft target.

    An oversized block stays whole. The embedder checks its actual token length;
    generation either includes it whole or reports its omission. We cannot infer
    safe internal boundaries for a paragraph or procedure from its words.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    groups: list[tuple[str, list[DocumentNode]]] = []

    current_parts: list[str] = []
    current_nodes: list[DocumentNode] = []
    current_length = 0

    for content, node in zip(
        content_parts,
        source_nodes,
    ):
        if not content.strip():
            continue

        # Complete source tables must be classified before prose chunking.
        if node.doctype == "Table":
            raise ValueError('Table reached prose chunking; classify it as a source element first')

        content_length = len(content)

        extra_length = content_length

        if current_parts:
            extra_length += 2

        if current_parts and current_length + extra_length > chunk_size:
            groups.append(
                (
                    "\n\n".join(current_parts),
                    current_nodes.copy(),
                )
            )

            current_parts = []
            current_nodes = []
            current_length = 0

        current_parts.append(content)
        current_nodes.append(node)

        current_length += (
            content_length if len(current_parts) == 1 else content_length + 2
        )

    if current_parts:
        groups.append(
            (
                "\n\n".join(current_parts),
                current_nodes.copy(),
            )
        )

    return groups


def chunk_section(
    section: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    content_parts, source_nodes = collect_section_content(section)

    if not content_parts:
        return []

    groups = split_section_content(
        content_parts=content_parts,
        source_nodes=source_nodes,
        chunk_size=CHUNK_SIZE,
    )

    chunks = []
    for index, (content, nodes) in enumerate(groups, start=1):
        chunk = create_chunk(
            document_name=document_name,
            section_path=section_path,
            content=content,
            source_nodes=nodes,
        )
        chunk.metadata.section_chunk_index = index
        chunk.metadata.section_chunk_count = len(groups)
        chunks.append(chunk)
    return chunks


def chunk_non_section_content(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    """
    Handle content outside a Section.
    This is important for unstructured documents where headings may be missing.
    """

    if not is_content_node(node):
        return []

    content = render_content_node(node)

    if not content.strip():
        return []

    groups = split_section_content([content], [node], CHUNK_SIZE)

    return [
        create_chunk(
            document_name=document_name,
            section_path=section_path,
            content=piece,
            source_nodes=nodes,
        )
        for piece, nodes in groups
    ]


def collect_chunks(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    """
    Recursively process the semantic document tree.

    Sections are semantic boundaries.
    """

    current_path = build_section_path(
        node=node,
        section_path=section_path,
    )

    chunks: list[Chunk] = []

    if node.doctype in {"Document", "Section"}:
        chunks.extend(
            chunk_section(
                section=node,
                document_name=document_name,
                section_path=current_path,
            )
        )

        # Process nested sections separately.
        for child in node.children:
            if child.doctype != "Section":
                continue

            chunks.extend(
                collect_chunks(
                    node=child,
                    document_name=document_name,
                    section_path=current_path,
                )
            )

        return chunks

    if is_content_node(node):
        chunks.extend(
            chunk_non_section_content(
                node=node,
                document_name=document_name,
                section_path=current_path,
            )
        )

        return chunks

    for child in node.children:
        chunks.extend(
            collect_chunks(
                node=child,
                document_name=document_name,
                section_path=current_path,
            )
        )

    return chunks


@observed('chunking')
def chunk_document(
    document: DocumentNode,
    document_title: str | None = None,
) -> list[Chunk]:
    chunks = collect_chunks(
        node=document,
        document_name=document.document_name,
        section_path=[],
    )
    title = document_title or document.document_name
    for chunk in chunks:
        chunk.metadata.document_title = title
        chunk.text = build_context_text(title, chunk.metadata.section_path, chunk.source_content)
    return chunks


def chunk_to_dict(
    chunk: Chunk,
) -> dict:
    return {
        "text": chunk.text,
        "retrieval_text": chunk.text,
        "source_content": chunk.source_content,
        "metadata": {
            "source_content": chunk.source_content,
            "table_data": chunk.metadata.table_data,
            "document_name": (chunk.metadata.document_name),
            "document_title": chunk.metadata.document_title,
            "section_chunk_index": chunk.metadata.section_chunk_index,
            "section_chunk_count": chunk.metadata.section_chunk_count,
            "node_ids": [str(node_id) for node_id in chunk.metadata.node_ids],
            "parent_id": (
                str(chunk.metadata.parent_id)
                if chunk.metadata.parent_id is not None
                else None
            ),
            "node_type": (chunk.metadata.node_type),
            "section_path": (chunk.metadata.section_path),
            "source_tag": (chunk.metadata.source_tag),
            "source_depth": (chunk.metadata.source_depth),
            "source_position": (chunk.metadata.source_position),
            "src": chunk.metadata.src,
        },
    }


def save_chunks(
    document_name: str,
    chunks: list[Chunk],
    output_dir: Path,
) -> None:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = output_dir / f"{document_name}.json"
    json_data = [chunk_to_dict(chunk) for chunk in chunks]

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            json_data,
            file,
            indent=2,
            ensure_ascii=False,
        )


    print(f"Chunk output saved: {json_path}")
