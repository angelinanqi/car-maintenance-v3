"use client";

import { Box } from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import type { DetectedTable, Selection } from "@/api/maintenanceAssistance";

export default function TableEvidence({
  table,
  selection,
  disabled,
  onExclude,
}: {
  table: DetectedTable;
  selection: Selection;
  disabled: boolean;
  onExclude: (row: number) => void;
}) {
  const rows = [...new Set(table.source.cells.map((cell) => cell.row))].sort(
    (a, b) => a - b,
  );
  return (
    <Box overflowX="auto" maxH="420px" overflowY="auto" mt={3}>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <caption>
          {table.title || "Service table"} — compare with the original
        </caption>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row}
              style={{
                opacity: selection.excluded_rows.includes(row) ? 0.5 : 1,
              }}
            >
              <td style={{ padding: 8, border: "1px solid #aab4bf" }}>
                <Checkbox
                  disabled={disabled}
                  checked={selection.excluded_rows.includes(row)}
                  onCheckedChange={() => onExclude(row)}
                >
                  Skip row {row + 1}
                </Checkbox>
              </td>
              {table.source.cells
                .filter((cell) => cell.row === row)
                .sort((a, b) => a.column - b.column)
                .map((cell) => (
                  <td
                    key={cell.column}
                    rowSpan={cell.rowspan || 1}
                    colSpan={cell.colspan || 1}
                    style={{
                      padding: 8,
                      border: "1px solid #aab4bf",
                      whiteSpace: "pre-wrap",
                      background: selection.columns.includes(cell.column)
                        ? "#fff9e8"
                        : undefined,
                      fontWeight: cell.header ? 600 : 400,
                    }}
                  >
                    {cell.text}
                  </td>
                ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Box>
  );
}

