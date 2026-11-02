"use client";

import { useEffect, useState } from "react";
import { Badge, Box, Button, Flex, Grid, Heading, Input, Stack, Text, Textarea } from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import FormField from "@/components/admin/FormField";
import { AdminSelect } from "@/components/admin/NativeControls";
import MaintenanceItemEditor from "@/components/admin/MaintenanceItemEditor";
import type { MaintenanceItem, SourceDocument } from "@/api/admin";
import type { DraftRowEdit, DraftRule, Review, Suggestion } from "@/api/maintenanceAssistance";
import { serviceInstruction } from "@/lib/adminJourney.mjs";
import TableEvidence from "./TableEvidence";

type Props = {
  review: Review;
  document: SourceDocument;
  vehicleId: string;
  tableId: string;
  items: MaintenanceItem[];
  existingItemIds: (string | null)[];
  blockedItems: (string | null)[];
  disabled: boolean;
  onDirty: (dirty: boolean) => void;
  onItem: (item: MaintenanceItem) => void;
  onNavigate: (page: number) => void;
  onSave: (row: Suggestion, body: DraftRowEdit) => Promise<boolean>;
  onAsk: (row: Suggestion) => void;
  onImport: (review: Review, rows: Suggestion[]) => void;
  onBack: () => void;
};

function instruction(row: Suggestion) {
  if (row.ai_draft?.manual_entry_required) return "Needs manual entry";
  if (!row.ai_draft?.rule) return "Timing needs checking";
  return serviceInstruction({ rule: row.ai_draft.rule });
}

