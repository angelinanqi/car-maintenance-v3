from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import re

from rag.app.models.document_tree import DocumentNode


class TableChunkingError(ValueError):
    """A table contains invalid explicit cell spans."""


@dataclass
class _Row:
    node: DocumentNode
    cells: list[DocumentNode]
    values: list[str]
    text: str


def get_rows(table: DocumentNode) -> list[DocumentNode]:
    return [n for n in table.children if n.doctype == "Row"]


def get_cells(row: DocumentNode) -> list[DocumentNode]:
    return [n for n in row.children if n.doctype == "Cell"]


def collect_text(node: DocumentNode) -> str:
    parts = []

    if node.text and node.text.strip():
        parts.append(node.text.strip())

    for child in node.children:
        value = collect_text(child)
        if value:
            parts.append(value)

    return " ".join(parts)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def get_cell_text(cell: DocumentNode) -> str:
    return normalize_text(collect_text(cell))


def escape_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", r"\|")


def _attribute(node: DocumentNode, name: str, default: Any = None) -> Any:
    value = getattr(node, name, None)
    if value is not None:
        return value

    metadata = getattr(node, "metadata", None)
    if isinstance(metadata, dict):
        return metadata.get(name, default)

    return default


def _span(cell: DocumentNode, name: str) -> int:
    value = _attribute(cell, name, 1)

    # Missing span metadata means one cell; never infer a merged cell.
    if value is None:
        return 1

    if isinstance(value, bool):
        raise TableChunkingError(f"Invalid {name}: {value!r}")

    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value)
    else:
        raise TableChunkingError(f"Invalid {name}: {value!r}")

    if result < 1:
        raise TableChunkingError(f"Invalid {name}: {value!r}")

    return result


def _read_table(
    table: DocumentNode,
) -> tuple[list[_Row], set[int]]:
    """
    Preserve source order and explicit spans.

    Empty slots covered by a span remain empty. The originating cell gets
    a structural annotation, e.g. [rowspan=2, colspan=3].

    Returns boundaries that cannot be split because of explicit rowspans.
    Boundary i means the boundary immediately before source row i.
    """
    source_rows = get_rows(table)
    rows: list[_Row] = []
    forbidden: set[int] = set()

    # Logical column -> exclusive ending source-row position.
    occupied_until: dict[int, int] = {}

    for index, node in enumerate(source_rows):
        cells = get_cells(node)
        values = [get_cell_text(cell) for cell in cells]
        occupied = {
            column
            for column, end in occupied_until.items()
            if end > index
        }

        slots = [""] * (max(occupied, default=-1) + 1)
        column = 0

        for cell, value in zip(cells, values):
            while column in occupied:
                column += 1

            rowspan = _span(cell, "rowspan")
            colspan = _span(cell, "colspan")
            end_row = index + rowspan

            if end_row > len(source_rows):
                raise TableChunkingError(
                    f"Row {index}: rowspan extends beyond the table."
                )

            covered_columns = range(column, column + colspan)

            if any(c in occupied for c in covered_columns):
                raise TableChunkingError(
                    f"Row {index}: overlapping spans; check extraction metadata."
                )

            required_width = column + colspan
            slots.extend([""] * max(0, required_width - len(slots)))

            rendered = escape_cell(value)

            if rowspan > 1 or colspan > 1:
                rendered += f" [rowspan={rowspan}, colspan={colspan}]"

            slots[column] = rendered

            if rowspan > 1:
                forbidden.update(range(index + 1, end_row))
                for covered_column in covered_columns:
                    occupied_until[covered_column] = end_row

            column += colspan

        # Keep empty rows internally for indexing and span relationships.
        # Omit them only from retrieval text.
        text = " | ".join(slots) if any(values) else ""
        rows.append(_Row(node, cells, values, text))

    return rows, forbidden


def _caption(table: DocumentNode) -> str:
    value = normalize_text(getattr(table, "caption", "") or "")
    return f"Table: {value}" if value else ""


def _render(
    caption: str,
    rows: list[_Row],
    indices: Iterable[int],
) -> str:
    lines = [caption] if caption else []
    lines.extend(
        rows[index].text
        for index in sorted(set(indices))
        if rows[index].text
    )
    return "\n".join(lines)


def format_table(table: DocumentNode) -> str:
    """
    Stable retrieval representation; no header/key-value/section inference.

    The DocumentNode tree remains unchanged. Complete original HTML is held
    separately in the source-element manifest, never reconstructed here.
    """
    rows, _ = _read_table(table)
    return _render(_caption(table), rows, range(len(rows)))


def structured_table(table: DocumentNode) -> dict:
    """Expand only declared spans, preserving the original cells separately.

    Structural validity does not attest OCR fidelity. Verification is an
    administrator action against the original source, never inferred here.
    """
    from html import escape
    rows = get_rows(table)
    grid = []
    occupied = {}
    html_rows = []
    for row_index, row in enumerate(rows):
        values = {}
        for (r, column), value in occupied.items():
            if r == row_index:
                values[column] = value
        column = 0
        html_cells = []
        for cell in get_cells(row):
            while column in values:
                column += 1
            text = get_cell_text(cell)
            rowspan, colspan = _span(cell, "rowspan"), _span(cell, "colspan")
            if row_index + rowspan > len(rows):
                raise TableChunkingError("Merged cell extends beyond table")
            for r in range(row_index, row_index + rowspan):
                for c in range(column, column + colspan):
                    if (r, c) in occupied:
                        raise TableChunkingError("Overlapping merged cells")
                    occupied[(r, c)] = text
                    if r == row_index:
                        values[c] = text
            tag = "th" if cell.source_tag == "th" else "td"
            html_cells.append(f'<{tag} rowspan="{rowspan}" colspan="{colspan}">{escape(text)}</{tag}>')
            column += colspan
        grid.append([values.get(c, "") for c in range(max(values, default=-1) + 1)])
        html_rows.append("<tr>" + "".join(html_cells) + "</tr>")
    width = max((len(row) for row in grid), default=0)
    valid = bool(width) and all(len(row) == width for row in grid)
    headers = 0
    for row in rows:
        if get_cells(row) and all(cell.source_tag == "th" for cell in get_cells(row)):
            headers += 1
        else:
            break
    return {"rows": grid, "header_row_count": headers or None,
            "parse_valid": valid, "source_node_id": str(table.id),
            "row_node_ids": [str(row.id) for row in rows],
            "source_html": "<table>" + "".join(html_rows) + "</table>"}
