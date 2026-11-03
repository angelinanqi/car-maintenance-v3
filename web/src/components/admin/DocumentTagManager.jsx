"use client";

import { useState } from "react";
import { Box, Button, Dialog, Fieldset, Flex, Input, Stack, Text } from "@chakra-ui/react";
import { useContent } from "@/components/ContentProvider";
import { changeDocumentTag } from "@/api/documents.mjs";
import { cleanTag, documentTagSummary, tagKey } from "@/lib/documentTags.mjs";
import FormField from "./FormField";
import useUnsavedChanges from "./useUnsavedChanges";

export default function DocumentTagManager({ onClose }) {
  const { documents, refresh } = useContent();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const [replacement, setReplacement] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const tags = documentTagSummary(documents);
  const filtered = tags.filter((tag) => tagKey(tag.name).includes(tagKey(query)));
  const dirty = Boolean(selected && cleanTag(replacement) !== selected);
  useUnsavedChanges(dirty);
  const merging = tags.find((tag) => tagKey(tag.name) === tagKey(replacement) && tagKey(tag.name) !== tagKey(selected));

  function close() {
    if (!busy && (!dirty || window.confirm("Discard the unsaved tag name?"))) onClose();
  }
  async function change(next) {
    if (busy || !selected) return;
    if (next !== null && !cleanTag(next)) { setError("Enter a tag name."); return; }
    if (next === null && !window.confirm(`Remove "${selected}" from every document that uses it? Documents keep their other labels and coverage.`)) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const outcome = await changeDocumentTag(selected, next === null ? null : cleanTag(next));
      setResult(outcome);
      if (!outcome.failed.length) { setSelected(""); setReplacement(""); }
      const warning = await refresh({ resources: ["documents"] });
      if (warning) setError(`Tag changes were saved, but the list could not be refreshed. ${warning}`);
    } catch (cause) {
      setError(cause.message);
      await refresh({ resources: ["documents"] });
    } finally { setBusy(false); }
  }

  return (
    <Dialog.Root open size="lg" closeOnInteractOutside={false} closeOnEscape={!busy}
      onOpenChange={({ open }) => { if (!open) close(); }}>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content maxH="85vh" overflowY="auto">
          <Dialog.Header><Dialog.Title>Manage document tags</Dialog.Title></Dialog.Header>
          <Dialog.Body>
            <Stack gap={4}>
              <Text color="muted">Rename a label across the library, merge it into another tag, or remove it from every document. Create new tags when adding or editing a document.</Text>
              {error && <Text role="alert" color="red.600">{error}</Text>}
              {result && <Box role="status" bg={result.failed.length ? "orange.50" : "green.50"} p={3} borderRadius="md">
                <Text>{result.updated.length} document(s) updated.{result.failed.length ? ` ${result.failed.length} could not be changed. Retry the same action after resolving these issues.` : ""}</Text>
                {result.failed.map((document) => <Text key={document.id} fontSize="sm">{document.name}: {document.error}</Text>)}
              </Box>}
              <Fieldset.Root disabled={busy}>
                <Stack gap={4}>
                  <FormField label="Find a tag"><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search labels" /></FormField>
                  <Stack as="ul" listStyleType="none" m={0} p={0} gap={2} maxH="260px" overflowY="auto">
                    {filtered.map((tag) => <Box as="li" key={tagKey(tag.name)}>
                      <Button type="button" w="full" justifyContent="space-between" variant={tagKey(selected) === tagKey(tag.name) ? "solid" : "outline"}
                        aria-pressed={tagKey(selected) === tagKey(tag.name)} onClick={() => {
                          setSelected(tag.name); setReplacement(tag.name); setResult(null); setError("");
                        }}>
                        <Text as="span">{tag.name}</Text><Text as="span" fontSize="sm">{tag.count} document(s)</Text>
                      </Button>
                    </Box>)}
                    {!tags.length && <Text>No tags yet. Add a label when uploading or editing a document.</Text>}
                    {tags.length > 0 && !filtered.length && <Text>No tags match this search.</Text>}
                  </Stack>
                  {selected && <form onSubmit={(event) => { event.preventDefault(); change(replacement); }}>
                    <Stack gap={3}>
                      <Text fontWeight="600">Selected: {selected}</Text>
                      <FormField label="Tag name"><Input value={replacement} maxLength={100} required
                        onChange={(event) => { setReplacement(event.target.value); setResult(null); }} /></FormField>
                      {merging && <Text fontSize="sm">This merges the selected tag into “{merging.name}”. Each document will have one copy of the tag.</Text>}
                      <Flex gap={3} wrap="wrap">
                        <Button type="submit" loading={busy} disabled={busy || !cleanTag(replacement) || cleanTag(replacement) === selected}>
                          {merging ? "Merge tags" : "Rename tag"}
                        </Button>
                        <Button type="button" colorPalette="red" variant="outline" disabled={busy} onClick={() => change(null)}>Remove tag from documents</Button>
                      </Flex>
                    </Stack>
                  </form>}
                </Stack>
              </Fieldset.Root>
            </Stack>
          </Dialog.Body>
          <Dialog.Footer><Button variant="outline" disabled={busy} onClick={close}>Close</Button></Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