export default function AIScheduleDraft(props: Props) {
  const { review, vehicleId, tableId, items, disabled, blockedItems, existingItemIds } = props;
  const rows = review.suggestions.filter((row) => row.ai_draft?.vehicle_id === vehicleId && row.table_id === tableId);
  const [selectedId, setSelectedId] = useState(rows[0]?.suggestion_id || "");
  const [chosen, setChosen] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [filter, setFilter] = useState("all");
  const [notice, setNotice] = useState("");
  const selected = rows.find((row) => row.suggestion_id === selectedId) || rows[0];
  const table = review.catalogue.tables.find((table) => table.table_id === tableId);
  const selection = review.selections.find((choice) => choice.table_id === tableId);
  const visible = rows.filter((row) => filter === "all" || row.status === filter);
  const blocked = (row: Suggestion) => blockedItems.includes(null) || blockedItems.includes(row.mapped_item_id);
  const ready = rows.filter((row) => row.status === "accepted" && row.ai_draft?.reviewed_at &&
    !row.ai_draft.manual_entry_required && row.mapped_item_id && !blocked(row) &&
    !existingItemIds.includes(row.mapped_item_id) && items.some((item) => item.id === row.mapped_item_id && item.active));
  const additions = ready.filter((row) => chosen.includes(row.suggestion_id));
  const warnings = [...new Set(rows.flatMap((row) => row.ai_draft?.warnings || []))];

  useEffect(() => {
    props.onDirty(dirty);
    return () => props.onDirty(false);
  }, [dirty, props.onDirty]);

  function open(row: Suggestion) {
    if (disabled || dirty) return;
    setSelectedId(row.suggestion_id);
    if (row.ai_draft?.source_page) props.onNavigate(row.ai_draft.source_page);
  }

  return <Stack gap={4}>
    <Flex justify="space-between" gap={3} align="center" wrap="wrap">
      <Heading size="sm">Review the AI Schedule Draft</Heading>
      <Button size="sm" variant="outline" disabled={disabled || dirty} onClick={props.onBack}>Choose another table</Button>
    </Flex>
    <Text fontSize="sm">Check each operation, interval, condition and source. Accepting saves your review; selected accepted rows can then be added to the schedule draft.</Text>
    {warnings.map((warning) => <Text key={warning} fontSize="sm" color="orange.800">{warning}</Text>)}
    {notice && <Text role="status">{notice}</Text>}
    <FormField label="Show AI rows">
      <AdminSelect disabled={disabled || dirty} value={filter} onChange={(event) => setFilter(event.target.value)}>
        <option value="all">All rows ({rows.length})</option>
        <option value="suggested">Needs review ({rows.filter((row) => row.status === "suggested").length})</option>
        <option value="accepted">Accepted ({rows.filter((row) => row.status === "accepted").length})</option>
        <option value="rejected">Skipped ({rows.filter((row) => row.status === "rejected").length})</option>
      </AdminSelect>
    </FormField>
    <Box overflowX="auto" maxH="330px" overflowY="auto" borderWidth="1px" borderRadius="8px">
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <caption style={{ textAlign: "left", padding: 10 }}>{table?.title || "Selected maintenance table"}</caption>
        <thead><tr>{["Add", "Operation and proposed timing", "Review"].map((label) => <th key={label} style={{ padding: 10, textAlign: "left", borderBottom: "1px solid #aab4bf" }}>{label}</th>)}</tr></thead>
        <tbody>{visible.map((row) => <tr key={row.suggestion_id} style={{ background: selected?.suggestion_id === row.suggestion_id ? "#fff9e8" : undefined }}>
          <td style={{ padding: 10, verticalAlign: "top" }}>
            <Checkbox aria-label={`Add ${row.edited_name || row.suggested_name}`} disabled={disabled || dirty || !ready.includes(row)} checked={chosen.includes(row.suggestion_id)}
              onCheckedChange={(event) => setChosen((previous) => event.checked === true ? [...previous, row.suggestion_id] : previous.filter((id) => id !== row.suggestion_id))} />
          </td>
          <td style={{ padding: 10, minWidth: 180 }}>
            <Button variant="plain" h="auto" whiteSpace="normal" textAlign="left" px={0} disabled={disabled || dirty} onClick={() => open(row)}>{row.edited_name || row.suggested_name}</Button>
            <Text fontSize="xs" mt={1}>{row.ai_draft?.action || "Choose action"} · {instruction(row)}</Text>
            {row.ai_draft?.rule?.conditions && <Text fontSize="xs" mt={1}>{row.ai_draft.rule.conditions}</Text>}
          </td>
          <td style={{ padding: 10, verticalAlign: "top" }}>
            <Badge colorPalette={row.status === "accepted" ? "green" : row.status === "rejected" ? "gray" : "orange"}>{row.status === "accepted" ? "Accepted" : row.status === "rejected" ? "Skipped" : "Needs review"}</Badge>
            {row.mapped_item_id && existingItemIds.includes(row.mapped_item_id) && <Text fontSize="xs" mt={1}>Already in schedule</Text>}
            {blocked(row) && <Text fontSize="xs" color="orange.800" mt={1}>Open clarification</Text>}
          </td>
        </tr>)}</tbody>
      </table>
      {!visible.length && <Text p={3}>No rows in this view.</Text>}
    </Box>
    {selected && <>
      <Heading size="sm">{selected.edited_name || selected.suggested_name}</Heading>
      <Text fontSize="sm">Source table row{selected.ai_draft!.source_rows.length > 1 ? "s" : ""}: {selected.ai_draft!.source_rows.map((row) => row + 1).join(", ")}. Highlighted cells below are the evidence cited for this proposal.</Text>
      {table && selection && <details open>
        <summary style={{ cursor: "pointer" }}>Supporting table and cited notes</summary>
        <TableEvidence table={table} selection={selection} disabled highlightedCells={selected.ai_draft!.evidence.cells} />
        {selected.ai_draft!.evidence.notes.map((note, index) => <Text key={`note-${index}`} fontSize="sm" whiteSpace="pre-wrap" mt={2}>Note: {note}</Text>)}
        {selected.ai_draft!.evidence.context.map((text, index) => <Text key={`context-${index}`} fontSize="sm" whiteSpace="pre-wrap" mt={2}>Source context: {text}</Text>)}
      </details>}
      {selected.uncertainty.map((text, index) => <Text key={index} fontSize="sm" color="orange.800">{text}</Text>)}
      <DraftRowEditor key={`${selected.suggestion_id}:${review.version}`} row={selected} document={props.document} items={items}
        disabled={disabled} blocked={blocked(selected)} onDirty={setDirty} onItem={props.onItem} onNavigate={props.onNavigate}
        onAsk={() => props.onAsk(selected)} onSave={async (body) => {
          const saved = await props.onSave(selected, body);
          if (saved && body.status === "accepted") setChosen((previous) => [...new Set([...previous, selected.suggestion_id])]);
          return saved;
        }} />
    </>}
    <Flex gap={3} wrap="wrap">
      <Button variant="outline" disabled={disabled || dirty || !ready.length} onClick={() => setChosen(ready.map((row) => row.suggestion_id))}>Select accepted rows ({ready.length})</Button>
      <Button disabled={disabled || dirty || !additions.length} onClick={() => {
        props.onImport(review, additions);
        setNotice("Selected rows were added to the schedule draft. Save the schedule below to keep them.");
      }}>Add {additions.length} selected {additions.length === 1 ? "row" : "rows"} to schedule draft</Button>
    </Flex>
  </Stack>;
}

