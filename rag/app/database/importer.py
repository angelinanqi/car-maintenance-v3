from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from uuid import UUID
from supabase import Client
from rag.app.database.models import DocumentNodeCreate

TABLE_NAME = "document_nodes"


def get_document_name(node: dict[str, Any]) -> str:
    metadata = node.get("metadata", {})

    document_name = metadata.get("document_name")

    if not document_name:
        raise ValueError("Node is missing metadata.document_name.")

    return document_name


def validate_node(
    node: dict[str, Any],
    document_name: str,
) -> None:
    if not isinstance(node, dict):
        raise ValueError("Node must be a dictionary.")

    node_type = node.get("type")

    if not node_type:
        raise ValueError("Node is missing its 'type'.")

    metadata = node.get("metadata")

    if not isinstance(metadata, dict):
        raise ValueError(f"Node '{node_type}' is missing metadata.")

    required_metadata = [
        "document_name",
        "source_tag",
        "source_depth",
        "source_position",
    ]

    for field_name in required_metadata:
        if field_name not in metadata:
            raise ValueError(
                f"Node '{node_type}' is missing " f"metadata.{field_name}."
            )

    node_document_name = metadata["document_name"]

    if node_document_name != document_name:
        raise ValueError(
            "Document name mismatch. "
            f"Expected '{document_name}', "
            f"found '{node_document_name}'."
        )

    children = node.get("children", [])

    if not isinstance(children, list):
        raise ValueError(f"Node '{node_type}' has invalid children.")

    for child in children:
        validate_node(
            node=child,
            document_name=document_name,
        )


def node_to_record(
    node: dict[str, Any],
    document_name: str,
    parent_id: UUID | None,
) -> DocumentNodeCreate:
    metadata = node["metadata"]

    return DocumentNodeCreate(
        document_name=document_name,
        doctype=node["type"],
        parent_id=parent_id,
        source_tag=metadata["source_tag"],
        source_depth=metadata["source_depth"],
        source_position=metadata["source_position"],
        title=node.get("title"),
        level=node.get("level"),
        text=node.get("text"),
        src=node.get("src"),
        alt=node.get("alt_text"),
        caption=node.get("caption"),
        ordered=node.get("ordered"),
    )


def insert_node(
    supabase: Client,
    node: dict[str, Any],
    document_name: str,
    parent_id: UUID | None = None,
    inserted_records: list[dict[str, Any]] | None = None,
) -> UUID:
    record = node_to_record(
        node=node,
        document_name=document_name,
        parent_id=parent_id,
    )

    data = record.model_dump(mode="json")

    response = supabase.table(TABLE_NAME).insert(data).execute()

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the inserted node: " f"{node.get('type')}"
        )

    inserted_row = response.data[0]

    generated_id = UUID(inserted_row["id"])

    if inserted_records is not None:
        inserted_records.append(inserted_row)

    print(f"Inserted {node['type']}: " f"{generated_id}")

    for child in node.get("children", []):
        insert_node(
            supabase=supabase,
            node=child,
            document_name=document_name,
            parent_id=generated_id,
            inserted_records=inserted_records,
        )

    return generated_id


def delete_existing_document(
    supabase: Client,
    document_name: str,
) -> None:
    (supabase.table(TABLE_NAME).delete().eq("document_name", document_name).execute())


def import_json_file(
    supabase: Client,
    json_path: Path,
    output_dir: Path,
) -> None:
    print()
    print("=" * 60)
    print(f"Importing: {json_path.name}")
    print("=" * 60)

    with json_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{json_path.name} does not contain " "a root node object.")

    document_name = get_document_name(data)

    validate_node(
        node=data,
        document_name=document_name,
    )

    print(f"Document: {document_name}")

    delete_existing_document(
        supabase=supabase,
        document_name=document_name,
    )

    inserted_records: list[dict[str, Any]] = []

    root_id = insert_node(
        supabase=supabase,
        node=data,
        document_name=document_name,
        parent_id=None,
        inserted_records=inserted_records,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = output_dir / json_path.name

    output_data = {
        "document_name": document_name,
        "root_id": str(root_id),
        "node_count": len(inserted_records),
        "nodes": inserted_records,
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output_data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(f"Finished: {json_path.name}")
    print(f"Document: {document_name}")
    print(f"Root UUID: {root_id}")
    print(f"Nodes inserted: {len(inserted_records)}")
    print(f"Checkpoint: {output_path}")
    print("=" * 60)


def import_directory(
    supabase: Client,
    input_dir: Path,
    output_dir: Path,
) -> None:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    json_files = sorted(input_dir.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in: {input_dir}")
        return

    print(f"Found {len(json_files)} JSON file(s).")

    for json_path in json_files:
        try:
            import_json_file(
                supabase=supabase,
                json_path=json_path,
                output_dir=output_dir,
            )

        except Exception as error:
            print()
            print(f"ERROR importing {json_path.name}:")
            print(error)
            print("Skipping this file and continuing...")

    print()
    print("=" * 60)
    print("All JSON files processed.")
    print("=" * 60)
