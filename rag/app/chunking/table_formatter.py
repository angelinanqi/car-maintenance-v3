from __future__ import annotations
from rag.app.database.models import DocumentNode


def get_rows(
    table: DocumentNode,
) -> list[DocumentNode]:
    return [child for child in table.children if child.doctype == "Row"]


def get_cells(
    row: DocumentNode,
) -> list[DocumentNode]:
    return [child for child in row.children if child.doctype == "Cell"]


def get_cell_text(
    cell: DocumentNode,
) -> str:
    if cell.text and cell.text.strip():
        return cell.text.strip()

    parts: list[str] = []

    for child in cell.children:
        child_text = collect_text(child)

        if child_text:
            parts.append(child_text)

    return "\n".join(parts)


def collect_text(
    node: DocumentNode,
) -> str:
    if node.text and node.text.strip():
        return node.text.strip()

    parts: list[str] = []

    for child in node.children:
        child_text = collect_text(child)

        if child_text:
            parts.append(child_text)

    return " ".join(parts)


def is_header_row(
    row: DocumentNode,
    total_rows: int,
) -> bool:
    """
    Decide whether the first row should be treated as headers.

    Rules:
    - A table with only one row does not have a header.
    - A two-column table is treated as label/value data.
    - For larger tables, the first row is considered a header
      only when it has at least two non-empty cells.
    """

    cells = get_cells(row)

    values = [get_cell_text(cell) for cell in cells]

    non_empty = [value for value in values if value.strip()]

    if total_rows <= 1:
        return False

    if len(values) == 2:
        return False

    return len(non_empty) >= 2


def format_label_value_row(
    cells: list[DocumentNode],
) -> str:
    values = [get_cell_text(cell) for cell in cells]

    values = [value for value in values if value.strip()]

    if not values:
        return ""

    if len(values) == 1:
        return f"- {values[0]}"

    if len(values) == 2:
        return f"- {values[0]}: {values[1]}"

    return "- " + "\n  ".join(values)


def format_header_row(
    headers: list[str],
    cells: list[DocumentNode],
) -> str:
    values = [get_cell_text(cell) for cell in cells]

    parts: list[str] = []

    for index, value in enumerate(values):
        if not value.strip():
            continue

        if index < len(headers) and headers[index]:
            parts.append(f"{headers[index]}: {value}")
        else:
            parts.append(value)

    if not parts:
        return ""

    return "- " + "\n  ".join(parts)


def format_table(
    table: DocumentNode,
) -> str:
    rows = get_rows(table)

    if not rows:
        return ""

    formatted: list[str] = []

    if table.caption and table.caption.strip():
        formatted.append(f"Table: {table.caption.strip()}")

    first_row = rows[0]

    if is_header_row(
        first_row,
        len(rows),
    ):
        headers = [get_cell_text(cell) for cell in get_cells(first_row)]

        data_rows = rows[1:]

        for row in data_rows:
            row_text = format_header_row(
                headers=headers,
                cells=get_cells(row),
            )

            if row_text:
                formatted.append(row_text)

    else:
        for row in rows:
            row_text = format_label_value_row(
                cells=get_cells(row),
            )

            if row_text:
                formatted.append(row_text)

    return "\n\n".join(formatted)