function initialFields(row: Suggestion) {
  const draft = row.ai_draft!;
  return {
    name: row.edited_name || row.suggested_name, action: draft.action || "", mapped: row.mapped_item_id || "",
    type: draft.rule?.type || "recurring", km: draft.rule?.distanceKm?.toString() || "",
    months: draft.rule?.months?.toString() || "", mileages: draft.rule?.distanceMilestones.join(", ") || "",
    ages: draft.rule?.monthMilestones.join(", ") || "", conditions: draft.rule?.conditions || "",
    notes: draft.rule?.notes || "", page: draft.source_page?.toString() || "",
  };
}

function points(text: string) {
  if (!text.trim()) return [];
  const values = text.split(",").map((value) => Number(value.trim()));
  if (values.some((value) => !Number.isSafeInteger(value) || value <= 0) || values.some((value, index) => index > 0 && value <= values[index - 1]))
    throw new Error("Enter unique, positive milestones in ascending order, separated by commas. Write 10000 without a thousands separator.");
  return values;
}

function DraftRowEditor({ row, document, items, disabled, blocked, onDirty, onItem, onNavigate, onAsk, onSave }: {
  row: Suggestion; document: SourceDocument; items: MaintenanceItem[]; disabled: boolean; blocked: boolean;
  onDirty: (dirty: boolean) => void; onItem: (item: MaintenanceItem) => void; onNavigate: (page: number) => void;
  onAsk: () => void; onSave: (body: DraftRowEdit) => Promise<boolean>;
}) {
  const original = initialFields(row);
  const [fields, setFields] = useState(original);
  const [confirmed, setConfirmed] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const dirty = JSON.stringify(fields) !== JSON.stringify(original) || confirmed;
  const manual = row.ai_draft!.manual_entry_required;
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);

  function change(values: Partial<typeof fields>) {
    setFields((previous) => ({ ...previous, ...values }));
    setConfirmed(false);
  }

  async function save(status: Suggestion['status']) {
    if (disabled) return;
    setError("");
    try {
      const rule: DraftRule | null = status === "rejected" ? null : {
        type: fields.type, distanceKm: fields.type === "recurring" && fields.km ? Number(fields.km) : null,
        months: fields.type === "recurring" && fields.months ? Number(fields.months) : null,
        distanceMilestones: fields.type === "milestone" ? points(fields.mileages) : [],
        monthMilestones: fields.type === "milestone" ? points(fields.ages) : [],
        conditions: fields.conditions, notes: fields.notes,
      };
      await onSave({ edited_name: fields.name.trim(), status,
        mapped_item_id: fields.mapped || null, action: (fields.action || null) as MaintenanceItem['action'] | null,
        rule, source_page: document.source_type === "pdf" && fields.page ? Number(fields.page) : null,
        confirm_review: status === "accepted" && confirmed });
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return <Stack gap={3} borderWidth="1px" borderRadius="8px" p={4}>
    {error && <Text role="alert">{error}</Text>}
    <FormField label="Operation name"><Input value={fields.name} maxLength={200} disabled={disabled} onChange={(event) => change({ name: event.target.value })} /></FormField>
    <FormField label="Action"><AdminSelect value={fields.action} disabled={disabled} onChange={(event) => {
      const action = event.target.value;
      change({ action, mapped: items.find((item) => item.id === fields.mapped)?.action === action ? fields.mapped : "" });
    }}><option value="">Choose action</option><option value="inspect">Inspect</option><option value="replace">Replace</option><option value="service">Service</option></AdminSelect></FormField>
    <FormField label="Matching service-library task"><AdminSelect value={fields.mapped} disabled={disabled} onChange={(event) => change({ mapped: event.target.value })}>
      <option value="">Choose a matching task</option>
      {items.filter((item) => item.active && (!fields.action || item.action === fields.action)).map((item) => <option key={item.id} value={item.id}>{row.catalogue_matches.some((match) => match.item_id === item.id) ? "Suggested: " : ""}{item.title} · {item.action}</option>)}
    </AdminSelect></FormField>
    <Button alignSelf="start" variant="outline" size="sm" disabled={disabled || !fields.action} onClick={() => setCreating(true)}>Add a missing service task</Button>
    {manual ? <Text color="orange.800" fontSize="sm">Skip this proposal and use “Add service task” in the schedule editor to enter its timing manually. This draft cannot represent the original timing as one rule.</Text> : <>
      <FormField label="Timing type"><AdminSelect value={fields.type} disabled={disabled} onChange={(event) => change({ type: event.target.value as DraftRule['type'] })}>
        <option value="recurring">Recurring interval</option><option value="milestone">Specific mileages or ages</option><option value="informational">Conditional guidance</option>
      </AdminSelect></FormField>
      {fields.type === "recurring" && <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
        <FormField label="Distance interval (km)"><Input type="number" min={1} step={1} value={fields.km} disabled={disabled} onChange={(event) => change({ km: event.target.value })} /></FormField>
        <FormField label="Time interval (months)"><Input type="number" min={1} step={1} value={fields.months} disabled={disabled} onChange={(event) => change({ months: event.target.value })} /></FormField>
      </Grid>}
      {fields.type === "milestone" && <>
        <FormField label="Service mileages (km, separated by commas)"><Input value={fields.mileages} disabled={disabled} onChange={(event) => change({ mileages: event.target.value })} /></FormField>
        <FormField label="Vehicle ages (months, separated by commas)"><Input value={fields.ages} disabled={disabled} onChange={(event) => change({ ages: event.target.value })} /></FormField>
      </>}
      <FormField label="Operating conditions"><Textarea value={fields.conditions} maxLength={2000} disabled={disabled} onChange={(event) => change({ conditions: event.target.value })} /></FormField>
      <FormField label="Notes and cautions"><Textarea value={fields.notes} maxLength={4000} disabled={disabled} onChange={(event) => change({ notes: event.target.value })} /></FormField>
    </>}
    {document.source_type === "pdf" && <Flex gap={3} align="end">
      <FormField label="Supporting PDF page"><Input type="number" min={1} step={1} value={fields.page} disabled={disabled} onChange={(event) => change({ page: event.target.value })} /></FormField>
      <Button variant="outline" size="sm" disabled={!fields.page || disabled} onClick={() => onNavigate(Number(fields.page))}>View page</Button>
    </Flex>}
    {blocked && <Text color="orange.800" fontSize="sm">Resolve this task's open clarification before accepting it.</Text>}
    {!manual && <Checkbox checked={confirmed} disabled={disabled || blocked} onCheckedChange={(event) => setConfirmed(event.checked === true)}>I checked this operation, timing, conditions and cited evidence against the original, including any uncertainties.</Checkbox>}
    <Flex gap={2} wrap="wrap">
      <Button disabled={disabled || manual || blocked || !confirmed || !fields.mapped || !fields.action || !fields.name.trim()} onClick={() => save("accepted")}>Accept reviewed row</Button>
      <Button variant="outline" disabled={disabled || !fields.name.trim()} onClick={() => save("suggested")}>{row.status === "accepted" ? "Mark for recheck" : "Save for later"}</Button>
      <Button variant="outline" disabled={disabled || !fields.name.trim()} onClick={() => save("rejected")}>Skip row</Button>
      <Button variant="plain" disabled={disabled || dirty} onClick={onAsk}>Needs clarification</Button>
    </Flex>
    {dirty && <Text fontSize="sm" color="muted">Save or accept this row before switching rows or adding accepted rows to the schedule.</Text>}
    {creating && <MaintenanceItemEditor initialTitle={fields.name} initialAction={fields.action as MaintenanceItem['action']}
      categories={[...new Set(items.map((item) => item.category).filter(Boolean))]}
      onClose={() => setCreating(false)} onSaved={(item) => { onItem(item); change({ mapped: item.id }); setCreating(false); }} />}
  </Stack>;
}
