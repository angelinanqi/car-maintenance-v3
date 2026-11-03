"use client";

import { useState } from "react";
import { Box, Button, Fieldset, Flex, Stack, Text } from "@chakra-ui/react";
import { useContent } from "@/components/ContentProvider";
import { saveDocumentCoverage } from "@/api/documents.mjs";
import { applyCoverageBatch } from "@/lib/documentBatch.mjs";
import DocumentCoverageFields from "./DocumentCoverageFields";

export default function UploadCoverageStep({ documents, preferredVehicle, remainingFileCount = 0, onBusy, onDone, onBack }) {
  const { knowledge, refresh } = useContent();
  const [draft, setDraft] = useState({
    vehicle_ids: preferredVehicle ? [preferredVehicle] : [], category_ids: [],
    vehicle_independent: false, year: "", engine: "", variant: "",
  });
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const savedIds = new Set(results.filter((result) => result.saved).map((result) => result.id));
  const complete = savedIds.size === documents.length;

  async function save() {
    if (busy || complete) return;
    if (!draft.vehicle_ids.length && !draft.category_ids.length) {
      setError("Choose at least one vehicle or learning topic, or finish later.");
      return;
    }
    setBusy(true);
    onBusy(true);
    setError("");
    const previous = results.filter((result) => result.saved);
    try {
      const outcomes = await applyCoverageBatch(documents.filter((document) => !savedIds.has(document.id)),
        draft, saveDocumentCoverage, (updates) => setResults([...previous, ...updates]));
      if (outcomes.some((result) => !result.saved)) {
        setError("Some coverage assignments failed. Your files are uploaded. Retry the remaining assignments below.");
      }
      await refresh({ documentsOnly: true });
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
      onBusy(false);
    }
  }

  return (
    <Stack gap={5}>
      <Box role="status" bg="green.50" p={4} borderRadius="md">
        <Text fontWeight="600">{documents.length} document(s) uploaded</Text>
        <Text fontSize="sm">Choose coverage once to apply it to every document in this bundle. You can adjust each document later.</Text>
        {remainingFileCount > 0 && <Text fontSize="sm" mt={2}>
          {remainingFileCount} selected file(s) still need upload. Return to the remaining files to retry, or finish with the documents already uploaded.
        </Text>}
        <Box as="details" mt={2}>
          <Box as="summary">Uploaded documents</Box>
          {documents.map((document) => <Text key={document.id} fontSize="sm">{document.name}</Text>)}
        </Box>
      </Box>
      {error && <Text role="alert" color="red.600">{error}</Text>}
      {!knowledge ? (
        <Stack>
          <Text>Coverage choices could not be loaded. Your uploaded documents are saved.</Text>
          <Button type="button" variant="outline" onClick={() => refresh({ resources: ["knowledge"] })}>Reload coverage choices</Button>
        </Stack>
      ) : (
        <Fieldset.Root disabled={busy}>
          <DocumentCoverageFields knowledge={knowledge} draft={draft} onChange={(next) => {
            setDraft(next); setResults([]); setError("");
          }} />
        </Fieldset.Root>
      )}
      {results.length > 0 && (
        <Stack gap={1} aria-live="polite">
          <Text fontWeight="600">Coverage saved for {savedIds.size} of {documents.length} documents</Text>
          {results.filter((result) => !result.saved).map((result) => (
            <Text key={result.id} fontSize="sm" color="red.600">{result.name}: {result.error}</Text>
          ))}
        </Stack>
      )}
      <Flex gap={3} wrap="wrap" justify="end">
        {onBack && <Button type="button" variant="outline" disabled={busy} onClick={onBack}>Back to remaining files</Button>}
        <Button type="button" variant="outline" disabled={busy} onClick={() => onDone(documents)}>
          {remainingFileCount ? "Finish with uploaded documents" : complete ? "Done" : "Finish later"}
        </Button>
        <Button type="button" disabled={!knowledge || busy || complete} loading={busy} onClick={save}>
          {complete ? "Coverage saved" : results.some((result) => !result.saved)
            ? "Retry remaining assignments" : `Apply coverage to ${documents.length} document(s)`}
        </Button>
      </Flex>
    </Stack>
  );
}
