from __future__ import annotations
import json
from pathlib import Path
from uuid import UUID
from rag.app.database.models import DocumentNode

TABLE_NAME = "document_nodes"
BATCH_SIZE = 1000

def get_nodes(supabase) -> list[DocumentNode]:
    nodes: list[DocumentNode] = []
    start = 0

    while True:
        response = (
            supabase.table(TABLE_NAME)
            .select("*")
            .range(start, start + BATCH_SIZE - 1)
            .execute()
        )

        batch = [DocumentNode(**row) for row in response.data]

        nodes.extend(batch)

        if len(batch) < BATCH_SIZE:
            break

        start += BATCH_SIZE

    return nodes


def group_nodes_by_document(
    nodes: list[DocumentNode],
) -> dict[str, list[DocumentNode]]:
    documents: dict[str, list[DocumentNode]] = {}

    for node in nodes:
        documents.setdefault(
            node.document_name,
            [],
        ).append(node)

    return documents


def build_tree(
    nodes: list[DocumentNode],
) -> list[DocumentNode]:
    nodes_by_id = {node.id: node for node in nodes}

    roots: list[DocumentNode] = []

    for node in nodes:
        node.children = []

    for node in nodes:
        if node.parent_id is None:
            roots.append(node)
            continue

        parent = nodes_by_id.get(node.parent_id)

        if parent is None:
            raise ValueError(
                "\n"
                "Missing parent!\n"
                f"Document: {node.document_name}\n"
                f"Node ID: {node.id}\n"
                f"Node type: {node.doctype}\n"
                f"Parent ID: {node.parent_id}\n"
                f"Source tag: {node.source_tag}\n"
                f"Source depth: {node.source_depth}\n"
                f"Source position: {node.source_position}\n"
            )

        parent.children.append(node)

    for node in nodes:
        node.children.sort(
            key=lambda child: (
                child.source_position,
                str(child.id),
            )
        )

    roots.sort(
        key=lambda node: (
            node.source_position,
            str(node.id),
        )
    )

    return roots


def check_for_cycles(
    node: DocumentNode,
    ancestors: set[UUID] | None = None,
) -> None:
    if ancestors is None:
        ancestors = set()

    if node.id in ancestors:
        raise ValueError(f"Cycle detected at node {node.id}")

    current_ancestors = ancestors | {node.id}

    for child in node.children:
        check_for_cycles(
            child,
            current_ancestors,
        )


def node_to_dict(
    node: DocumentNode,
) -> dict:
    data = {
        "document_name": node.document_name,
        "type": node.doctype,
        "metadata": {
            "id": str(node.id),
            "parent_id": (str(node.parent_id) if node.parent_id is not None else None),
            "source_tag": node.source_tag,
            "source_depth": node.source_depth,
            "source_position": node.source_position,
        },
        "children": [node_to_dict(child) for child in node.children],
    }

    if node.title is not None:
        data["title"] = node.title

    if node.level is not None:
        data["level"] = node.level

    if node.text is not None:
        data["text"] = node.text

    if node.src is not None:
        data["src"] = node.src

    if node.alt is not None:
        data["alt"] = node.alt

    if node.caption is not None:
        data["caption"] = node.caption

    if node.ordered is not None:
        data["ordered"] = node.ordered

    return data


def save_tree(
    document_name: str,
    root: DocumentNode,
    output_dir: Path,
) -> None:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = output_dir / f"{document_name}.json"

    data = node_to_dict(root)

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Retrieval output saved: {output_path}")


def retrieve_documents(
    supabase,
    output_dir: Path,
) -> None:
    nodes = get_nodes(supabase)

    if not nodes:
        print("No nodes found in the database.")
        return

    documents = group_nodes_by_document(nodes)

    print(f"Retrieved {len(nodes)} nodes " f"from {len(documents)} document(s).")

    for document_name, document_nodes in documents.items():
        print()
        print("=" * 60)
        print(f"Reconstructing: {document_name}")
        print("=" * 60)

        roots = build_tree(document_nodes)

        if not roots:
            raise ValueError(f"No root node found for document " f"'{document_name}'.")

        for root in roots:
            check_for_cycles(root)

            if root.doctype != "Document":
                print(f"Warning: root {root.id} is " f"{root.doctype}, not Document.")

            save_tree(
                document_name=document_name,
                root=root,
                output_dir=output_dir,
            )

        print(f"Found {len(roots)} root node(s).")
