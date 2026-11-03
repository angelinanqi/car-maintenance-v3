"use client";

import { useEffect, useRef, useState } from 'react';
import { Button, Dialog, Field, Flex, Input, Stack, Text } from '@chakra-ui/react';
import { request } from '@/api/client.mjs';
import { AdminSelect } from './NativeControls';
import { ACTIVE_IMPORTS, importLabel } from '@/lib/websiteImports.mjs';
import useUnsavedChanges from './useUnsavedChanges';

export default function WebsiteArticleModal({ onClose, onAdded, initialJobId = null, onJobChanged }) {
  const [url, setUrl] = useState('');
  const [method, setMethod] = useState('pdf');
  const [media, setMedia] = useState('screen');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [job, setJob] = useState(null);
  const [jobId, setJobId] = useState(initialJobId);
  const [savedDocument, setSavedDocument] = useState(null);
  const [file, setFile] = useState(null);
  const requestKey = useRef(null);
  useUnsavedChanges(Boolean(url) && !jobId && !savedDocument);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer;
    async function poll() {
      try {
        const result = await request(`/website-imports/${jobId}`, { signal: controller.signal, timeoutMs: 15000 });
        if (controller.signal.aborted) return;
        setJob(result); setUrl(result.submitted_url);
        if (ACTIVE_IMPORTS.has(result.status)) timer = setTimeout(poll, 2000);
      } catch (cause) {
        if (!controller.signal.aborted) { setError(cause.message); timer = setTimeout(poll, 5000); }
      }
    }
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, job?.status]);

  function close() {
    if (!saving && (jobId || savedDocument || !url || window.confirm('Discard this website URL?'))) onClose();
  }
  function changed() { requestKey.current = null; setError(''); }
  function acceptJob(result) { setJob(result); setJobId(result.id); onJobChanged?.(); }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true); setError('');
    try {
      if (method === 'text') {
        const document = savedDocument || await request('/documents/website', {
          method: 'POST', body: { url: url.trim() }, timeoutMs: 65000,
        });
        setSavedDocument(document);
        await onAdded(document);
      } else {
        requestKey.current ||= crypto.randomUUID();
        if (method === 'manual') {
          if (!file) throw new Error('Choose a PDF saved from your browser.');
          const body = new FormData();
          body.append('url', url.trim()); body.append('idempotency_key', requestKey.current); body.append('file', file);
          acceptJob(await request('/website-imports/manual', { method: 'POST', body, timeoutMs: 180000 }));
        } else acceptJob(await request('/website-imports', { method: 'POST',
          body: { url: url.trim(), media, idempotency_key: requestKey.current }, timeoutMs: 20000 }));
      }
    } catch (cause) { setError(cause.message); }
    finally { setSaving(false); }
  }

  async function action(name) {
    setSaving(true); setError('');
    try { acceptJob(await request(`/website-imports/${jobId}/${name}`, { method: 'POST', timeoutMs: 20000 })); }
    catch (cause) { setError(cause.message); }
    finally { setSaving(false); }
  }
  async function attachPDF() {
    if (!file) return;
    setSaving(true); setError('');
    try {
      const body = new FormData(); body.append('file', file);
      acceptJob(await request(`/website-imports/${jobId}/manual-pdf`, { method: 'POST', body, timeoutMs: 180000 }));
    } catch (cause) { setError(cause.message); }
    finally { setSaving(false); }
  }
  async function openDocument() {
    setSaving(true); setError('');
    try { await onAdded(await request(`/documents/${job.document_id}`, { timeoutMs: 20000 })); }
    catch (cause) { setError(cause.message); }
    finally { setSaving(false); }
  }
  const stopped = job && ['failed', 'cancelled'].includes(job.status);
  return <Dialog.Root open closeOnInteractOutside={false} closeOnEscape={!saving} onOpenChange={event => !event.open && close()}>
    <Dialog.Backdrop />
    <Dialog.Positioner><Dialog.Content>
      <form onSubmit={submit}>
        <Dialog.Header><Dialog.Title>Import website</Dialog.Title></Dialog.Header>
        <Dialog.Body><Stack gap={4}>
          {!jobId && <>
            <Text>Capture a public webpage as a PDF, then preview and process it through the document workflow.</Text>
            <Field.Root><Field.Label>Import method</Field.Label>
              <AdminSelect value={method} disabled={saving || Boolean(savedDocument)} onChange={event => { setMethod(event.target.value); changed(); }}>
                <option value="pdf">Webpage as PDF (recommended)</option>
                <option value="text">Direct text import</option>
                <option value="manual">Upload a saved PDF with its website URL</option>
              </AdminSelect>
            </Field.Root>
            <Field.Root required><Field.Label>Website URL</Field.Label>
              <Input type="url" required maxLength={2048} value={url} disabled={saving || Boolean(savedDocument)} placeholder="https://example.com/article"
                onChange={event => { setUrl(event.target.value); changed(); }} />
            </Field.Root>
            {method === 'pdf' && <Field.Root><Field.Label>Page layout</Field.Label>
              <AdminSelect value={media} disabled={saving} onChange={event => { setMedia(event.target.value); changed(); }}>
                <option value="screen">Screen appearance</option><option value="print">Website print layout</option>
              </AdminSelect>
            </Field.Root>}
            {method === 'manual' && <Field.Root required><Field.Label>Saved PDF</Field.Label>
              <Input type="file" accept="application/pdf,.pdf" disabled={saving} onChange={event => { setFile(event.target.files?.[0] || null); changed(); }} />
            </Field.Root>}
            <Text fontSize="sm" color="muted">Only this page is captured. Sites requiring sign-in or a browser challenge may need a PDF saved manually. Check the resulting document before publication.</Text>
          </>}
          {jobId && !job && <Text role="status">Loading saved import…</Text>}
          {job && <>
            <Text as="a" href={job.submitted_url} target="_blank" rel="noopener noreferrer" overflowWrap="anywhere" color="blue.700">{job.submitted_url}</Text>
            <Text role="status" fontWeight="600">{importLabel(job)}</Text>
            {ACTIVE_IMPORTS.has(job.status) && <Text fontSize="sm">You can close this dialog. The import is saved and will continue in the background.</Text>}
            {job.title && <Text>{job.title}{job.page_count ? ` · ${job.page_count} pages` : ''}</Text>}
            {job.error && <Text role="alert" color="red.600">{job.error}</Text>}
            {job.warnings?.map(warning => <Text key={warning} color="orange.700" fontSize="sm">{warning}</Text>)}
            {job.status === 'completed' && <Text>{job.document_id ? 'PDF saved. Open it to preview, assign coverage and process it.' : 'The saved document has been removed from the library. Start a new import to capture it again.'}</Text>}
            {stopped && <>
              <Flex gap={3} wrap="wrap">
                <Button type="button" variant="outline" disabled={saving} onClick={() => action('retry')}>Retry capture</Button>
                <Button type="button" variant="outline" disabled={saving} onClick={() => { setJob(null); setJobId(null); setMedia('print'); changed(); }}>Try another layout</Button>
              </Flex>
              <Field.Root><Field.Label>Or attach a PDF saved from your browser</Field.Label>
                <Input type="file" accept="application/pdf,.pdf" disabled={saving} onChange={event => setFile(event.target.files?.[0] || null)} />
              </Field.Root>
              <Button type="button" disabled={saving || !file} onClick={attachPDF}>Save attached PDF</Button>
            </>}
          </>}
          {error && <Text role="alert" color="red.600">{error}</Text>}
        </Stack></Dialog.Body>
        <Dialog.Footer>
          <Button type="button" variant="outline" disabled={saving} onClick={close}>{jobId ? 'Close' : 'Cancel'}</Button>
          {job && ACTIVE_IMPORTS.has(job.status) && <Button type="button" variant="outline" disabled={saving} onClick={() => action('cancel')}>Cancel import</Button>}
          {job?.document_id && <Button type="button" loading={saving} onClick={openDocument}>Open PDF document</Button>}
          {!jobId && <Button type="submit" loading={saving}>{savedDocument ? 'Open saved document' : method === 'pdf' ? 'Queue PDF capture' : 'Save and continue'}</Button>}
        </Dialog.Footer>
      </form>
    </Dialog.Content></Dialog.Positioner>
  </Dialog.Root>;
}
