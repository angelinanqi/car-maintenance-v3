"use client";
import { useEffect, useRef, useState } from 'react';
import { Box, Button, Field, Flex, Heading, Input, Spinner, Stack, Text, Textarea } from '@chakra-ui/react';
import { listAll, request as api } from '@/api/client.mjs';
import TipTapEditor from '@/components/editor/TipTapEditor';
import ChatNotes from './ChatNotes';

function sections(guide) {
  const document = new DOMParser().parseFromString(guide.content, 'text/html');
  return (guide.exploration?.steps || []).flatMap(step => {
    const heading = [...document.querySelectorAll('h2[data-section-id]')].find(node => node.getAttribute('data-section-id') === step.section_id);
    if (!heading) return [];
    let html = heading.outerHTML, next = heading.nextSibling;
    while (next && next.nodeName !== 'H2') { html += next.outerHTML || next.textContent; next = next.nextSibling; }
    return [{ ...step, html, title: heading.textContent }];
  });
}

export default function ChatTools({ request, restoredActivity, snapshot, session, busy, onBusy, onActivity, onSnapshot, onStartingPoints, onExplanation, onAsk }) {
  const [panel, setPanel] = useState(null);
  const [guide, setGuide] = useState(null);
  const [step, setStep] = useState(0);
  const [plan, setPlan] = useState(null);
  const [items, setItems] = useState([]);
  const [guides, setGuides] = useState([]);
  const [notes, setNotes] = useState(null);
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [answer, setAnswer] = useState(null);
  const [example, setExample] = useState(false);
  const working = useRef(false);
  const alive = useRef(true);
  const appliedRestore = useRef(null);
  const vehicleId = snapshot.activeVehicleId;
  const steps = guide ? sections(guide) : [];
  const current = steps[step];
  useEffect(() => { alive.current = true; return () => { alive.current = false; onBusy(false); }; }, [onBusy]);

  async function perform(action) {
    if (working.current || busy) return;
    working.current = true; setLoading(true); onBusy(true); setError(''); setStatus('');
    try { await action(); } catch (cause) { if (alive.current) setError(cause.message); }
    finally { if (alive.current) { working.current = false; setLoading(false); onBusy(false); } }
  }
  async function progress(lesson, index, completed) {
    const parts = sections(lesson);
    await api(`/mobile/me/progress/${lesson.id}`, { method: 'PUT', body: {
      guide_revision: lesson.updated_at, ...(parts[index] ? { current_step_id: parts[index].id } : {}),
      ...(completed === undefined ? {} : { completed }),
    } });
    try { await onSnapshot(); await onStartingPoints(); }
    catch { throw new Error('Your progress was saved, but could not be refreshed. Refresh starting points before retrying.'); }
  }
  async function setActivity(value) {
    if (!alive.current) return;
    onActivity(value);
    if (session.created) await api(`/chat/sessions/${session.id}/activity`, { method: 'PUT', body: { activity: value } });
  }
  async function openGuide(id, stepId) {
    const lesson = await api(`/guides/${id}`);
    if (!alive.current) return;
    const found = sections(lesson).findIndex(section => section.id === stepId);
    const index = found < 0 ? 0 : found;
    setGuide(lesson); setStep(index); setPanel('guide'); setPlan(null); setAnswer(null); setExample(false);
    await progress(lesson, index);
    await setActivity({ kind: 'guide', guide_id: lesson.id, revision: lesson.updated_at,
      ...(sections(lesson)[index] ? { step_id: sections(lesson)[index].id } : {}) });
  }
  async function openPlan(id) {
    if (!vehicleId) throw new Error('Add or select a vehicle to prepare its service plan.');
    const result = id ? await api(`/mobile/me/service-plans/${id}`)
      : await api('/mobile/me/service-plans/preview', { method: 'POST', body: { vehicle_id: vehicleId } });
    if (alive.current) { setPlan(result); setGuide(null); setPanel('plan'); onActivity(result.id ? { kind: 'plan', plan_id: result.id, revision: result.fingerprint } : null); }
  }
  async function savePlan() {
    if (!plan || plan.stale) throw new Error('Refresh this proposal before saving or using it.');
    const result = plan.id ? plan : await api('/mobile/me/service-plans', { method: 'POST', body: { vehicle_id: vehicleId, fingerprint: plan.fingerprint } });
    if (alive.current) setPlan(result);
    await setActivity({ kind: 'plan', plan_id: result.id, revision: result.fingerprint });
    return result;
  }
  async function saved() { const result = await listAll('/mobile/me/saved-items'); if (alive.current) { setItems(result.reverse()); setPanel('saved'); } }
  async function selectItem(item) {
    if (item.vehicle_id && item.vehicle_id !== vehicleId) throw new Error('Select the vehicle associated with this saved item, then reopen it.');
    if (item.kind === 'guide') await openGuide(item.guide_id);
    if (item.kind === 'plan') await openPlan(item.plan_id);
    if (item.kind === 'explanation') onExplanation(item);
    if (item.kind === 'notes') { setNotes({ item, key: item.id }); setPanel('notes'); }
  }
  useEffect(() => {
    if (!request) return;
    perform(async () => {
      if (request.kind === 'guide') await openGuide(request.item.id, request.item.stepId);
      else if (request.kind === 'plan') await openPlan();
      else if (request.kind === 'saved') await saved();
      else if (request.kind === 'guides') { const result = await listAll('/guides'); if (alive.current) { setGuides(result); setPanel('guides'); } }
      else if (request.kind === 'explanation') {
        if (!request.item.message_id) throw new Error('This answer cannot be saved yet. Restore the conversation and retry.');
        await api('/mobile/me/saved-items', { method: 'POST', body: { kind: 'explanation', title: request.item.answer.slice(0, 80), message_id: request.item.message_id } });
        if (alive.current) setStatus('Explanation saved.');
      } else if (request.kind === 'note' || request.kind === 'mechanic') {
        setNotes({ mechanic: request.kind === 'mechanic', key: request.id,
          question: [...session.messages].reverse().find(message => message.role === 'user')?.answer || '' }); setPanel('notes');
      } else setPanel(request.kind);
    });
  }, [request]);
  useEffect(() => {
    if (busy || !restoredActivity || appliedRestore.current === restoredActivity) return;
    appliedRestore.current = restoredActivity;
    if (restoredActivity?.kind === 'guide') perform(() => openGuide(restoredActivity.guide_id, restoredActivity.step_id));
    if (restoredActivity?.kind === 'plan') perform(() => openPlan(restoredActivity.plan_id));
  }, [restoredActivity, busy]);

  return <Stack gap={3}>
    {loading && <Spinner size="sm" />}
    {error && <Text role="alert">{error}</Text>}{status && <Text role="status">{status}</Text>}
    {panel && <Button alignSelf="start" variant="ghost" disabled={loading || busy} onClick={() => setPanel(null)}>Return to conversation</Button>}
    {panel === 'guides' && <Stack><Heading size="md">Learning Guides</Heading>{guides.map(item => <Button key={item.id} variant="outline" disabled={loading || busy} onClick={() => perform(() => openGuide(item.id))}>{item.title}</Button>)}</Stack>}
    {panel === 'guide' && guide && <Stack>
      <Heading size="md">{guide.title}</Heading><Text>{steps.length ? `${step + 1} of ${steps.length} sections` : 'Published guide'}</Text>
      <TipTapEditor key={`${guide.id}:${guide.updated_at}:${step}`} readOnly content={current?.html || guide.content} />
      {current?.example_html && <><Button variant="outline" onClick={() => setExample(value => !value)}>{example ? 'Hide example' : 'Show an example'}</Button>{example && <TipTapEditor key={`example:${guide.id}:${step}`} readOnly content={current.example_html} />}</>}
      {current?.activity && <Stack><Text>{current.activity.prompt}</Text>{current.activity.options.map(option => <Button key={option.id} variant="outline" onClick={() => setAnswer(option.id)}>{option.text}</Button>)}
        {answer && <Text role="status">{current.activity.options.find(option => option.id === answer)?.feedback}</Text>}
      </Stack>}
      <Flex gap={2} wrap="wrap">
        <Button disabled={loading || busy} onClick={() => onAsk()}>Ask about this</Button>
        <Button variant="outline" disabled={loading || busy} onClick={() => onAsk('simplify')}>Explain more simply</Button>
        <Button variant="outline" disabled={loading || busy} onClick={() => perform(async () => {
          await api('/mobile/me/saved-items', { method: 'POST', body: { kind: 'guide', guide_id: guide.id, title: guide.title } }); setStatus('Guide saved.');
        })}>Save guide</Button>
        {step > 0 && <Button disabled={loading || busy} onClick={() => perform(() => openGuide(guide.id, steps[step - 1].id))}>Previous section</Button>}
        {step < steps.length - 1 ? <Button disabled={loading || busy} onClick={() => perform(() => openGuide(guide.id, steps[step + 1].id))}>Continue</Button>
          : <Button disabled={loading || busy} onClick={() => perform(async () => { await progress(guide, step, true); setStatus('Guide marked as completed.'); })}>Mark as completed</Button>}
      </Flex>
    </Stack>}
    {panel === 'plan' && plan && <Stack>
      <Heading size="md">Your Next Service</Heading><Text>{plan.snapshot.mileage} km recorded · Prepared {plan.snapshot.as_of} · {plan.snapshot.total_tasks} tracked items</Text>
      {plan.stale && <Text role="alert">Your records, schedule or date changed. Refresh this proposal before using it.</Text>}
      {Object.entries(plan.snapshot.groups).map(([group, entries]) => <Box key={group} borderWidth="1px" p={3}>
        <Heading size="sm">{({ due: 'Due Now', discuss: 'Discuss at This Visit', check: 'Needs Checking', upcoming: 'Other Tracked Items' })[group]}</Heading>
        {entries.map(item => <Stack key={item.task_id} data-testid={`plan-item-${item.task_id}`} py={3}>
          <Text fontWeight="semibold">{item.title} · {item.action} · {item.status.label}</Text>
          <Text>{item.schedule_source === 'manufacturer' ? 'Published manufacturer schedule' : item.schedule_source === 'custom' ? 'Your custom reminder' : 'No timing rule'}</Text>
          {item.status.nextKm != null && <Text>Due mileage: {item.status.nextKm} km</Text>}{item.status.nextDate && <Text>Due date: {item.status.nextDate}</Text>}
          {item.rule?.notes && <Text>{item.rule.notes}</Text>}{item.rule?.conditions && <Text>{item.rule.conditions}</Text>}
          <Flex gap={2}>{item.lesson_ids?.[0] && <Button variant="outline" disabled={busy || loading} onClick={() => perform(() => openGuide(item.lesson_ids[0]))}>Understand this maintenance</Button>}
            <Button variant="outline" disabled={plan.stale || busy || loading} onClick={() => setRecord({ id: crypto.randomUUID(), item, date: new Date().toISOString().slice(0, 10), mileage: String(plan.snapshot.mileage), notes: '' })}>Record completed work</Button></Flex>
        </Stack>)}
      </Box>)}
      <Flex gap={2} wrap="wrap">
        <Button disabled={loading || busy || plan.stale} onClick={() => perform(async () => {
          const result = await savePlan(); await api('/mobile/me/saved-items', { method: 'POST', body: { kind: 'plan', title: 'My next service', plan_id: result.id } }); setStatus('Plan saved.');
        })}>Save plan</Button>
        <Button variant="outline" disabled={loading || busy} onClick={() => perform(() => openPlan())}>Refresh plan</Button>
        <Button variant="outline" disabled={loading || busy || plan.stale} onClick={() => perform(async () => { const result = await savePlan(); await setActivity({ kind: 'plan', plan_id: result.id, revision: result.fingerprint }); onAsk(); })}>Ask about this plan</Button>
        <Button variant="outline" disabled={loading || busy || plan.stale} onClick={() => perform(async () => {
          const result = await savePlan();
          setNotes({ mechanic: true, key: crypto.randomUUID(), planId: result.id, question: 'Help me prepare questions about my saved service plan.',
            initialNotes: [`Saved service proposal · ${result.snapshot.as_of}`, ...['due', 'discuss', 'check'].flatMap(group => result.snapshot.groups[group].map(item => `${item.title} · ${item.action} · ${item.status.label}`))].join('\n') }); setPanel('notes');
        })}>Prepare mechanic notes</Button>
      </Flex>
    </Stack>}
    {record && <Stack as="form" borderWidth="1px" p={4} onSubmit={event => { event.preventDefault(); perform(async () => {
      if (!/^\d+$/.test(record.mileage) || !record.date) throw new Error('Enter the service date and whole-number mileage.');
      await api(`/mobile/me/records/${record.id}`, { method: 'PUT', body: { id: record.id, vehicleId, taskId: record.item.task_id,
        title: record.item.title, mileage: Number(record.mileage), date: record.date + 'T00:00:00', notes: record.notes } });
      setRecord(null); setStatus('Service record saved.');
      try { await onSnapshot(); await openPlan(); } catch { throw new Error('Service record saved, but its updated proposal could not refresh. Refresh the plan.'); }
    }); }}>
      <Text>Record {record.item.title}</Text>
      <Field.Root><Field.Label>Service date</Field.Label><Input type="date" value={record.date} disabled={loading || busy} onChange={event => setRecord({ ...record, date: event.target.value })} /></Field.Root>
      <Field.Root><Field.Label>Service mileage (km)</Field.Label><Input value={record.mileage} disabled={loading || busy} onChange={event => setRecord({ ...record, mileage: event.target.value })} /></Field.Root>
      <Field.Root><Field.Label>Service notes</Field.Label><Textarea maxLength={10000} value={record.notes} disabled={loading || busy} onChange={event => setRecord({ ...record, notes: event.target.value })} /></Field.Root>
      <Button type="submit" disabled={loading || busy}>Save service record</Button><Button variant="outline" disabled={loading || busy} onClick={() => setRecord(null)}>Cancel service record</Button>
    </Stack>}
    {panel === 'saved' && <Stack><Heading size="md">Saved</Heading>{!items.length && <Text>No saved items yet.</Text>}{items.map(item => <Flex key={item.id} gap={2} wrap="wrap">
      <Button variant="outline" disabled={!item.available || loading || busy} onClick={() => perform(() => selectItem(item))}>{item.title}{!item.available ? ' · Original content is no longer available' : ''}</Button>
      <Button variant="ghost" disabled={loading || busy} onClick={() => perform(async () => { await api(`/mobile/me/saved-items/${item.id}`, { method: 'DELETE' }); await saved(); })}>Remove {item.title}</Button>
    </Flex>)}</Stack>}
    {panel === 'notes' && notes && <ChatNotes key={notes.key} item={notes.item} mechanic={notes.mechanic} planId={notes.planId} initialQuestion={notes.question}
      initialNotes={notes.initialNotes} vehicleId={vehicleId} session={session} disabled={busy || loading} onBusy={onBusy} />}
    {panel === 'maintenance' && <Stack><Heading size="md">Your Saved Maintenance</Heading>
      {snapshot.tasks.filter(task => task.vehicleId === vehicleId).map(task => <Text key={task.id}>{task.title} · {task.status?.label || 'Information required'}</Text>)}
      {snapshot.records.filter(item => item.vehicleId === vehicleId).map(item => <Text key={item.id}>{item.title} · {item.date} · {item.mileage} km · {item.notes}</Text>)}
    </Stack>}
    {panel === 'emergency' && <Stack><Text>If anyone is in immediate danger, call 999. Move to safety if possible.</Text><Button asChild><a href="/admin/emergency">Open emergency guidance</a></Button></Stack>}
  </Stack>;
}
