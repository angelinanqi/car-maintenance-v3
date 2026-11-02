"use client";
import { useRef, useState } from 'react';
import { Button, Field, Flex, Heading, Stack, Text, Textarea } from '@chakra-ui/react';
import { request } from '@/api/client.mjs';
import useUnsavedChanges from '@/components/admin/useUnsavedChanges';

export default function ChatNotes({ item, vehicleId, session, initialQuestion = '', initialNotes = '', mechanic = false, planId, disabled, onBusy }) {
  const [question, setQuestion] = useState(initialQuestion);
  const [text, setText] = useState(item?.payload?.text || initialNotes);
  const [savedText, setSavedText] = useState(item?.payload?.text || '');
  const [savedId, setSavedId] = useState(item?.id || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [places, setPlaces] = useState(null);
  const id = useRef(null);
  const initialSave = useRef(null);
  const working = useRef(false);
  useUnsavedChanges(text !== savedText);

  async function perform(action) {
    if (working.current || disabled) return;
    working.current = true; setBusy(true); onBusy(true); setError(''); setStatus('');
    try { await action(); } catch (cause) { setError(cause.message || 'This action could not complete. Your notes are kept.'); }
    finally { working.current = false; setBusy(false); onBusy(false); }
  }
  function prepare() {
    if (text.trim() && !window.confirm('Replace your discussion notes? Copy or save them first if you want to keep them.')) return;
    perform(async () => {
      if (!question.trim() || question.length > 4000) throw new Error('Describe your concern within 4000 characters.');
      const data = await request('/chat/mechanic-questions', { method: 'POST', body: {
        question: question.trim(), vehicle_id: vehicleId || null,
        ...(session.created ? { session_id: session.id, session_token: session.token } : {}),
        ...(planId ? { plan_id: planId } : {}),
      } });
      if (!Array.isArray(data.questions) || data.questions.length < 3 || data.questions.length > 5) throw new Error('The question list could not be read. Retry preparing questions.');
      setText([initialNotes, 'Questions for a mechanic', data.vehicle_summary, data.concern_summary,
        ...data.questions.flatMap((entry, index) => [`${index + 1}. ${entry.question}`, `Why ask: ${entry.reason}`]),
        'Details to bring:', ...(data.details_to_note || [])].filter(Boolean).join('\n\n'));
      setStatus(data.tailored ? 'Tailored questions prepared. Review before sharing.' : 'General administrator checklist. Adapt it to your concern.');
    });
  }
  function save() {
    perform(async () => {
      if (!text.trim() || text.length > 20000) throw new Error('Enter notes within 20000 characters.');
      const title = item?.title || (mechanic ? 'Questions for my mechanic' : 'Chat notes');
      let identity = savedId;
      if (!identity) {
        id.current ||= crypto.randomUUID();
        initialSave.current ||= { id: id.current, kind: 'notes', title, vehicle_id: vehicleId || null,
          ...(planId ? { plan_id: planId } : {}), text };
        const saved = await request('/mobile/me/saved-items', { method: 'POST', body: initialSave.current });
        identity = saved.id; setSavedId(identity);
      }
      if (savedId || initialSave.current?.text !== text) {
        await request(`/mobile/me/saved-items/${identity}`, { method: 'PATCH', body: { title, text } });
      }
      setSavedText(text); setStatus('Notes saved.');
    });
  }
  function nearby() {
    perform(async () => {
      if (!navigator.geolocation) throw new Error('Location is unavailable in this browser. Enable location access and retry.');
      const position = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 15000, maximumAge: 60000 }));
      const data = await request('/emergency/nearby', { method: 'POST', body: {
        latitude: position.coords.latitude, longitude: position.coords.longitude, service: 'mechanic', radius_metres: 5000,
      } });
      setPlaces(data.places);
    });
  }
  return <Stack gap={3}>
    <Heading size="md">{mechanic ? 'Prepare for a Mechanic' : 'Your Notes'}</Heading>
    {mechanic && <><Field.Root><Field.Label>What would you like clarified?</Field.Label>
      <Textarea value={question} maxLength={4000} disabled={busy || disabled} onChange={event => setQuestion(event.target.value)} />
    </Field.Root><Button alignSelf="start" disabled={busy || disabled} onClick={prepare}>Prepare my questions</Button></>}
    <Field.Root><Field.Label>Discussion notes</Field.Label><Textarea value={text} maxLength={20000} rows={8} disabled={busy || disabled} onChange={event => setText(event.target.value)} /></Field.Root>
    <Flex gap={2} wrap="wrap">
      <Button disabled={busy || disabled} onClick={save}>Save notes</Button>
      <Button variant="outline" disabled={busy || disabled || !text.trim()} onClick={() => perform(async () => {
        await navigator.clipboard.writeText(text); setStatus('Notes copied.');
      })}>Copy discussion notes</Button>
      {mechanic && <Button variant="outline" disabled={busy || disabled} onClick={nearby}>Find nearby workshops</Button>}
    </Flex>
    {status && <Text role="status">{status}</Text>}
    {error && <Text role="alert">{error}</Text>}
    {places && <Stack><Text>Powered by Google. Call to confirm availability; your notes are not sent to workshops.</Text>
      {!places.length && <Text>No workshops were found. Try again from another location.</Text>}
      {places.map(place => <Stack key={place.id} borderWidth="1px" p={3}>
        <Text fontWeight="semibold">{place.name}</Text><Text>{place.address} · {place.distance_metres} m · {place.business_status}</Text>
        <a target="_blank" rel="noopener noreferrer" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name + ' ' + place.address)}&query_place_id=${encodeURIComponent(place.id)}`}>Open map</a>
        {/^\+?[\d ()-]{3,30}$/.test(place.phone) && <a href={'tel:' + place.phone.replace(/[^\d+]/g, '')}>Call {place.phone}</a>}
        {place.attributions?.map((attribution, index) => <Text key={index} fontSize="sm">{attribution.provider}</Text>)}
      </Stack>)}
    </Stack>}
  </Stack>;
}
