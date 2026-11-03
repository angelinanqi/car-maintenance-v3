"use client";

import { useEffect, useState } from "react";
import { Box, Button, Flex, Input, Stack, Text, Textarea } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { API_URL } from "@/lib/config.mjs";

export default function VisualReview({ document, onSaved, onDirty }) {
  const [images, setImages] = useState(null);
  const [selected, setSelected] = useState("");
  const [edits, setEdits] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const path = `/documents/${document.id}/visuals`;
  const image = images?.find((item) => item.element_id === selected);
  const value = edits[selected] || {
    title: image?.review?.title || image?.generated_identity?.title || image?.caption || "",
    description: image?.review?.description ?? image?.generated_identity?.description ?? "",
    uncertainty: image?.review?.uncertainty ?? image?.generated_identity?.uncertainty ?? "",
    approved: Boolean(image?.review),
  };
  const pendingCount = Object.keys(edits).length;
  const checkedCount = images?.filter((item) => edits[item.element_id]?.approved ?? Boolean(item.review)).length || 0;
  const selectedIndex = images?.findIndex((item) => item.element_id === selected) ?? -1;
  const invalid = Object.entries(edits).find(([, review]) => review.approved && !review.title.trim());
  const readOnly = document.published || Boolean(document.superseded_by_id);

  useEffect(() => {
    onDirty?.(pendingCount > 0 && !saved);
    return () => onDirty?.(false);
  }, [pendingCount, saved, onDirty]);

  async function load() {
    setBusy(true);
    setError("");
    try {
      const result = await request(`${path}?revision=${document.source_revision}`);
      setImages(result);
      setSelected(result[0]?.element_id || "");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  function edit(changes) {
    if (busy || readOnly) return;
    setEdits((previous) => ({ ...previous, [selected]: { ...value, ...changes } }));
    setError("");
  }

  function checkAndNext() {
    if (!image?.available || busy || readOnly) return;
    if (!value.title.trim()) { setError("Enter an identifying title before marking this illustration checked."); return; }
    edit({ approved: true });
    if (selectedIndex < images.length - 1) setSelected(images[selectedIndex + 1].element_id);
  }

  function discard() {
    if (busy || !window.confirm("Discard all unsaved illustration reviews?")) return;
    setEdits({});
    setError("");
  }

  async function save() {
    if (busy || saved || readOnly || !pendingCount) return;
    if (invalid) { setSelected(invalid[0]); setError("Every approved illustration needs an identifying title."); return; }
    setBusy(true);
    setError("");
    try {
      await request(path, { method: "POST", body: {
        source_revision: document.source_revision,
        reviews: Object.entries(edits).map(([element_id, review]) => ({ element_id, ...review })),
      } });
      setSaved(true);
      await onSaved?.("Illustration reviews saved as a draft. Confirm all changes when you are ready to rebuild the index.");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return <Stack gap={3}>
    <Text fontWeight="semibold">Illustration identity</Text>
    <Text fontSize="sm">Check the illustrations against their original pages. Move between images to review as many as you need; checks and edits stay here until you save the whole batch. Saving creates a draft. Confirm all changes afterwards to rebuild the index.</Text>
    {error && <Text role="alert">{saved ? "The reviews were saved, but refreshing the document failed. Reload the document to continue. " : ""}{error}</Text>}
    {saved ? <Text role="status">All changes in this illustration review batch are saved as a draft. Indexing is on hold until you confirm all changes.</Text>
      : <>
        {!images && <Button variant="outline" loading={busy} onClick={load}>Review illustrations</Button>}
        {images?.length === 0 && <Text>No extracted illustrations.</Text>}
        {image && <>
          <Text role="status" fontSize="sm">{checkedCount} of {images.length} illustrations checked · {pendingCount} unsaved changes</Text>
          <select aria-label="Illustration to review" value={selected} disabled={busy} onChange={(event) => setSelected(event.target.value)}>
            {images.map((item) => <option key={item.element_id} value={item.element_id}>
              {(edits[item.element_id]?.approved ?? Boolean(item.review)) ? "Checked · " : ""}{item.element_id} · {edits[item.element_id]?.title || item.review?.title || item.caption || item.section_path.at(-1) || "Untitled"}
            </option>)}
          </select>
          <Flex gap={2} wrap="wrap">
            <Button size="sm" variant="outline" disabled={busy || selectedIndex <= 0} onClick={() => setSelected(images[selectedIndex - 1].element_id)}>Previous illustration</Button>
            <Button size="sm" variant="outline" disabled={busy || selectedIndex >= images.length - 1} onClick={() => setSelected(images[selectedIndex + 1].element_id)}>Next illustration</Button>
          </Flex>
          <Text fontSize="sm">PDF pages: {image.pages.join(", ") || "unavailable"}</Text>
          <Text fontSize="sm">Inherited section: {image.section_path.join(" → ")}</Text>
          {image.generated_identity && !image.review && <Text fontSize="sm">The suggested identity was generated from this image. Check its labels and interpretation before approving it.</Text>}
          {image.available ? <Box bg="white" p={3}><img
            src={`${API_URL}${path}/${selected}?revision=${document.source_revision}`}
            crossOrigin="use-credentials" alt="Original illustration for identity review"
            style={{ maxWidth: "100%", maxHeight: 400, objectFit: "contain" }} /></Box>
            : <Text role="alert">The original image is missing. Prepare this manual from its PDF.</Text>}
          <Input aria-label="Reviewed illustration title" value={value.title} maxLength={200} disabled={busy || readOnly}
            placeholder="Identifying title" onChange={(event) => edit({ title: event.target.value })} />
          <Textarea aria-label="Reviewed illustration description" value={value.description} maxLength={1600} disabled={busy || readOnly}
            placeholder="Visible content and distinguishing features" onChange={(event) => edit({ description: event.target.value })} />
          <Textarea aria-label="Uncertain illustration details" value={value.uncertainty} maxLength={800} disabled={busy || readOnly}
            placeholder="Unclear labels or relationships" onChange={(event) => edit({ uncertainty: event.target.value })} />
          <label><input type="checkbox" checked={value.approved} disabled={busy || readOnly || !image.available}
            onChange={(event) => edit({ approved: event.target.checked })} /> I checked this image's identity against the original</label>
          {document.published && <Text fontSize="sm">Unpublish this document or stage a replacement before saving identity changes.</Text>}
          <Button alignSelf="start" disabled={busy || readOnly || !image.available || !value.title.trim()} onClick={checkAndNext}>
            {selectedIndex < images.length - 1 ? "Mark checked and next" : "Mark illustration checked"}
          </Button>
          {pendingCount > 0 && <Text fontSize="sm" color="muted">Your changes are not saved yet. Finish reviewing, then save all illustration reviews together.</Text>}
          {invalid && <Text role="alert" fontSize="sm">A checked illustration needs an identifying title. <Button variant="plain" size="xs" disabled={busy} onClick={() => setSelected(invalid[0])}>Open that illustration</Button></Text>}
          <Flex gap={3} wrap="wrap">
            <Button loading={busy} disabled={busy || readOnly || !pendingCount || Boolean(invalid)} onClick={save}>Save all illustration reviews as draft</Button>
            {pendingCount > 0 && <Button variant="outline" disabled={busy} onClick={discard}>Discard unsaved illustration reviews</Button>}
          </Flex>
        </>}
      </>}
  </Stack>;
}
