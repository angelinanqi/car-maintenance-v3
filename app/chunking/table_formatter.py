from __future__ import annotations
from app.database.models import DocumentNode


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
        if child.text and child.text.strip():
            parts.append(child.text.strip())

    return " ".join(parts)


def format_table(
    table: DocumentNode,
) -> str:
    rows = get_rows(table)

    if not rows:
        return ""

    formatted_rows: list[str] = []

    headers = get_cells(rows[0])

    header_texts = [get_cell_text(cell) for cell in headers]

    has_headers = any(text for text in header_texts)

    data_rows = rows[1:] if has_headers else rows

    if table.caption:
        formatted_rows.append(f"Table: {table.caption.strip()}")

    for row in data_rows:
        cells = get_cells(row)

        values = [get_cell_text(cell) for cell in cells]

        if not any(values):
            continue

        if has_headers:
            row_parts: list[str] = []

            for index, value in enumerate(values):
                if not value:
                    continue

                if index < len(header_texts):
                    header = header_texts[index]

                    if header:
                        row_parts.append(f"{header}: {value}")
                    else:
                        row_parts.append(value)
                else:
                    row_parts.append(value)

            if row_parts:
                formatted_rows.append("- " + "\n  ".join(row_parts))

        else:
            formatted_rows.append(
                "- " + "\n  ".join(value for value in values if value)
            )

    return "\n\n".join(formatted_rows)
