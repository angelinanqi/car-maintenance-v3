"use client";
import { useEffect, useState } from 'react';
import { Button, Field, Input, NativeSelect, Stack, Text, Flex } from '@chakra-ui/react';
import { listAll, request } from '@/api/client.mjs';

export default function ChatGarage({ snapshot, busy, onChanged, onError, onBusyChange }) {
  const [catalogue, setCatalogue] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ id: '', catalogueId: '', name: '', plateNumber: '', mileage: '' });
  const [saving, setSaving] = useState(false);
  useEffect(() => { onBusyChange(saving); }, [saving, onBusyChange]);
  async function addVehicle() {
    setSaving(true);
    try {
      setCatalogue(await listAll('/mobile/vehicle-catalogue', {}, { timeoutMs: 30000 }));
      setForm({ id: crypto.randomUUID(), catalogueId: '', name: '', plateNumber: '', mileage: '' });
      setEditing(true);
    } catch (error) { onError(error.message); }
    finally { setSaving(false); }
  }
  async function save(event) {
    event.preventDefault();
    if (saving || busy) return;
    setSaving(true);
    try {
      const { id, ...fields } = form;
      if (!fields.catalogueId || !/^\d+$/.test(fields.mileage)) throw new Error('Choose a vehicle and enter a nonnegative whole-number odometer reading.');
      await request(`/mobile/me/vehicles/${id}`, { method: 'PUT', body: { ...fields, mileage: Number(fields.mileage) } });
      await request('/mobile/me/active-vehicle', { method: 'PUT', body: { id } });
      setEditing(false);
      await onChanged();
    } catch (error) { onError(error.message); }
    finally { setSaving(false); }
  }
  return <Stack gap={3}>
    <Flex gap={3} align="end" wrap="wrap">
      <Field.Root maxW="340px" disabled={busy || saving}>
        <Field.Label>Your vehicle</Field.Label>
        <NativeSelect.Root><NativeSelect.Field aria-label="Your vehicle" value={snapshot?.activeVehicleId || ''} onChange={async event => {
          setSaving(true);
          try { await request('/mobile/me/active-vehicle', { method: 'PUT', body: { id: event.target.value } }); await onChanged(); }
          catch (error) { onError(error.message); }
          finally { setSaving(false); }
        }}>
          {!snapshot?.vehicles?.length && <option value="">General car assistance</option>}
          {(snapshot?.vehicles || []).map(vehicle => <option key={vehicle.id} value={vehicle.id}>{vehicle.name || vehicle.model} · {vehicle.mileage} km</option>)}
        </NativeSelect.Field><NativeSelect.Indicator /></NativeSelect.Root>
      </Field.Root>
      <Button variant="outline" disabled={busy || saving} onClick={addVehicle}>Add my vehicle</Button>
    </Flex>
    {editing && <Stack as="form" onSubmit={save} borderWidth="1px" p={4} gap={3} maxW="560px">
      <Text fontWeight="semibold">Add to my garage</Text>
      <Field.Root required><Field.Label>Catalogue vehicle</Field.Label><NativeSelect.Root>
        <NativeSelect.Field required aria-label="Catalogue vehicle" value={form.catalogueId} disabled={saving} onChange={event => setForm({ ...form, catalogueId: event.target.value })}>
          <option value="">Choose a vehicle</option>
          {catalogue?.map(vehicle => <option key={vehicle.id} value={vehicle.id}>{vehicle.name} {vehicle.year} {vehicle.engine} {vehicle.variant}</option>)}
        </NativeSelect.Field><NativeSelect.Indicator /></NativeSelect.Root></Field.Root>
      {['name', 'plateNumber', 'mileage'].map(field => <Field.Root key={field} required={field === 'mileage'}>
        <Field.Label>{({ name: 'Nickname', plateNumber: 'Plate number', mileage: 'Odometer (km)' })[field]}</Field.Label>
        <Input aria-label={field} required={field === 'mileage'} disabled={saving} value={form[field]} maxLength={field === 'plateNumber' ? 40 : 200}
          inputMode={field === 'mileage' ? 'numeric' : 'text'} onChange={event => setForm({ ...form, [field]: event.target.value })} />
      </Field.Root>)}
      <Flex gap={2}><Button type="submit" disabled={saving}>Save my vehicle</Button><Button variant="outline" disabled={saving} onClick={() => setEditing(false)}>Cancel</Button></Flex>
    </Stack>}
  </Stack>;
}
