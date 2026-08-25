from __future__ import annotations
import json
from pathlib import Path
from app.database.models import DocumentNode
from app.models.chunk import Chunk, ChunkMetadata
from app.chunking.table_formatter import format_table

CHUNK_SIZE = 1000


def split_text(
    text: str,
    chunk_size: int,
) -> list[str]:
    text = " ".join(text.split())

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    words = text.split()
    chunks: list[str] = []

    current_words: list[str] = []
    current_length = 0

    for word in words:
        extra_length = len(word)

        if current_words:
            extra_length += 1

        if current_length + extra_length > chunk_size:
            chunks.append(" ".join(current_words))

            current_words = [word]
            current_length = len(word)

        else:
            current_words.append(word)
            current_length += extra_length

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def build_section_path(
    node: DocumentNode,
    section_path: list[str],
) -> list[str]:
    current_path = section_path.copy()

    if node.doctype == "Section" and node.title and node.title.strip():
        current_path.append(node.title.strip())

    return current_path


def build_context_text(
    document_name: str,
    section_path: list[str],
    content: str,
    content_type: str,
) -> str:
    parts = [
        f"Document: {document_name}",
    ]

    if section_path:
        parts.append("Section: " + " > ".join(section_path))

    if content_type:
        parts.append(f"Content type: {content_type}")

    parts.append(f"Content:\n{content.strip()}")

    return "\n\n".join(parts)


def create_chunk(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
    content: str,
    content_type: str,
) -> Chunk:
    text = build_context_text(
        document_name=document_name,
        section_path=section_path,
        content=content,
        content_type=content_type,
    )

    metadata = ChunkMetadata(
        document_name=document_name,
        node_id=node.id,
        parent_id=node.parent_id,
        node_type=node.doctype,
        section_path=section_path.copy(),
        source_tag=node.source_tag,
        source_depth=node.source_depth,
        source_position=node.source_position,
        src=node.src,
    )

    return Chunk(
        text=text,
        metadata=metadata,
    )


def chunk_paragraph(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    if not node.text or not node.text.strip():
        return []

    text_parts = split_text(
        node.text,
        CHUNK_SIZE,
    )

    return [
        create_chunk(
            node=node,
            document_name=document_name,
            section_path=section_path,
            content=text,
            content_type="paragraph",
        )
        for text in text_parts
    ]


def chunk_table(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    table_text = format_table(node)

    if not table_text.strip():
        return []

    return [
        create_chunk(
            node=node,
            document_name=document_name,
            section_path=section_path,
            content=table_text,
            content_type="table",
        )
    ]


def chunk_image(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    parts: list[str] = []

    if node.caption and node.caption.strip():
        parts.append(f"Caption: {node.caption.strip()}")

    if node.alt and node.alt.strip():
        parts.append(f"Description: {node.alt.strip()}")

    if not parts:
        return []

    return [
        create_chunk(
            node=node,
            document_name=document_name,
            section_path=section_path,
            content="\n".join(parts),
            content_type="image",
        )
    ]


def chunk_list(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    items: list[str] = []

    for child in node.children:
        if child.doctype != "ListItem":
            continue

        if child.text and child.text.strip():
            items.append(child.text.strip())
            continue

        child_text = collect_node_text(child)

        if child_text:
            items.append(child_text)

    if not items:
        return []

    list_text = "\n".join(
        f"{index}. {item}"
        for index, item in enumerate(
            items,
            start=1,
        )
    )

    return [
        create_chunk(
            node=node,
            document_name=document_name,
            section_path=section_path,
            content=list_text,
            content_type="list",
        )
    ]


def collect_node_text(
    node: DocumentNode,
) -> str:
    if node.text and node.text.strip():
        return node.text.strip()

    parts: list[str] = []

    for child in node.children:
        child_text = collect_node_text(child)

        if child_text:
            parts.append(child_text)

    return " ".join(parts)


def collect_chunks(
    node: DocumentNode,
    document_name: str,
    section_path: list[str],
) -> list[Chunk]:
    current_path = build_section_path(
        node=node,
        section_path=section_path,
    )

    if node.doctype == "Paragraph":
        return chunk_paragraph(
            node=node,
            document_name=document_name,
            section_path=current_path,
        )

    if node.doctype == "Table":
        return chunk_table(
            node=node,
            document_name=document_name,
            section_path=current_path,
        )

    if node.doctype == "Image":
        return chunk_image(
            node=node,
            document_name=document_name,
            section_path=current_path,
        )

    if node.doctype == "List":
        return chunk_list(
            node=node,
            document_name=document_name,
            section_path=current_path,
        )

    chunks: list[Chunk] = []

    for child in node.children:
        chunks.extend(
            collect_chunks(
                node=child,
                document_name=document_name,
                section_path=current_path,
            )
        )

    return chunks


def chunk_document(
    document: DocumentNode,
) -> list[Chunk]:
    return collect_chunks(
        node=document,
        document_name=document.document_name,
        section_path=[],
    )


def chunk_to_dict(
    chunk: Chunk,
) -> dict:
    return {
        "text": chunk.text,
        "metadata": {
            "document_name": chunk.metadata.document_name,
            "node_id": str(chunk.metadata.node_id),
            "parent_id": (
                str(chunk.metadata.parent_id)
                if chunk.metadata.parent_id is not None
                else None
            ),
            "node_type": chunk.metadata.node_type,
            "section_path": chunk.metadata.section_path,
            "source_tag": chunk.metadata.source_tag,
            "source_depth": chunk.metadata.source_depth,
            "source_position": chunk.metadata.source_position,
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
    text_path = output_dir / f"{document_name}.txt"

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

    with text_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            file.write("=" * 60)
            file.write("\n")
            file.write(f"CHUNK {index:03d}\n")
            file.write("=" * 60)
            file.write("\n\n")

            file.write(chunk.text)

            file.write("\n\n")
            file.write("Metadata:\n")

            file.write(
                json.dumps(
                    chunk_to_dict(chunk)["metadata"],
                    indent=2,
                    ensure_ascii=False,
                )
            )

            file.write("\n\n")

    print(f"Chunk output saved: {json_path}")
    print(f"Chunk inspection saved: {text_path}")
