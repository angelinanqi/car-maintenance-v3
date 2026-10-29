"use client";

import { useEffect, useState } from "react";
import { Box, Button, Flex, Stack, Text, Textarea } from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import { request } from "@/api/client.mjs";
import FormField from "./FormField";

function escapeText(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function tableMarkup(block, values) {
  const rows = [...new Set(block.cells.map((cell) => cell.row))].sort((a, b) => a - b);
  const caption = block.html.match(/<caption\b[^>]*>[\s\S]*?<\/caption>/i)?.[0] || "";
  return `<table>${caption}${rows.map((row) => `<tr>${block.cells.map((cell, index) => {
    if (cell.row !== row) return "";
    const tag = cell.header ? "th" : "td";
    return `<${tag} rowspan="${cell.rowspan}" colspan="${cell.colspan}">${escapeText(values[index]).replaceAll("\n", "<br>")}</${tag}>`;
  }).join("")}</tr>`).join("\n")}</table>`;
}

export default function ExtractionCorrection({ document, block, disabled, onDirty, onSaved }) {
  const sourceCells = block.cells || [];
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(block.text);
  const [cells, setCells] = useState(sourceCells.map((cell) => cell.text));
  const [html, setHtml] = useState(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const isTable = block.kind === "table";
  const changed = isTable ? html !== null ? html !== block.html : cells.some((value, index) => value !== sourceCells[index].text) : text !== block.text;
  const replacement = isTable ? html ?? tableMarkup(block, cells) : text;

  useEffect(() => {
    onDirty(open && !saved);
    return () => onDirty(false);
  }, [open, saved, onDirty]);

  function cancel() {
    if (busy || (changed && !window.confirm("Discard this unsaved correction?"))) return;
    setOpen(false);
    setText(block.text);
    setCells(sourceCells.map((cell) => cell.text));
    setHtml(null);
    setReason("");
    setConfirmed(false);
    setError("");
  }

  async function save() {
    if (busy || disabled || !changed || !reason.trim() || !confirmed) return;
    setBusy(true);
    setError("");
    try {
      await request(`/documents/${document.id}/corrections`, { method: "POST", body: {
        source_revision: document.source_revision, element_id: block.element_id,
        replacement, reason, confirm_source: confirmed,
      } });
      setSaved(true);
      await onSaved("Correction saved. Indexing is pending; you can continue correcting other entries. Review the latest extraction before final approval.");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  if (document.published || document.superseded_by_id) return <Text fontSize="sm" color="muted">Take this document offline or stage a replacement to correct its extraction.</Text>;
  if (!open) return <Button alignSelf="start" size="sm" variant="outline" disabled={disabled} onClick={() => setOpen(true)}>
    Correct extracted {isTable ? "table" : "text"}
  </Button>;

  return <Stack gap={4} borderWidth="1px" borderColor="brand.200" borderRadius="8px" p={4}>
    <Text fontWeight="600">Correct extracted {isTable ? "table" : "text"}</Text>
    <Text fontSize="sm">Copy what the original says, including its units and conditions. Saving keeps the original extraction and edit history, rebuilds the knowledge index, and starts a new document review. Existing schedule drafts keep their previous references and need checking again.</Text>
    {error && <Text role="alert">{saved ? "The correction was saved, but refreshing the document failed. Reload the document to continue. " : ""}{error}</Text>}
    {saved ? <Text role="status">Correction saved. The latest extraction is queued for indexing. Reload the document to continue correcting or reviewing entries.</Text> : <>
      {!isTable ? <FormField label="Corrected section text"><Textarea value={text} minH="260px" maxLength={200000} disabled={busy || disabled}
        onChange={(event) => { setText(event.target.value); setConfirmed(false); }} /></FormField>
        : html !== null ? <FormField label="Corrected table HTML" hint="Use one table with tr, th and td cells. Rowspan and colspan preserve merged cells. All rows must cover the same number of columns.">
          <Textarea value={html} minH="300px" maxLength={200000} fontFamily="mono" fontSize="sm" disabled={busy || disabled}
            onChange={(event) => { setHtml(event.target.value); setConfirmed(false); }} />
        </FormField> : <>
          <Text fontSize="sm">Edit cell text below. Existing rows, columns and merged cells are preserved.</Text>
          <Box overflow="auto" maxH="420px">
            <table style={{ width: "100%", borderCollapse: "collapse" }}><tbody>
              {[...new Set(block.cells.map((cell) => cell.row))].sort((a, b) => a - b).map((row) => <tr key={row}>
                {block.cells.map((cell, index) => cell.row === row && <td key={index} rowSpan={cell.rowspan} colSpan={cell.colspan}
                  style={{ padding: 6, border: "1px solid #aab4bf", background: cell.header ? "#fff9e8" : undefined, minWidth: 140 }}>
                  <Textarea aria-label={`Row ${cell.row + 1}, column ${cell.column + 1}`} value={cells[index]} minH="70px" maxLength={20000} disabled={busy || disabled}
                    onChange={(event) => { setCells(cells.map((value, position) => position === index ? event.target.value : value)); setConfirmed(false); }} />
                </td>)}
              </tr>)}
            </tbody></table>
          </Box>
          <Button size="sm" variant="plain" alignSelf="start" disabled={busy || disabled} onClick={() => setHtml(changed ? tableMarkup(block, cells) : block.html)}>Repair rows or merged cells in HTML</Button>
        </>}
      <FormField label="Reason for correction"><Textarea value={reason} maxLength={1000} disabled={busy || disabled}
        placeholder="For example: OCR read 10,000 km as 1,000 km."
        onChange={(event) => setReason(event.target.value)} /></FormField>
      <Checkbox checked={confirmed} disabled={busy || disabled} onCheckedChange={(event) => setConfirmed(event.checked === true)}>
        I checked this correction against the original document.
      </Checkbox>
      <Flex gap={3} wrap="wrap">
        <Button loading={busy} disabled={disabled || !changed || !replacement.trim() || !reason.trim() || !confirmed} onClick={save}>Save correction and rebuild index</Button>
        <Button variant="outline" disabled={busy} onClick={cancel}>Cancel correction</Button>
      </Flex>
    </>}
  </Stack>;
}
