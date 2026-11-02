"use client";
import { useEffect, useState } from 'react';
import { Box, Button, Flex, Heading, Input, Stack, Text } from '@chakra-ui/react';
import { Checkbox } from '@/components/ui/checkbox';
import { AdminSelect } from './NativeControls';
import FormField from './FormField';
import type { MaintenanceItem, Schedule, ScheduleEntry } from '@/api/admin';

export default function FrequencyTools({ entries, schedules, items, disabled, onChange }: {
  entries: ScheduleEntry[]; schedules: Schedule[]; items: MaintenanceItem[]; disabled: boolean;
  onChange: (entries: ScheduleEntry[]) => void;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const [km, setKm] = useState('');
  const [months, setMonths] = useState('');
  const [preset, setPreset] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { setSelected([]); }, [entries.length]);
  const presets = [...new Map(schedules.flatMap(s => s.entries.filter(e => e.rule.type === 'recurring' && (e.rule.distanceKm || e.rule.months)).map(e => {
    const key = `${e.rule.distanceKm || ''}:${e.rule.months || ''}`;
    return [key, { km: e.rule.distanceKm, months: e.rule.months, revision: s.revision }] as const;
  }))).entries()];
  const groups = new Map<string, number[]>();
  entries.forEach((e, i) => {
    const label = e.rule.type === 'recurring' ? `${e.rule.distanceKm || '—'} km / ${e.rule.months || '—'} months`
      : e.rule.type === 'milestone' ? `Milestones: ${e.rule.distanceMilestones.join(', ') || '—'} km / ${e.rule.monthMilestones.join(', ') || '—'} months` : 'Conditional guidance';
    groups.set(label, [...(groups.get(label) || []), i]);
  });
  return <Box borderWidth="1px" p={4} borderRadius="md" mb={4}><Stack gap={3}>
    <Heading size="sm">Apply a Frequency to Several Items</Heading>
    <Text fontSize="sm">Choose items and enter a recurring interval. Source references, actions and conditions stay with each item.</Text>
    {entries.map((entry, index) => <Checkbox key={index} disabled={disabled} checked={selected.includes(index)} onCheckedChange={e => setSelected(e.checked === true ? [...selected, index] : selected.filter(i => i !== index))}>{items.find(i => i.id === entry.itemId)?.title || `Rule ${index + 1}`} · {entry.action}</Checkbox>)}
    {presets.length > 0 && <>
      <FormField label="Previously used for this vehicle"><AdminSelect disabled={disabled} value={preset} onChange={e => setPreset(e.target.value)}><option value="">Choose an interval to reuse</option>{presets.map(([key, value]) => <option key={key} value={key}>{value.km || '—'} km / {value.months || '—'} months · revision {value.revision}</option>)}</AdminSelect></FormField>
      <Button variant="outline" disabled={disabled || !preset} onClick={() => { const value = presets.find(([key]) => key === preset)?.[1]; if (value) { setKm(value.km?.toString() || ''); setMonths(value.months?.toString() || ''); } }}>Use these interval values</Button>
    </>}
    <Flex gap={2}><FormField label="Bulk distance interval (km)"><Input type="number" min={1} disabled={disabled} value={km} onChange={e => setKm(e.target.value)} /></FormField><FormField label="Bulk time interval (months)"><Input type="number" min={1} disabled={disabled} value={months} onChange={e => setMonths(e.target.value)} /></FormField></Flex>
    {error && <Text role="alert" color="red.700">{error}</Text>}
    <Button disabled={disabled || !selected.length} onClick={() => {
      if ((!km && !months) || [km, months].some(v => v && (!Number.isSafeInteger(Number(v)) || Number(v) <= 0))) { setError('Enter at least one positive whole-number interval.'); return; }
      setError('');
      onChange(entries.map((entry, index) => selected.includes(index) ? { ...entry, rule: { ...entry.rule,
        type: 'recurring', distanceKm: km ? Number(km) : null, months: months ? Number(months) : null,
        distanceMilestones: [], monthMilestones: [], vehicleStartDate: null,
      } } : entry));
    }}>Apply interval to {selected.length} selected items</Button>
    <Box as="details"><Box as="summary" cursor="pointer">Review Items Grouped by Frequency</Box><Stack mt={2}>{[...groups].map(([label, indices]) => <Flex key={label} gap={2} wrap="wrap"><Text>{label} · {indices.length} items</Text><Button size="sm" variant="outline" disabled={disabled} onClick={() => setSelected(indices)}>Select this group</Button></Flex>)}</Stack></Box>
  </Stack></Box>;
}
