"use client";

import { useEffect, useState } from "react";
import { Box, Button, Dialog, Stack, Text } from "@chakra-ui/react";
import { categoryRemovalImpact } from "@/api/categories.mjs";
import { AdminSelect } from "./NativeControls";
import FormField from "./FormField";

export default function CategoryRemovalDialog({ category, categories, archiveCategory, deleteCategory, onClose, onComplete }) {
  const [impact, setImpact] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [deleteMode, setDeleteMode] = useState(Boolean(category.archived));
  const [target, setTarget] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setImpact(null);
    setError("");
    categoryRemovalImpact(category.id, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setImpact(result); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [category.id, attempt]);

  const guides = impact?.guides || [];
  const publishedCount = guides.filter((guide) => guide.status === "published").length;
  const historyBlocksDeletion = Boolean(impact && (impact.chat_count || impact.recap_count));
  const destinations = categories.filter((item) => item.id !== category.id && !item.archived && (!publishedCount || item.published));
  const validTarget = destinations.some((item) => item.id === target);
  const canDelete = impact && !historyBlocksDeletion && (!guides.length || validTarget);
  const archived = impact?.category.archived ?? category.archived;

  async function act(permanent) {
    if (busy || !impact || (permanent && !canDelete)) return;
    setBusy(true);
    setError("");
    try {
      if (permanent) {
        await deleteCategory(category.id, { fingerprint: impact.fingerprint, target_category_id: guides.length ? target : null });
      } else {
        await archiveCategory(category.id);
      }
      onComplete(permanent ? (guides.length ? "Guides moved and topic deleted." : "Topic deleted.")
        : "Topic archived. Its content and history are preserved. Restore it from Show archived topics when needed.");
    } catch (cause) {
      setError(cause.message);
      if (cause.status === 409 || cause.status === 404) setImpact(null);
    } finally {
      setBusy(false);
    }
  }

  return <Dialog.Root open onOpenChange={(event) => { if (!event.open && !busy) onClose(); }} size="lg" scrollBehavior="inside">
    <Dialog.Backdrop />
    <Dialog.Positioner><Dialog.Content>
      <Dialog.Header><Dialog.Title>Remove “{category.name}”</Dialog.Title></Dialog.Header>
      <Dialog.Body><Stack gap={4}>
        {loading && <Text role="status">Checking guides, assignments and saved history…</Text>}
        {error && <Text role="alert" color="red.600">{error}</Text>}
        {!loading && !impact && <Button alignSelf="start" variant="outline" disabled={busy} onClick={() => setAttempt((value) => value + 1)}>Refresh removal details</Button>}
        {impact && <>
          <Text>Archiving hides this topic and its guides from drivers and removes the topic from new chatbot selections. Guides, documents, assignments and saved history stay intact.</Text>
          <Box bg="bg.subtle" borderWidth="1px" borderRadius="8px" p={4}>
            <Text fontWeight="600" mb={2}>What this topic contains</Text>
            <Text>{guides.length} guides: {publishedCount} published, {guides.length - publishedCount} drafts</Text>
            <Text>{impact.document_links.length} document assignments · {impact.video_links.length} video links</Text>
            <Text>{impact.chat_count} saved chats · {impact.recap_count} learning recaps</Text>
            {guides.length > 0 && <Box as="details" mt={3}>
              <Box as="summary" cursor="pointer">View guides</Box>
              <Box as="ul" pl={5} mt={2}>{guides.map((guide) => <Box as="li" key={guide.id}>{guide.title} ({guide.status})</Box>)}</Box>
            </Box>}
            {(impact.document_links.length > 0 || impact.video_links.length > 0) && <Box as="details" mt={3}>
              <Box as="summary" cursor="pointer">View assignments</Box>
              <Box as="ul" pl={5} mt={2}>
                {impact.document_links.map((link) => <Box as="li" key={link.id}>Document: {link.name}</Box>)}
                {impact.video_links.map((link) => <Box as="li" key={link.id}>Video: {link.video_id}</Box>)}
              </Box>
            </Box>}
          </Box>
          {!deleteMode && <Button alignSelf="start" variant="plain" disabled={busy} onClick={() => setDeleteMode(true)}>Review permanent deletion</Button>}
          {deleteMode && <Stack gap={3}>
            {historyBlocksDeletion ? <Text role="status">This topic has saved chat or learning history. Permanent deletion is blocked. Archive it to preserve those references.</Text> : <>
              <Text>Permanently deleting removes the topic and its document assignments and video links. Original documents, stored files and videos are kept.</Text>
              {guides.length > 0 && <FormField label="Move all guides to" hint={publishedCount ? "Choose a published topic so published guides remain available." : "Both draft and published destination topics are available."}>
                <AdminSelect aria-label="Move all guides to" value={target} disabled={busy} onChange={(event) => setTarget(event.target.value)}>
                  <option value="">Choose a destination topic</option>
                  {destinations.map((item) => <option key={item.id} value={item.id}>{item.name}{item.published ? "" : " (Draft)"}</option>)}
                </AdminSelect>
              </FormField>}
              {guides.length > 0 && !destinations.length && <Text>Create a destination topic{publishedCount ? " and publish it" : ""} before deleting, or archive this topic.</Text>}
            </>}
          </Stack>}
        </>}
      </Stack></Dialog.Body>
      <Dialog.Footer flexWrap="wrap">
        <Button variant="outline" disabled={busy} onClick={onClose}>Cancel</Button>
        {deleteMode && !historyBlocksDeletion && <Button colorPalette="red" variant="outline" disabled={busy || loading || !canDelete} loading={busy} onClick={() => act(true)}>
          {guides.length ? "Move guides and delete topic" : "Delete topic permanently"}
        </Button>}
        {!archived && <Button disabled={busy || loading || !impact} loading={busy} onClick={() => act(false)}>Archive topic</Button>}
      </Dialog.Footer>
    </Dialog.Content></Dialog.Positioner>
  </Dialog.Root>;
}
