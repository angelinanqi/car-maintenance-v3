"use client";

import { useEffect, useState } from "react";
import {
  Button,
  Fieldset,
  Flex,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useContent } from "@/components/ContentProvider";
import { request } from "@/api/client.mjs";
import { documentCoverage } from "@/lib/adminJourney.mjs";
import DocumentCoverageFields from "./DocumentCoverageFields";
import useUnsavedChanges from "./useUnsavedChanges";

export default function DocumentCoverage({
  document,
  preferredVehicle = "",
  onDirty,
  onSaved,
  disabled = false,
  prepare = false,
}) {
  const { knowledge, refresh } = useContent();
  const coverage = documentCoverage(document.id, knowledge);
  const initial = {
    ...coverage,
    vehicle_ids:
      coverage.vehicle_ids.length ||
      coverage.category_ids.length ||
      !preferredVehicle
        ? coverage.vehicle_ids
        : [preferredVehicle],
    year: document.year || "",
    engine: document.engine || "",
    variant: document.variant || "",
    vehicle_independent: document.vehicle_independent || false,
  };
  const [baseline, setBaseline] = useState({
    ...initial,
    vehicle_ids: coverage.vehicle_ids,
  });
  const [draft, setDraft] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  useUnsavedChanges(dirty);
  useEffect(() => {
    onDirty?.(dirty);
    return () => onDirty?.(false);
  }, [dirty, onDirty]);

  async function save(event) {
    event.preventDefault();
    if (busy) return;
    const shouldPrepare = prepare && event.nativeEvent.submitter?.value !== "save";
    let coverageSaved = false;
    if (!draft.vehicle_ids.length && !draft.category_ids.length) {
      setError(
        "Choose at least one vehicle or topic so we know where this document belongs.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { vehicle_ids, category_ids, ...metadata } = draft;
      await request(`/documents/${document.id}`, {
        method: "PATCH",
        body: metadata,
      });
      await request(`/knowledge/documents/${document.id}/associations`, {
        method: "PUT",
        body: { vehicle_ids, category_ids },
      });
      setBaseline(draft);
      coverageSaved = true;
      if (shouldPrepare) {
        const force = document.status === "processed" ? "?force=true" : "";
        await request(`/documents/${document.id}/process${force}`, { method: "POST" });
        setNotice("Coverage saved and preparation requested. You can return later.");
      } else {
        setNotice("Coverage saved. You can continue with the next step below.");
      }
      await refresh({ documentsOnly: true });
      onSaved?.();
    } catch (cause) {
      setError(`${coverageSaved && shouldPrepare ? "Coverage was saved, but preparation was not confirmed. " : ""}${cause.message}`);
      await refresh({ documentsOnly: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save}>
      <Fieldset.Root disabled={busy || disabled}>
        <Stack gap={4}>
          <Text color="muted">
            Choose only the vehicles and topics covered by the original. If a
            year or engine is unclear, save your work and confirm it before
            making the document available.
          </Text>
          {error && <Text role="alert">{error}</Text>}
          {notice && <Text role="status">{notice}</Text>}
          <DocumentCoverageFields knowledge={knowledge} draft={draft}
            onChange={(next) => { setDraft(next); setNotice(""); }} />
          <Flex gap={3} wrap="wrap">
            <Button
              type="submit"
              value={prepare ? "prepare" : "save"}
              loading={busy}
              disabled={!prepare && !dirty}
            >
              {prepare ? "Save coverage and prepare" : "Save coverage"}
            </Button>
            {prepare && (
              <Button type="submit" value="save" variant="outline" disabled={busy || !dirty}>
                Save coverage only
              </Button>
            )}
          </Flex>
        </Stack>
      </Fieldset.Root>
    </form>
  );
}
