"use client";

import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Heading, Input, Stack, Text } from '@chakra-ui/react';
import { Checkbox } from '@/components/ui/checkbox';
import { AdminSelect } from './NativeControls';
import FormField from './FormField';
import MaintenanceItemEditor from './MaintenanceItemEditor';
import type { MaintenanceItem, SourceDocument } from '@/api/admin';
import { loadReview, updateReview, type Review, type Selection, type Suggestion, type DetectedTable } from '@/api/maintenanceAssistance';

export default function MaintenanceAssistance({ document, items, onItem, onNavigate, onImport, disabled, onDirty }: {
  document: SourceDocument; items: MaintenanceItem[]; onItem: (item: MaintenanceItem) => void;
  onNavigate: (page: number) => void; onImport: (review: Review, suggestions: Suggestion[]) => void;
  disabled: boolean; onDirty: (dirty: boolean) => void;
}) {
  const [review, setReview] = useState<Review | null>(null);
  const [choices, setChoices] = useState<Selection[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [tablePage, setTablePage] = useState(0);
  const [suggestionPage, setSuggestionPage] = useState(0);
  const [suggestionFilter, setSuggestionFilter] = useState('all');
  const [expanded, setExpanded] = useState('');
  const [bookmarkTitle, setBookmarkTitle] = useState('');
  const [bookmarkLocation, setBookmarkLocation] = useState('');
  const [manualTable, setManualTable] = useState('');
  const [manualName, setManualName] = useState('');
  const [creating, setCreating] = useState<string | null>(null);
  const [resetRows, setResetRows] = useState(0);
  const [rowDirty, setRowDirty] = useState<Record<string, boolean>>({});
  const alive = useRef(true);
  const activeRequest = useRef(false);
  const selectionDirty = !!review && JSON.stringify(choices) !== JSON.stringify(review.selections);
  const dirty = selectionDirty || Object.values(rowDirty).some(Boolean) || !!manualName || !!bookmarkTitle || !!bookmarkLocation;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    loadReview(document.id, document.source_revision, controller.signal)
      .then(value => { if (alive.current) { setReview(value); setChoices(value.selections); } })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (alive.current) setLoading(false); });
    return () => { alive.current = false; controller.abort(); onDirty(false); };
  }, [document.id, document.source_revision, onDirty]);

  async function mutate(path: string, method: string, body: object = {}, success?: () => void) {
    if (!review || activeRequest.current) return;
    activeRequest.current = true; setBusy(true); setError(''); setNotice('');
    try {
      const next = await updateReview(review, path, method, body);
      if (alive.current) { setReview(next); if (path === '/confirmation' || !selectionDirty) setChoices(next.selections); setNotice('Review saved.'); success?.(); }
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { activeRequest.current = false; if (alive.current) setBusy(false); }
  }
  async function reload() {
    if (dirty && !window.confirm('Discard unsaved review edits and reload?')) return;
    setLoading(true); setError('');
    try {
      const next = await loadReview(document.id, document.source_revision);
      if (alive.current) { setReview(next); setChoices(next.selections); setRowDirty({}); setResetRows(v => v + 1); setManualName(''); setBookmarkTitle(''); setBookmarkLocation(''); }
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { if (alive.current) setLoading(false); }
  }
  function updateChoice(table: DetectedTable, columns: number[], excluded_rows: number[]) {
    setChoices(previous => [...previous.filter(c => c.table_id !== table.table_id),
      { table_id: table.table_id, confirmed: true as const, columns, excluded_rows }].sort((a, b) => a.table_id.localeCompare(b.table_id)));
  }
  const locked = busy || disabled || loading;
  const tables = (review?.catalogue.tables || []).filter(t =>
    (filter === 'all' || t.ranking.classification === filter) &&
    [t.title, ...t.source.cells.map(c => c.text)].join(' ').toLowerCase().includes(search.toLowerCase()));
  const suggestions = (review?.suggestions || []).filter(s => suggestionFilter === 'all' || s.status === suggestionFilter);
  const ready = (review?.suggestions || []).filter(s => s.status === 'accepted' && s.mapped_item_id);
  return <Box borderWidth="1px" borderRadius="md" p={4} mb={5}>
    <Stack gap={4}>
      <Heading size="md">Find maintenance items in this source</Heading>
      <Text>Confirm tables and item columns, review suggested names, then add accepted items to your schedule. Enter frequencies from the original source.</Text>
      {loading && <Text role="status">Loading detected tables…</Text>}
      {error && <Text role="alert" color="red.700">{error}</Text>}
      {notice && <Text role="status" color="green.700">{notice}</Text>}
      <Button alignSelf="start" variant="outline" disabled={busy || loading} onClick={reload}>Reload extraction review</Button>
      {review && <>
        {!review.catalogue.extraction_available && <Text>No completed extraction is available. Process this source in Documents, or add a manual bookmark below.</Text>}
        <Flex gap={2} wrap="wrap">
          <Input aria-label="Search detected tables" placeholder="Search table titles or content" value={search} onChange={e => { setSearch(e.target.value); setTablePage(0); }} />
          <AdminSelect aria-label="Table relevance" value={filter} onChange={e => { setFilter(e.target.value); setTablePage(0); }}>
            <option value="all">All detected tables</option><option value="likely">Likely maintenance schedules</option><option value="possible">Possible matches</option><option value="other">Other tables</option>
          </AdminSelect>
        </Flex>
        <Text>{tables.length} tables · {choices.length} selected</Text>
        {!tables.length && <Text>No matching tables. Try another filter or add a manual bookmark.</Text>}
        {tables.slice(tablePage * 10, tablePage * 10 + 10).map(table => {
          const choice = choices.find(c => c.table_id === table.table_id);
          const columns = [...new Set(table.source.cells.map(c => c.column))].sort((a, b) => a - b);
          return <Box key={table.table_id} borderWidth="1px" p={3} borderRadius="md">
            <Stack gap={2}>
              <Checkbox disabled={locked} checked={!!choice} onCheckedChange={e => {
                if (e.checked === true) updateChoice(table, [], []);
                else setChoices(choices.filter(c => c.table_id !== table.table_id));
              }}>Confirm {table.title || table.table_id} as a maintenance table</Checkbox>
              <Text fontSize="sm">{table.ranking.classification} · {table.ranking.reasons.join(', ') || 'No maintenance signals'} · {table.pages.length ? `Pages ${table.pages.join(', ')}` : document.source_type === 'md' ? 'Markdown section' : 'Page not detected'}</Text>
              <Flex gap={2} wrap="wrap">
                <Button size="sm" variant="outline" onClick={() => setExpanded(expanded === table.table_id ? '' : table.table_id)}>{expanded === table.table_id ? 'Hide table' : 'Inspect table'}</Button>
                {table.pages.map(page => <Button key={page} size="sm" variant="outline" onClick={() => onNavigate(page)}>Open page {page}</Button>)}
              </Flex>
              {(expanded === table.table_id || !!choice) && <>
                {choice && <Box><Text fontWeight="semibold">Item description columns (select at least one)</Text><Flex gap={3} wrap="wrap">{columns.map(column => <Checkbox key={column} disabled={locked} checked={choice.columns.includes(column)} onCheckedChange={e => updateChoice(table,
                  e.checked === true ? [...choice.columns, column].sort((a, b) => a - b) : choice.columns.filter(c => c !== column), choice.excluded_rows)}>Column {column + 1}</Checkbox>)}</Flex></Box>}
                <TableEvidence table={table} selection={choice} disabled={locked} onExclude={row => choice && updateChoice(table, choice.columns,
                  choice.excluded_rows.includes(row) ? choice.excluded_rows.filter(r => r !== row) : [...choice.excluded_rows, row].sort((a, b) => a - b))} />
                {table.uncertainty.length > 0 && <Text fontSize="sm" color="orange.800">Review needed: {table.uncertainty.map(s => s.replaceAll('_', ' ')).join('; ')}</Text>}
                {[...(table.source.context || []), ...(table.source.notes || [])].map((text, i) => <Text key={i} whiteSpace="pre-wrap" fontSize="sm">{text}</Text>)}
              </>}
            </Stack>
          </Box>;
        })}
        <Pager page={tablePage} count={tables.length} size={10} onChange={setTablePage} />
        <Flex gap={2} wrap="wrap">
          <Button disabled={locked || !selectionDirty || Object.values(rowDirty).some(Boolean) || choices.some(c => !c.columns.length)} onClick={() => mutate('/confirmation', 'PUT', { tables: choices })}>Save table confirmation</Button>
          <Button variant="outline" disabled={locked || selectionDirty || !review.selections.length || Object.values(rowDirty).some(Boolean)} onClick={() => mutate('/suggestions', 'POST', {}, () => setSuggestionPage(0))}>Extract item suggestions</Button>
        </Flex>
        {selectionDirty && <Text fontSize="sm">Save your table and column choices before extracting items.</Text>}
        <Box as="section" borderTopWidth="1px" pt={3}>
          <Heading size="sm" mb={2}>Manual table bookmark</Heading>
          <FormField label="Bookmark title"><Input disabled={locked} value={bookmarkTitle} maxLength={500} onChange={e => setBookmarkTitle(e.target.value)} /></FormField>
          <FormField label={document.source_type === 'pdf' ? 'PDF page number' : 'Markdown section heading'}><Input disabled={locked} type={document.source_type === 'pdf' ? 'number' : 'text'} min={1} value={bookmarkLocation} onChange={e => setBookmarkLocation(e.target.value)} /></FormField>
          <Button mt={2} variant="outline" disabled={locked || !bookmarkTitle.trim() || !bookmarkLocation.trim() || selectionDirty} onClick={() => mutate('/bookmarks', 'POST', {
            title: bookmarkTitle, ...(document.source_type === 'pdf' ? { page: Number(bookmarkLocation) } : { section: bookmarkLocation })
          }, () => { setBookmarkTitle(''); setBookmarkLocation(''); })}>Save bookmark</Button>
          {review.bookmarks.map(b => <Flex key={b.table_id} gap={2} mt={2} align="center"><Text>{b.title} · {b.page ? `Page ${b.page}` : b.section}</Text>{b.page && <Button size="sm" variant="outline" onClick={() => onNavigate(b.page!)}>Open page {b.page}</Button>}</Flex>)}
        </Box>
        <Heading size="sm">Review item suggestions</Heading>
        <AdminSelect aria-label="Suggestion status" disabled={Object.values(rowDirty).some(Boolean)} value={suggestionFilter} onChange={e => { setSuggestionFilter(e.target.value); setSuggestionPage(0); }}><option value="all">All suggestions</option><option value="suggested">Awaiting review</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></AdminSelect>
        {suggestions.slice(suggestionPage * 20, suggestionPage * 20 + 20).map(s => <SuggestionRow key={`${s.suggestion_id}:${resetRows}`} suggestion={s} items={items} disabled={locked}
          onSave={body => mutate(`/suggestions/${encodeURIComponent(s.suggestion_id)}`, 'PATCH', body, () => setRowDirty(previous => ({ ...previous, [s.suggestion_id]: false })))}
          onDirty={value => setRowDirty(previous => previous[s.suggestion_id] === value ? previous : { ...previous, [s.suggestion_id]: value })}
          onCreate={name => setCreating(name)} />)}
        {!suggestions.length && <Text>No suggestions in this view. Confirm tables and extract items, or add an item manually.</Text>}
        <Pager disabled={Object.values(rowDirty).some(Boolean)} page={suggestionPage} count={suggestions.length} size={20} onChange={setSuggestionPage} />
        <FormField label="Source for a manual item"><AdminSelect disabled={locked} value={manualTable} onChange={e => setManualTable(e.target.value)}><option value="">Select a confirmed table or bookmark</option>{review.selections.map(s => <option key={s.table_id} value={s.table_id}>{review.catalogue.tables.find(t => t.table_id === s.table_id)?.title || s.table_id}</option>)}{review.bookmarks.map(b => <option key={b.table_id} value={b.table_id}>{b.title}</option>)}</AdminSelect></FormField>
        <FormField label="Manual item name"><Input disabled={locked} maxLength={500} value={manualName} onChange={e => setManualName(e.target.value)} /></FormField>
        <Button variant="outline" disabled={locked || selectionDirty || !manualTable || !manualName.trim()} onClick={() => mutate('/manual-items', 'POST', { table_id: manualTable, name: manualName }, () => setManualName(''))}>Add manual suggestion</Button>
        <Button disabled={locked || dirty || !ready.length} onClick={() => onImport(review, ready)}>Add {ready.length} accepted mapped items to draft</Button>
        <Text fontSize="sm">Accepted items need a standard catalogue mapping before import. Existing items in this draft are skipped. Frequencies remain for you to enter.</Text>
      </>}
    </Stack>
    {creating !== null && <MaintenanceItemEditor initialTitle={creating} categories={[...new Set(items.map(i => i.category).filter(Boolean))]} onClose={() => setCreating(null)} onSaved={item => { onItem(item); setCreating(null); setNotice('Standard item created. Select it in the mapping and save your review.'); }} />}
  </Box>;
}

function Pager({ page, count, size, onChange, disabled = false }: { page: number; count: number; size: number; onChange: (n: number) => void; disabled?: boolean }) {
  if (count <= size) return null;
  return <Flex gap={2} align="center"><Button size="sm" variant="outline" disabled={disabled || !page} onClick={() => onChange(page - 1)}>Previous</Button><Text>Page {page + 1} of {Math.ceil(count / size)}</Text><Button size="sm" variant="outline" disabled={disabled || (page + 1) * size >= count} onClick={() => onChange(page + 1)}>Next</Button></Flex>;
}

function TableEvidence({ table, selection, disabled, onExclude }: { table: DetectedTable; selection?: Selection; disabled: boolean; onExclude: (row: number) => void }) {
  const rows = [...new Set(table.source.cells.map(c => c.row))].sort((a, b) => a - b);
  return <Box overflowX="auto" maxH="420px" overflowY="auto">
    <table style={{ borderCollapse: 'collapse', width: '100%' }}>
      <caption>{table.title || 'Extracted table'} — check against the original source</caption>
      <tbody>{rows.map(row => <tr key={row} style={{ opacity: selection?.excluded_rows.includes(row) ? .5 : 1 }}>
        <td style={{ border: '1px solid #aab4bf', padding: 6 }}>{selection ? <Checkbox disabled={disabled} checked={selection.excluded_rows.includes(row)} onCheckedChange={() => onExclude(row)}>Exclude row {row + 1}</Checkbox> : `Row ${row + 1}`}</td>
        {table.source.cells.filter(c => c.row === row).sort((a, b) => a.column - b.column).map(cell => <td key={cell.column} rowSpan={cell.rowspan || 1} colSpan={cell.colspan || 1} style={{ border: '1px solid #aab4bf', padding: 6, whiteSpace: 'pre-wrap', fontWeight: cell.header ? 600 : 400, background: selection?.columns.includes(cell.column) ? '#edf8ef' : undefined }}>{cell.text}</td>)}
      </tr>)}</tbody>
    </table>
    {!rows.length && <Text whiteSpace="pre-wrap">{table.source.original_markdown || table.source.original_html || 'No readable cells. Use a manual item.'}</Text>}
  </Box>;
}

function SuggestionRow({ suggestion: s, items, disabled, onSave, onDirty, onCreate }: {
  suggestion: Suggestion; items: MaintenanceItem[]; disabled: boolean;
  onSave: (body: object) => void; onDirty: (value: boolean) => void; onCreate: (name: string) => void;
}) {
  const [name, setName] = useState(s.edited_name || s.suggested_name);
  const [mapped, setMapped] = useState(s.mapped_item_id || '');
  const [status, setStatus] = useState(s.status);
  useEffect(() => { setName(s.edited_name || s.suggested_name); setMapped(s.mapped_item_id || ''); setStatus(s.status); }, [s.edited_name, s.suggested_name, s.mapped_item_id, s.status]);
  const dirty = name !== (s.edited_name || s.suggested_name) || mapped !== (s.mapped_item_id || '') || status !== s.status;
  const dirtyCallback = useRef(onDirty); dirtyCallback.current = onDirty;
  useEffect(() => { dirtyCallback.current(dirty); }, [dirty]);
  useEffect(() => () => dirtyCallback.current(false), []);
  const suggested = new Set(s.catalogue_matches.map(m => m.item_id));
  return <Box borderWidth="1px" borderRadius="md" p={3}><Stack gap={2}>
    <Text fontWeight="semibold">{s.manual ? 'Manual entry' : `Extracted row ${(s.row ?? 0) + 1}`} · {s.status}</Text>
    <Text whiteSpace="pre-wrap">Original: {s.original_text ?? 'Entered manually'}</Text>
    {(s.potential_duplicate || s.uncertainty.length > 0) && <Text fontSize="sm" color="orange.800">{s.potential_duplicate ? 'Possible duplicate. ' : ''}{s.uncertainty.map(s => s.replaceAll('_', ' ')).join('; ')}</Text>}
    <FormField label="Reviewed item name"><Input disabled={disabled} maxLength={500} value={name} onChange={e => setName(e.target.value)} /></FormField>
    <FormField label="Standard item mapping"><AdminSelect disabled={disabled} value={mapped} onChange={e => setMapped(e.target.value)}><option value="">Leave unmapped</option>{[...items].filter(i => i.active || i.id === mapped).sort((a, b) => Number(suggested.has(b.id)) - Number(suggested.has(a.id))).map(item => <option key={item.id} value={item.id}>{suggested.has(item.id) ? 'Suggested: ' : ''}{item.title} · {item.action}{item.category ? ` · ${item.category}` : ''}</option>)}</AdminSelect></FormField>
    <Button alignSelf="start" size="sm" variant="outline" disabled={disabled} onClick={() => onCreate(name)}>Create standard item</Button>
    <FormField label="Review decision"><AdminSelect disabled={disabled} value={status} onChange={e => setStatus(e.target.value as Suggestion['status'])}><option value="suggested">Awaiting review</option><option value="accepted">Accept</option><option value="rejected">Reject</option></AdminSelect></FormField>
    <Button alignSelf="start" disabled={disabled || !dirty || !name.trim()} onClick={() => onSave({ status, edited_name: name, mapped_item_id: mapped || null })}>Save item review</Button>
  </Stack></Box>;
}
