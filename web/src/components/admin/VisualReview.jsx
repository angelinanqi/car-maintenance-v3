"use client";

import { useState } from "react";
import { Box, Button, Input, Stack, Text, Textarea } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { API_URL } from "@/lib/config.mjs";

export default function VisualReview({ document, onSaved }) {
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
    setEdits({ ...edits, [selected]: { ...value, ...changes } });
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      await request(path, { method: "POST", body: {
        source_revision: document.source_revision,
        reviews: Object.entries(edits).map(([element_id, review]) => ({ element_id, ...review })),
      } });
      setSaved(true);
      await onSaved();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return <Stack gap={3}>
    <Text fontWeight="semibold">Illustration identity</Text>
    <Text fontSize="sm">Compare each illustration with its original page. Give it a title that distinguishes it from similar diagrams. Approving its identity makes it eligible for chat selection; nearby paragraphs and notes still need their own source checks.</Text>
    {error && <Text role="alert">{error}</Text>}
    {saved ? <Text role="status">Reviews saved. Document preparation and indexing are running. Reopen the document when they finish.</Text>
      : <>
        {!images && <Button variant="outline" loading={busy} onClick={load}>Review illustrations</Button>}
        {images?.length === 0 && <Text>No extracted illustrations.</Text>}
        {image && <>
          <select aria-label="Illustration to review" value={selected} onChange={(event) => setSelected(event.target.value)}>
            {images.map((item) => <option key={item.element_id} value={item.element_id}>
              {item.element_id} · {item.review?.title || item.caption || item.section_path.at(-1) || "Untitled"}
            </option>)}
          </select>
          <Text fontSize="sm">PDF pages: {image.pages.join(", ") || "unavailable"}</Text>
          <Text fontSize="sm">Inherited section: {image.section_path.join(" → ")}</Text>
          {image.generated_identity && !image.review && <Text fontSize="sm">The suggested identity was generated from this image. Check its labels and interpretation before approving it.</Text>}
          {image.available ? <Box bg="white" p={3}><img
            src={`${API_URL}${path}/${selected}?revision=${document.source_revision}`}
            crossOrigin="use-credentials" alt="Original illustration for identity review"
            style={{ maxWidth: "100%", maxHeight: 400, objectFit: "contain" }} /></Box>
            : <Text role="alert">The original image is missing. Prepare this manual from its PDF.</Text>}
          <Input aria-label="Reviewed illustration title" value={value.title} maxLength={200}
            placeholder="Identifying title" onChange={(event) => edit({ title: event.target.value })} />
          <Textarea aria-label="Reviewed illustration description" value={value.description} maxLength={1600}
            placeholder="Visible content and distinguishing features" onChange={(event) => edit({ description: event.target.value })} />
          <Textarea aria-label="Uncertain illustration details" value={value.uncertainty} maxLength={800}
            placeholder="Unclear labels or relationships" onChange={(event) => edit({ uncertainty: event.target.value })} />
          <label><input type="checkbox" checked={value.approved} disabled={!image.available}
            onChange={(event) => edit({ approved: event.target.checked })} /> I checked this image's identity against the original</label>
          {document.published && <Text fontSize="sm">Unpublish this document or stage a replacement before saving identity changes.</Text>}
          <Button loading={busy} disabled={document.published || !Object.keys(edits).length}
            onClick={save}>Save reviews and prepare document</Button>
        </>}
      </>}
  </Stack>;
}
