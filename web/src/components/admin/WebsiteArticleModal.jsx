"use client";

import { useState } from "react";
import { Button, Dialog, Field, Input, Stack, Text } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import useUnsavedChanges from "./useUnsavedChanges";

export default function WebsiteArticleModal({ onClose, onAdded }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedDocument, setSavedDocument] = useState(null);
  useUnsavedChanges(Boolean(url));

  function close() {
    if (!saving && (!url || window.confirm("Discard this article URL?"))) onClose();
  }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    try {
      const document = savedDocument || await request("/documents/website", {
        method: "POST", body: { url: url.trim() }, timeoutMs: 65000,
      });
      setSavedDocument(document);
      await onAdded(document);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setSaving(false);
    }
  }

  return <Dialog.Root open closeOnInteractOutside={false} closeOnEscape={!saving} onOpenChange={(event) => !event.open && close()}>
    <Dialog.Backdrop />
    <Dialog.Positioner><Dialog.Content>
      <form onSubmit={submit}>
        <Dialog.Header><Dialog.Title>Add website article</Dialog.Title></Dialog.Header>
        <Dialog.Body><Stack gap={4}>
          <Text>Save a public article as a stable snapshot. Next, choose its vehicles or topics, prepare it and review it before publication.</Text>
          <Text fontSize="sm" color="muted">Only this page is imported. Updated content creates a separate snapshot. Images that cannot be saved are flagged for review. Login, paywall and JavaScript-only pages are unsupported.</Text>
          <Field.Root required><Field.Label>Article URL</Field.Label>
            <Input type="url" required maxLength={2048} value={url} disabled={saving || Boolean(savedDocument)} placeholder="https://example.com/article" onChange={(event) => setUrl(event.target.value)} />
          </Field.Root>
          {saving && <Text role="status">Retrieving the article and saving its snapshot…</Text>}
          {savedDocument && <Text role="status">Article snapshot saved. Opening its document workspace…</Text>}
          {error && <Text role="alert" color="red.600">{error}</Text>}
        </Stack></Dialog.Body>
        <Dialog.Footer>
          <Button variant="outline" disabled={saving} onClick={close}>Cancel</Button>
          <Button type="submit" loading={saving}>Save article and continue</Button>
        </Dialog.Footer>
      </form>
    </Dialog.Content></Dialog.Positioner>
  </Dialog.Root>;
}
