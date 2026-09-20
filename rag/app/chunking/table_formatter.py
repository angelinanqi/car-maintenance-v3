from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable
import re

from rag.app.models.document_tree import DocumentNode


class TableChunkingError(ValueError):
    """A table cannot be split safely within the supplied token budget."""


@dataclass(frozen=True)
class TablePolicy:
    # Zero-based SOURCE row positions, including completely empty rows.
    #
    # None: repeat a bounded leading prefix as uncertain context.
    # 0: explicitly declare that there are no table-level header rows.
    # N: repeat the first N source rows.
    header_row_count: int | None = None

    # Supply these only when supported by extraction metadata or inspection.
    section_rows: frozenset[int] = frozenset()

    # A listed row must stay with its preceding row.
    keep_with_previous: frozenset[int] = frozenset()

    # Conservative proximity heuristic; never copies/invents parent values.
    protect_likely_continuations: bool = True

    # Used only when header_row_count is unknown.
    fallback_context_fraction: float = 0.25


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

    The original DocumentNode tree, including original HTML and metadata,
    remains unchanged and remains the source of truth.
    """
    rows, _ = _read_table(table)
    return _render(_caption(table), rows, range(len(rows)))


def _node_id(node: DocumentNode) -> str:
    # Adapt this helper if your model uses another identifier field.
    value = getattr(node, "id", None)
    if value is None:
        value = getattr(node, "node_id", None)
    if value is None:
        raise TableChunkingError("DocumentNode has no id or node_id.")
    return str(value)


def _descendant_ids(node: DocumentNode) -> Iterable[str]:
    yield _node_id(node)
    for child in node.children:
        yield from _descendant_ids(child)


def chunk_table(
    table: DocumentNode,
    *,
    max_tokens: int,
    count_tokens: Callable[[str], int],
    policy: TablePolicy | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Return JSON-compatible chunks: {"text": ..., "metadata": ...}.

    Pass the embedding model's actual token counter. The budget applies
    to the complete returned text, including repeated context/caption.

    Pass existing document/section/source metadata through `metadata`.
    Do not run these chunks through a generic text splitter afterwards.

    Oversized indivisible groups raise TableChunkingError. Nothing is
    truncated, and no oversized chunk is returned.
    """
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive.")

    policy = policy or TablePolicy()
    rows, forbidden = _read_table(table)
    caption = _caption(table)
    row_count = len(rows)
    table_id = _node_id(table)

    if not 0 < policy.fallback_context_fraction < 1:
        raise ValueError("fallback_context_fraction must be between 0 and 1.")

    if (
        policy.header_row_count is not None
        and not 0 <= policy.header_row_count <= row_count
    ):
        raise ValueError("header_row_count is outside the source table.")

    if any(not 0 <= i < row_count for i in policy.section_rows):
        raise ValueError("section_rows contains an invalid source row.")

    if any(not 1 <= i < row_count for i in policy.keep_with_previous):
        raise ValueError("keep_with_previous contains an invalid source row.")

    forbidden.update(policy.keep_with_previous)

    # Keep a declared section label with its next nonempty row.
    for section in policy.section_rows:
        following = next(
            (
                i
                for i in range(section + 1, row_count)
                if rows[i].text
            ),
            None,
        )
        if following is not None:
            forbidden.update(range(section + 1, following + 1))

    if policy.protect_likely_continuations:
        previous: int | None = None

        for index, row in enumerate(rows):
            if not row.text:
                continue

            if (
                previous is not None
                and index not in policy.section_rows
                and previous not in policy.section_rows
                and row.values
                and (
                    not row.values[0]
                    or len(row.values) < len(rows[previous].values)
                )
            ):
                forbidden.update(range(previous + 1, index + 1))

            previous = index

    # Atomic units cannot be split internally.
    units: list[list[int]] = []

    for index in range(row_count):
        if units and index in forbidden:
            units[-1].append(index)
        else:
            units.append([index])

    context: list[int] = []
    body_units = list(units)

    if policy.header_row_count is not None:
        # If a span/continuation crosses the header boundary, preserve
        # the whole atomic unit rather than breaking that relationship.
        while body_units and body_units[0][0] < policy.header_row_count:
            context.extend(body_units.pop(0))
        context_mode = "declared"
    else:
        # These are repeated SOURCE rows, not asserted semantic headers.
        # A bounded prefix cannot guarantee understanding of every
        # unannotated table; this limitation is exposed in metadata.
        context_budget = max(
            1, int(max_tokens * policy.fallback_context_fraction)
        )

        while body_units:
            candidate = context + body_units[0]
            text = _render("", rows, candidate)

            if count_tokens(text) > context_budget:
                break

            context.extend(body_units.pop(0))

        # Retain at least the first meaningful atomic unit as context.
        # If it cannot coexist with subsequent data, fail explicitly.
        while body_units and not any(rows[i].text for i in context):
            context.extend(body_units.pop(0))

        context_mode = "leading_prefix_fallback"

    base_metadata = dict(metadata or {})
    base_metadata.update(
        {
            "node_type": "Table",
            "table_id": table_id,
            "table_context_mode": context_mode,
            "table_context_requires_review": context_mode != "declared",
        }
    )

    parent_id = getattr(table, "parent_id", None)
    if parent_id is not None:
        base_metadata["parent_id"] = str(parent_id)

    chunks: list[dict[str, Any]] = []
    body: list[int] = []
    active_section: int | None = None
    chunk_section: int | None = None

    def indices_for(
        body_indices: list[int],
        section: int | None,
    ) -> list[int]:
        indices = context + body_indices
        if section is not None:
            indices = indices + [section]
        return sorted(set(indices))

    def text_for(
        body_indices: list[int],
        section: int | None,
    ) -> str:
        return _render(caption, rows, indices_for(body_indices, section))

    def emit(body_indices: list[int], section: int | None) -> None:
        indices = indices_for(body_indices, section)
        text = _render(caption, rows, indices)

        if not text:
            return

        tokens = count_tokens(text)
        if tokens > max_tokens:
            raise TableChunkingError(
                f"Table {table_id}: context plus indivisible source rows "
                f"{body_indices or context} requires {tokens} tokens; "
                f"budget is {max_tokens}. Check context annotations or "
                "use an explicitly configured larger embedding budget."
            )

        ids = [table_id]
        for index in indices:
            ids.extend(_descendant_ids(rows[index].node))

        chunk_metadata = dict(base_metadata)
        chunk_metadata.update(
            {
                "node_ids": list(dict.fromkeys(ids)),
                "table_row_indices": indices,
                "table_body_row_indices": list(body_indices),
                "table_context_row_indices": [
                    i for i in indices if i not in body_indices
                ],
                "table_token_count": tokens,
            }
        )

        chunks.append({"text": text, "metadata": chunk_metadata})

    # A section included in table context can remain active afterward.
    for index in context:
        if index in policy.section_rows:
            active_section = index

    for unit in body_units:
        if not any(rows[i].text for i in unit):
            continue

        sections_in_unit = [
            i for i in unit if i in policy.section_rows
        ]

        # Keep independent sections in separate chunks where possible.
        if sections_in_unit and body:
            emit(body, chunk_section)
            body = []

        if unit[0] in policy.section_rows:
            active_section = unit[0]

        if not body:
            chunk_section = active_section

        candidate = body + unit

        if count_tokens(text_for(candidate, chunk_section)) <= max_tokens:
            body = candidate
        else:
            if body:
                emit(body, chunk_section)

            body = list(unit)
            chunk_section = active_section

            # Validate before continuing; no partial result is returned.
            if count_tokens(text_for(body, chunk_section)) > max_tokens:
                raise TableChunkingError(
                    f"Table {table_id}: source rows {unit}, together with "
                    f"required context, exceed {max_tokens} tokens. "
                    "The row/span/continuation group was not split."
                )

        if sections_in_unit:
            active_section = sections_in_unit[-1]

    if body:
        emit(body, chunk_section)
    elif not chunks:
        emit([], active_section)

    for index, chunk in enumerate(chunks):
        chunk["metadata"]["table_chunk_index"] = index
        chunk["metadata"]["table_chunk_count"] = len(chunks)

    return chunks