"use client";
import { useEffect, useRef, useState } from 'react';
import { Box, Button, Collapsible, Field, Flex, Grid, Heading, NativeSelect, Spinner, Stack, Text, Textarea } from '@chakra-ui/react';
import AdminLayout from '@/components/layouts/AdminLayout';
import ChatMessage from '@/components/chatbot/ChatMessage';
import ChatSourcePanel from '@/components/chatbot/ChatSourcePanel';
import ChatGarage from '@/components/chatbot/ChatGarage';
import ChatTools from '@/components/chatbot/ChatTools';
import ChatStarterEditor from '@/components/ChatStarterEditor';
import MechanicTemplateEditor from '@/components/MechanicTemplateEditor';
import { useContent } from '@/components/ContentProvider';
import { useSession } from '@/components/SessionProvider';
import { request } from '@/api/client.mjs';
import { createChatSession, resumeChat, sendChatMessage } from '@/api/chat.mjs';
import { newChatSession, readChatRecovery, recoveryKey, restoredChat, writeChatRecovery } from '@/lib/chatRecovery.mjs';

export default function ChatbotPage() {
  const { user } = useSession();
  const { configuration } = useContent();
  const [snapshot, setSnapshot] = useState(null);
  const [mode, setMode] = useState('catalogue');
  const [catalogue, setCatalogue] = useState(null);
  const [catalogueError, setCatalogueError] = useState('');
  const [testVehicle, setTestVehicle] = useState('');
  const [session, setSession] = useState(null);
  const [sessionKey, setSessionKey] = useState(null);
  const [draft, setDraft] = useState('');
  const [starters, setStarters] = useState([]);
  const [discovery, setDiscovery] = useState(null);
  const [activity, setActivity] = useState(null);
  const [restoredActivity, setRestoredActivity] = useState(null);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [restoreFailed, setRestoreFailed] = useState(false);
  const [garageBusy, setGarageBusy] = useState(false);
  const [toolBusy, setToolBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reload, setReload] = useState(0);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [toolRequest, setToolRequest] = useState(null);
  const [workspacePanel, setWorkspacePanel] = useState('sources');
  const [sourceAnswerId, setSourceAnswerId] = useState(null);
  const generation = useRef(0);
  const sending = useRef(false);
  const controller = useRef(null);
  const restoreTarget = useRef(null);
  const input = useRef(null);
  const log = useRef(null);
  const testing = mode === 'catalogue';
  const testScope = testing && testVehicle ? { scope_type: 'vehicle', scope_id: testVehicle } : {};
  const key = user ? (testing ? (testVehicle ? `roadie-admin-test:${user.id}:${testVehicle}` : null)
    : snapshot ? recoveryKey(user.id, snapshot.activeVehicleId) : null) : null;
  const limit = configuration?.chat_max_message_length || 4000;
  const blocked = busy || restoring || garageBusy || toolBusy;

  async function refreshSnapshot() {
    const data = await request('/mobile/me'); setSnapshot(data); return data;
  }
  async function refreshStartingPoints() {
    const results = await Promise.allSettled([request('/mobile/chat-starters'), ...(testing ? [] : [request('/mobile/me/companion')])]);
    if (results[0].status === 'fulfilled') setStarters(results[0].value.questions);
    if (results[1]?.status === 'fulfilled') setDiscovery(results[1].value);
    if (results.some(result => result.status === 'rejected')) setNotice('Some starting points could not refresh. Retry when your connection is available.');
  }
  async function refreshCatalogue() {
    setCatalogueError('');
    try { const data = await request('/knowledge/manage'); setCatalogue([...data.vehicles].sort((a, b) => `${a.name} ${a.year} ${a.engine} ${a.variant}`.localeCompare(`${b.name} ${b.year} ${b.engine} ${b.variant}`))); }
    catch (cause) { setCatalogueError(cause.message); }
  }
  useEffect(() => { refreshCatalogue(); }, [user?.id]);
  useEffect(() => {
    if (testing) return;
    let active = true;
    const abort = new AbortController();
    request('/mobile/me', { signal: abort.signal }).then(data => { if (active) setSnapshot(data); })
      .catch(cause => { if (active) { setError(cause.message); setRestoring(false); } });
    return () => { active = false; abort.abort(); };
  }, [user?.id, testing]);

  useEffect(() => {
    if (!key) {
      controller.current?.abort(); generation.current++;
      setSession(null); setSessionKey(null); setPending(null); setRestoring(false);
      setError(''); setNotice(''); setActivity(null); setRestoredActivity(null);
      return;
    }
    const version = ++generation.current;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    sending.current = false;
    setBusy(false); setRestoring(true); setRestoreFailed(false); setError(''); setNotice('');
    setPending(null); setDraft(''); setActivity(null); setRestoredActivity(null); setSession(null); setSessionKey(key); setSelectedMessage(null); setToolRequest(null);
    const target = restoreTarget.current; restoreTarget.current = null;
    async function restore() {
      try {
        const saved = target || readChatRecovery(localStorage, key);
        if (!saved) { if (version === generation.current) setSession(newChatSession()); return; }
        let data, missing = false;
        try { data = await resumeChat(saved.session_id, { messageId: saved.message_id, signal: abort.signal }); }
        catch (cause) {
          if (cause.status !== 404 || !saved.pending) throw cause;
          missing = true;
          data = { session_id: saved.session_id, session_token: newChatSession().token, messages: [] };
        }
        if (abort.signal.aborted || version !== generation.current) return;
        const restored = restoredChat(data, saved.pending);
        restored.session.created = !missing;
        setSession(restored.session); setPending(restored.pending);
        setRestoredActivity(data.activity || null); setActivity(data.activity || null);
        setSelectedMessage(saved.message_id || null);
        writeChatRecovery(localStorage, key, restored.session.id, restored.pending);
        if (restored.pending) setError('Your last question was interrupted. Retry to recover its answer.');
      } catch (cause) {
        if (!abort.signal.aborted && version === generation.current) { setError(cause.message); setRestoreFailed(true); }
      } finally {
        if (!abort.signal.aborted && version === generation.current) setRestoring(false);
      }
    }
    restore(); refreshStartingPoints();
    return () => { abort.abort(); controller.current?.abort(); generation.current++; };
  }, [key, reload]);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [session?.messages.length, busy]);

  async function send(event, retry = null, assistance = null) {
    event?.preventDefault();
    if (blocked || sending.current || restoreFailed || !session || sessionKey !== key || (!retry && pending)) return;
    const text = retry?.message || draft.trim();
    if (!text || text.length > limit) { setError(`Enter a question within ${limit} characters.`); return; }
    sending.current = true;
    setBusy(true); setError(''); setSelectedMessage(null);
    const version = generation.current;
    const abort = new AbortController(); controller.current = abort;
    const payload = retry || { request_id: crypto.randomUUID(), message: text, session_id: session.id,
      session_token: session.token, ...testScope, ...(activity ? { activity } : {}), ...(assistance ? { assistance } : {}) };
    setPending(payload);
    if (!retry || !session.messages.some(message => message.id === payload.request_id + ':user')) {
      setDraft('');
      setSession(current => ({ ...current, messages: [...current.messages, { id: payload.request_id + ':user', role: 'user', answer: text }] }));
    }
    try {
      writeChatRecovery(localStorage, key, session.id, payload);
      if (!session.created) await createChatSession(session, abort.signal, testScope);
      if (abort.signal.aborted || version !== generation.current) return;
      setSession(current => ({ ...current, created: true }));
      const result = await sendChatMessage(payload, abort.signal);
      if (abort.signal.aborted || version !== generation.current) return;
      setSession(current => ({ ...current, token: result.session_token,
        messages: [...current.messages, { ...result, role: 'assistant', id: result.message_id || crypto.randomUUID() }] }));
      setPending(null);
      if (result.activity_notice) setNotice(result.activity_notice);
      try { writeChatRecovery(localStorage, key, session.id); }
      catch { setNotice('Your answer is saved online. This browser could not update its recovery file; reopening will recover the saved answer.'); }
    } catch (cause) {
      if (!abort.signal.aborted && version === generation.current) {
        setError(cause.message);
        if (cause.status === 403 && cause.message.includes('chat session is not accessible')) setRestoreFailed(true);
      }
    } finally {
      if (version === generation.current) { sending.current = false; setBusy(false); input.current?.focus(); }
    }
  }
  function startNew() {
    if (blocked || (session?.messages.length && !window.confirm('Start a new conversation? The current browser reference and unsent draft will be cleared. Saved server history is retained.'))) return;
    try { localStorage.setItem(key, JSON.stringify({ cleared: true })); setReload(value => value + 1); }
    catch { setError('This browser could not reset its saved conversation. Check storage access and retry.'); }
  }
  function openExplanation(item) {
    if (pending) { setError('Retry your interrupted question or start a new conversation before opening a saved explanation.'); return; }
    if (item.vehicle_id && item.vehicle_id !== snapshot.activeVehicleId) { setError('Select the vehicle associated with this saved item before reopening it.'); return; }
    restoreTarget.current = { session_id: item.payload.session_id, message_id: item.message_id };
    setReload(value => value + 1);
  }
  function showWorkspace(panel) {
    setWorkspacePanel(panel);
    if (window.matchMedia('(max-width: 1279px)').matches) {
      requestAnimationFrame(() => document.getElementById('chat-workspace')?.scrollIntoView({ block: 'start' }));
    }
  }
  function openTool(kind, item = null) { showWorkspace('tools'); setToolRequest({ kind, item, id: crypto.randomUUID() }); }

  return <AdminLayout title="Try the Chatbot" description="Choose a catalogue vehicle to test its answers and inspect the sources returned.">
    <Stack gap={5}>
      <Box bg="white" borderWidth="1px" borderRadius="20px" p={4}>
        <Flex gap={2} mb={4} wrap="wrap">
          <Button aria-pressed={testing} variant={testing ? 'solid' : 'outline'} disabled={busy || toolBusy} onClick={() => { setMode('catalogue'); setWorkspacePanel('sources'); }}>Test a Catalogue Vehicle</Button>
          <Button aria-pressed={!testing} variant={!testing ? 'solid' : 'outline'} disabled={busy || toolBusy} onClick={() => setMode('personal')}>Test My Garage &amp; Records</Button>
        </Flex>
        <Flex justify="space-between" gap={4} align="center" wrap="wrap">
          {testing && <Stack gap={2} flex={1} maxW="640px">
            <Field.Root><Field.Label>Vehicle to test</Field.Label><NativeSelect.Root>
              <NativeSelect.Field aria-label="Vehicle to test" value={testVehicle} disabled={busy || toolBusy || !catalogue} onChange={event => setTestVehicle(event.target.value)}>
                <option value="">{catalogue ? 'Choose a catalogue vehicle' : 'Loading catalogue...'}</option>
                {(catalogue || []).map(vehicle => <option key={vehicle.id} value={vehicle.id} disabled={!vehicle.published || vehicle.active === false}>
                  {[vehicle.name, vehicle.year, vehicle.engine, vehicle.variant].filter(Boolean).join(' · ')}{!vehicle.published ? ' — Unpublished' : vehicle.active === false ? ' — Inactive' : ''}
                </option>)}
              </NativeSelect.Field><NativeSelect.Indicator />
            </NativeSelect.Root></Field.Root>
            <Text color="muted" fontSize="sm">Uses published sources for this vehicle. No personal vehicle, mileage or service records are needed.</Text>
            {catalogueError && <Text role="alert">{catalogueError}</Text>}
            <Button size="sm" variant="plain" alignSelf="start" disabled={busy} onClick={refreshCatalogue}>Refresh Vehicle List</Button>
          </Stack>}
          {!testing && snapshot && <ChatGarage snapshot={snapshot} busy={busy || restoring || toolBusy || !!pending} onChanged={refreshSnapshot} onError={setError} onBusyChange={setGarageBusy} />}
          <Flex gap={2} wrap="wrap">
            <Button size="sm" variant="ghost" disabled={blocked} onClick={refreshStartingPoints}>Refresh Starting Points</Button>
            <Button size="sm" variant="outline" disabled={blocked || !key} onClick={startNew}>New Conversation</Button>
            {!testing && <Button size="sm" variant="outline" colorPalette="red" disabled={blocked || !!pending || restoreFailed} onClick={() => openTool('emergency')}>Emergency Help</Button>}
          </Flex>
        </Flex>
      </Box>
      {notice && <Text role="status">{notice}</Text>}
      {error && <Box role="alert"><Text>{error}</Text>
        {!testing && !snapshot && <Button onClick={() => refreshSnapshot().catch(cause => setError(cause.message))}>Retry Loading My Garage</Button>}
        {restoreFailed && <Button disabled={restoring} onClick={() => setReload(value => value + 1)}>Retry Restore</Button>}
      </Box>}
      <Grid templateColumns={{ base: 'minmax(0, 1fr)', xl: 'minmax(0, 1.5fr) minmax(320px, 1fr)' }} gap={5} alignItems="start">
        <Stack gap={0} minW={0} bg="white" borderWidth="1px" borderRadius="20px" overflow="hidden">
          <Flex px={5} py={4} borderBottomWidth="1px" gap={3} align="center">
            <img src="/branding/roadie_logo.png" alt="" width="36" height="36" />
            <Box><Heading size="md">Your Conversation</Heading><Text color="muted" fontSize="sm">Vehicle guidance with references you can inspect</Text></Box>
          </Flex>
          <Stack ref={log} role="log" aria-label="Conversation" aria-live="polite" tabIndex={0} h={{ base: '55dvh', xl: '58dvh' }} minH="320px" overflowY="auto" p={{ base: 4, md: 5 }} gap={5}>
            {!key && testing && <Stack my="auto" gap={2}><Heading size="lg">Choose a Vehicle to Start</Heading><Text>Select any published catalogue vehicle above to test its chatbot answers.</Text></Stack>}
            {(restoring || busy) && <Flex gap={2} role="status"><Spinner size="sm" /><Text>{restoring ? 'Restoring conversation...' : 'Checking your sources...'}</Text></Flex>}
            {session && sessionKey === key && <>
              {session.messages.length === 0 && !restoring && <Stack align="start" gap={3} my="auto">
                <Heading size="lg">What Would You Like to Know?</Heading>
                <Text color="muted" fontSize="sm">Choose a starting point or ask your own question.</Text>
                {starters.slice(0, 3).map(question => <Button key={question} variant="outline" w="full" justifyContent="start" textAlign="left" disabled={blocked || !!pending} onClick={() => { setDraft(question); input.current?.focus(); }}>{question}</Button>)}
                {!testing && discovery?.resume?.map(item => <Button key={item.guide_id} variant="ghost" disabled={blocked} onClick={() => openTool('guide', { id: item.guide_id, stepId: item.step_id })}>Continue Learning: {item.title}</Button>)}
                {!testing && discovery?.featured?.slice(0, 1).map(item => <Button key={item.id} variant="ghost" disabled={blocked} onClick={() => openTool('guide', item)}>Explore: {item.title}</Button>)}
                <Button size="sm" variant="plain" disabled={blocked} onClick={refreshStartingPoints}>Refresh Starting Points</Button>
              </Stack>}
              {selectedMessage && <Box><Text>Saved Explanation / Historical Answer</Text><Button variant="ghost" onClick={() => setSelectedMessage(null)}>Show Conversation</Button></Box>}
              {session.messages.filter(message => !selectedMessage || message.id === selectedMessage).map(message => <Stack key={message.id} id={'chat-message-' + message.id} align={message.role === 'user' ? 'end' : 'start'} gap={2}>
                <ChatMessage message={message} onMaintenance={testing ? null : () => openTool('maintenance')} onEmergency={testing ? null : () => openTool('emergency')} onGuide={testing || blocked ? null : id => openTool('guide', { id })} />
                {message.role === 'assistant' && <Flex gap={2} wrap="wrap">
                  <Button size="xs" variant="outline" onClick={() => { setSourceAnswerId(message.id); showWorkspace('sources'); }}>Inspect Sources</Button>
                  {!testing && <Button size="xs" variant="ghost" disabled={blocked || !!pending} onClick={() => openTool('explanation', message)}>Save Explanation</Button>}
                  {!testing && <Button size="xs" variant="ghost" disabled={blocked || !!pending} onClick={() => openTool('note', message)}>Add Note</Button>}
                  {!testing && message.suggested_activity === 'service_plan' && <Button size="xs" variant="outline" disabled={blocked || !!pending} onClick={() => openTool('plan')}>Plan My Next Service</Button>}
                </Flex>}
              </Stack>)}
            </>}
          </Stack>
          <Box borderTopWidth="1px" p={4} bg="canvas">
            {pending && !restoreFailed && <Button mb={3} variant="outline" disabled={blocked} onClick={event => send(event, pending)}>Retry Interrupted Reply</Button>}
            <Box as="form" onSubmit={send}>
              <Field.Root><Field.Label>Your Question</Field.Label><Textarea ref={input} aria-label="Message" value={draft} maxLength={limit} rows={3}
                placeholder="Ask about your car..." disabled={!session || restoring || restoreFailed || garageBusy} onChange={event => setDraft(event.target.value)} onKeyDown={event => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(event); }
                }} /></Field.Root>
              <Flex mt={3} justify="space-between" gap={3} align="center" wrap="wrap">
                <Box><Text fontSize="xs" color="muted">{draft.length}/{limit} characters</Text><Text fontSize="xs" color="muted">Enter to send / Shift+Enter for a new line</Text></Box>
                <Button type="submit" disabled={!session || blocked || restoreFailed || !!pending || !draft.trim()}>Send Question</Button>
              </Flex>
            </Box>
            <Text fontSize="xs" color="muted" mt={3}>General guidance, not a diagnosis. Confirm repairs and specifications with a qualified mechanic.</Text>
          </Box>
        </Stack>
        <Stack as="aside" id="chat-workspace" aria-label="Chat Sources and Tools" minW={0} gap={0} borderWidth="1px" bg="white" borderRadius="20px" overflow="hidden">
          <Flex borderBottomWidth="1px" p={2} gap={2}>
            <Button flex={1} variant={workspacePanel === 'sources' ? 'solid' : 'ghost'} aria-pressed={workspacePanel === 'sources'} onClick={() => setWorkspacePanel('sources')}>Sources</Button>
            {!testing && <Button flex={1} variant={workspacePanel === 'tools' ? 'solid' : 'ghost'} aria-pressed={workspacePanel === 'tools'} onClick={() => setWorkspacePanel('tools')}>Your Tools</Button>}
          </Flex>
          <Box p={4} display={workspacePanel === 'sources' ? 'block' : 'none'}>
            <ChatSourcePanel messages={session && sessionKey === key ? session.messages : []} selectedId={sourceAnswerId} onSelect={setSourceAnswerId}
              onFind={id => { setSelectedMessage(null); requestAnimationFrame(() => document.getElementById('chat-message-' + id)?.scrollIntoView({ block: 'nearest' })); }} />
          </Box>
          <Stack p={4} gap={4} display={workspacePanel === 'tools' ? 'flex' : 'none'}>
            <Text fontSize="sm" color="muted">Use the same personal learning, service plans and saved records as the mobile app.</Text>
            <Flex gap={2} wrap="wrap">
              {[['plan', 'Service Plan'], ['mechanic', 'Mechanic Prep'], ['guides', 'Learn'], ['saved', 'Saved Items']].map(([kind, label]) => <Button key={kind} size="sm" variant="outline" disabled={!session || blocked || !!pending || restoreFailed} onClick={() => openTool(kind)}>{label}</Button>)}
            </Flex>
            {!testing && session && sessionKey === key && <ChatTools key={key + ':' + session.id} request={toolRequest} restoredActivity={restoredActivity} snapshot={snapshot}
              session={session} busy={busy || restoring || garageBusy || !!pending || restoreFailed} onBusy={setToolBusy} onActivity={setActivity}
              onSnapshot={refreshSnapshot} onStartingPoints={refreshStartingPoints} onExplanation={openExplanation}
              onAsk={assistance => { if (assistance === 'simplify') send(null, { request_id: crypto.randomUUID(), message: 'Please explain this section more simply.', session_id: session.id, session_token: session.token, activity, assistance }); else input.current?.focus(); }} />}
          </Stack>
        </Stack>
      </Grid>
      <Collapsible.Root><Collapsible.Trigger asChild><Button variant="outline">Manage Shared Chatbot Content</Button></Collapsible.Trigger>
        <Collapsible.Content pt={4}><Text color="muted" fontSize="sm" mb={4}>These settings affect shared starting questions and mechanic preparation content for drivers.</Text><ChatStarterEditor /><MechanicTemplateEditor /></Collapsible.Content>
      </Collapsible.Root>
    </Stack>
  </AdminLayout>;
}
