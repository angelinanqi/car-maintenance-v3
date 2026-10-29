"use client";

import { useEffect, useRef, useState } from "react";
import { Badge, Box, Button, Flex, Grid, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { originalDocumentUrl } from "@/api/documents.mjs";
import { API_URL } from "@/lib/config.mjs";
import { AdminSelect } from "./NativeControls";
import FormField from "./FormField";
import { QuestionDialog } from "./ReviewQuestions";
import useUnsavedChanges from "./useUnsavedChanges";
import VisualReview from "./VisualReview";
import ExtractionCorrection from "./ExtractionCorrection";

const statusLabels = { checked: "Checked", needs_clarification: "Needs clarification" };

export default function DocumentReview({ document, onLoaded, onUpdated }) {
  const [review, setReview] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [pending, setPending] = useState(null);
  const [saving, setSaving] = useState(false);
  const [stale, setStale] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [asking, setAsking] = useState(null);
  const [saved, setSaved] = useState(false);
  const [correctionDirty, setCorrectionDirty] = useState(false);
  const savingRef = useRef(false);
  const mounted = useRef(true);
  useUnsavedChanges(Boolean(pending || saving || correctionDirty));

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setReview(null);
    setLoadError("");
    setSaveError("");
    setPending(null);
    setStale(false);
    setSaved(false);
    request(`/documents/${document.id}/review?revision=${document.source_revision}`, { signal: controller.signal })
      .then((result) => { if (!controller.signal.aborted) setReview(result); })
      .catch((cause) => { if (!controller.signal.aborted) setLoadError(cause.message); });
    return () => controller.abort();
  }, [document.id, document.source_revision, attempt]);

  useEffect(() => {
    onLoaded(Boolean(review && !pending && !saving && !stale && !correctionDirty));
    return () => onLoaded(false);
  }, [review, pending, saving, stale, correctionDirty, onLoaded]);

  const progress = pending || review?.progress;
  const blocks = review?.blocks || [];
  const decisions = progress?.decisions || {};
  const selected = blocks.find((block) => block.element_id === progress?.current_element_id) || blocks[0];
  const needle = query.trim().toLowerCase();
  const visible = blocks.filter((block) => {
    const status = decisions[block.element_id];
    const matchesStatus = filter === "all" || (filter === "unchecked" && status !== "checked") ||
      (filter === "needs_clarification" && status === "needs_clarification") ||
      (filter === "issues" && block.issues.length > 0);
    const text = [block.title, block.text, ...block.section_path, ...block.issues].join(" ").toLowerCase();
    return matchesStatus && (!needle || text.includes(needle));
  });
  const checked = blocks.filter((block) => decisions[block.element_id] === "checked").length;
  const clarification = blocks.filter((block) => decisions[block.element_id] === "needs_clarification").length;
  const index = visible.findIndex((block) => block.element_id === selected?.element_id);
  const page = progress?.source_page ?? selected?.pages[0] ?? null;
  const original = `${originalDocumentUrl(document.id, document.source_revision)}${document.source_type === "pdf" && page ? `#page=${page}` : ""}`;
  const reviewDisabled = saving || Boolean(pending) || stale;
  const disabled = reviewDisabled || correctionDirty;

  async function save(next) {
    if (savingRef.current || stale) return;
    savingRef.current = true;
    setSaving(true);
    setPending(next);
    setSaveError("");
    setSaved(false);
    try {
      const result = await request(`/documents/${document.id}/review/progress`, {
        method: "PUT", body: {
          source_revision: document.source_revision, version: review.progress.version,
          decisions: next.decisions, current_element_id: next.current_element_id, source_page: next.source_page,
        },
      });
      if (!mounted.current) return;
      setReview((previous) => ({ ...previous, progress: result }));
      setPending(null);
      setSaved(true);
    } catch (cause) {
      if (!mounted.current) return;
      setSaveError(cause.message);
      if (cause.status === 409) setStale(true);
    } finally {
      savingRef.current = false;
      if (mounted.current) setSaving(false);
    }
  }

  function select(block) {
    if (disabled) return;
    save({ ...progress, current_element_id: block.element_id, source_page: block.pages[0] || null });
  }

  function decide(status, advance = false, block = selected) {
    if (savingRef.current || pending || stale || !block) return;
    const nextDecisions = { ...decisions };
    if (status) nextDecisions[block.element_id] = status;
    else delete nextDecisions[block.element_id];
    const nextBlock = advance && index >= 0 ? visible[index + 1] : null;
    save({ ...progress, decisions: nextDecisions,
      current_element_id: nextBlock?.element_id || block.element_id,
      source_page: nextBlock ? nextBlock.pages[0] || null : page });
  }

  function reload() {
    if (saving || ((pending || correctionDirty) && !window.confirm("Reload saved progress? Unsaved checklist changes and extraction corrections will be discarded."))) return;
    setAttempt((value) => value + 1);
  }

  return <Stack gap={5}>
    <Text color="muted">Check instructions, numbers, units and table relationships against the original.
      Your checklist and source position save as you work. Final approval is a separate step below.</Text>
    <Flex gap={3} justify="space-between" align="center" wrap="wrap">
      <Box>
        <Text fontWeight="600">{checked} of {blocks.length} entries checked{clarification ? ` · ${clarification} need clarification` : ""}</Text>
        <Text fontSize="sm" color="muted">Your review progress for this document version</Text>
      </Box>
      <Text role="status" fontSize="sm" color="muted">{saving ? "Saving progress…" : pending ? "Changes are not saved" : saved ? "Progress saved" : review?.progress.version ? "Saved review restored" : ""}</Text>
    </Flex>
    {(loadError || saveError) && <Box role="alert" bg="orange.50" borderWidth="1px" borderColor="orange.200" p={4} borderRadius="8px">
      <Text>{loadError || saveError}</Text>
      <Flex gap={3} mt={3} wrap="wrap">
        {pending && !stale && <Button size="sm" disabled={saving} onClick={() => save(pending)}>Retry saving progress</Button>}
        <Button size="sm" variant="outline" disabled={saving} onClick={reload}>Reload saved review</Button>
      </Flex>
    </Box>}
    {!review && !loadError && <Text role="status">Opening your document review…</Text>}
    {review && <>
      <Grid templateColumns={{ base: "1fr", md: "2fr 1fr" }} gap={3}>
        <FormField label="Find a section, table or illustration"><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search headings and extracted content" /></FormField>
        <FormField label="Show entries"><AdminSelect value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="all">All entries ({blocks.length})</option>
          <option value="unchecked">Unchecked ({blocks.length - checked})</option>
          <option value="needs_clarification">Needs clarification ({clarification})</option>
          <option value="issues">Extraction issues ({blocks.filter((block) => block.issues.length).length})</option>
        </AdminSelect></FormField>
      </Grid>
      <Box as="nav" aria-label="Document review entries" maxH="200px" overflowY="auto" borderWidth="1px" borderRadius="8px">
        {visible.map((block) => <Button key={block.element_id} variant="plain" w="100%" h="auto" minH="44px" py={3} px={4}
          justifyContent="start" textAlign="left" whiteSpace="normal" borderRadius="0"
          bg={selected?.element_id === block.element_id ? "brand.50" : "transparent"}
          aria-current={selected?.element_id === block.element_id ? "step" : undefined}
          disabled={disabled} onClick={() => select(block)}>
          <Flex gap={3} align="center" wrap="wrap">
            <Text as="span">{block.kind === "image" ? "Illustration" : block.kind === "table" ? "Table" : "Section"}: {block.title}</Text>
            <Badge colorPalette={decisions[block.element_id] === "checked" ? "green" : decisions[block.element_id] ? "orange" : "gray"}>{statusLabels[decisions[block.element_id]] || "Unchecked"}</Badge>
            {block.issues.length > 0 && <Text as="span" fontSize="xs" color="orange.800">Check extraction</Text>}
          </Flex>
        </Button>)}
        {!visible.length && <Text p={4}>No entries match these filters. Clear the search or choose another filter.</Text>}
      </Box>
      {selected && <>
        <Flex gap={3} justify="space-between" align="center" wrap="wrap">
          <Box minW={0}>
            <Text fontSize="sm" color="muted">{selected.section_path.join(" → ") || "Document content"}</Text>
            <Heading size="md">{selected.title}</Heading>
            {index < 0 && <Text fontSize="sm" color="muted">The open entry is outside the current filters.</Text>}
          </Box>
          <Flex gap={2}>
            <Button size="sm" variant="outline" disabled={disabled || index <= 0} onClick={() => select(visible[index - 1])}>Previous</Button>
            <Button size="sm" variant="outline" disabled={disabled || index < 0 || index >= visible.length - 1} onClick={() => select(visible[index + 1])}>Next</Button>
          </Flex>
        </Flex>
        <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={5}>
          <Stack gap={3} minW={0} position={{ base: "static", xl: "sticky" }} top={{ xl: "110px" }} alignSelf="start">
            <Flex justify="space-between" align="center" gap={2} wrap="wrap">
              <Heading size="sm">Original document</Heading>
              <Button asChild variant="outline" size="xs"><a href={original} target="_blank" rel="noopener noreferrer">Open original in new tab</a></Button>
            </Flex>
            {document.source_type === "pdf" && <>
              <Text fontSize="sm" color="muted">{selected.pages.length ? `Source PDF page${selected.pages.length > 1 ? "s" : ""}: ${selected.pages.join(", ")}` : "No reliable page reference. Locate this content in the original using the page control below."}</Text>
              <form key={`${selected.element_id}:${page}`} onSubmit={(event) => {
                event.preventDefault();
                if (disabled) return;
                const value = Number(new FormData(event.currentTarget).get("page"));
                if (Number.isSafeInteger(value) && value > 0 && value <= 100000)
                  save({ ...progress, current_element_id: selected.element_id, source_page: value });
              }}><Flex gap={2} align="end">
                <FormField label="PDF page (file page number)"><Input name="page" type="number" min={1} max={100000} step={1} required defaultValue={page || ""} disabled={disabled} w="130px" /></FormField>
                <Button type="submit" size="sm" variant="outline" disabled={disabled}>Go to page</Button>
              </Flex></form>
            </>}
            <Box asChild w="100%" h={{ base: "360px", xl: "560px" }} borderWidth="1px" borderRadius="8px" bg="white">
              <iframe key={original} title={`Original: ${document.name}`} src={original} />
            </Box>
          </Stack>
          <Stack gap={3} minW={0}>
            <Heading size="sm">What the system read</Heading>
            {selected.issues.length > 0 && <Box bg="orange.50" borderRadius="8px" p={3}>
              {selected.issues.map((issue) => <Text key={issue} fontSize="sm" mb={1}>{issue}</Text>)}
            </Box>}
            <Box key={selected.element_id} maxH={{ base: "400px", xl: "620px" }} overflow="auto" bg="canvas" p={4} borderRadius="8px"
              css={{ "& table": { width: "100%", borderCollapse: "collapse" }, "& td, & th": { border: "1px solid #aab4bf", padding: "8px", minWidth: "80px" } }}>
              {selected.kind === "table" && selected.html ? <Box dangerouslySetInnerHTML={{ __html: selected.html }} />
                : selected.kind === "image" && selected.image_available ? <img
                  src={`${API_URL}/documents/${document.id}/visuals/${selected.source_element_id}?revision=${document.source_revision}`}
                  crossOrigin="use-credentials" alt={selected.title} style={{ maxWidth: "100%", maxHeight: 520, objectFit: "contain" }} />
                : <Text whiteSpace="pre-wrap">{selected.text || "Check this illustration in the original document."}</Text>}
            </Box>
            {selected.kind === "image" && <Text fontSize="sm" color="muted">Checking this entry records your comparison. Use illustration identity review below to approve its identity for chatbot selection.</Text>}
            {["text", "table"].includes(selected.kind) && <ExtractionCorrection key={`${selected.element_id}:${attempt}`}
              document={document} block={selected} disabled={reviewDisabled} onDirty={setCorrectionDirty}
              onSaved={async (message) => { onLoaded(false); await onUpdated?.(message); }} />}
            <Flex gap={2} wrap="wrap">
              <Button disabled={disabled} onClick={() => decide("checked", true)}>Mark checked{index >= 0 && index < visible.length - 1 ? " and next" : ""}</Button>
              <Button variant="outline" disabled={disabled} onClick={() => setAsking(selected)}>Needs clarification</Button>
              {decisions[selected.element_id] && <Button variant="plain" disabled={disabled} onClick={() => decide(null)}>Mark unchecked</Button>}
            </Flex>
            {decisions[selected.element_id] === "needs_clarification" && <Text fontSize="sm">Resolve the saved question in <a href="#questions" style={{ textDecoration: "underline" }}>Questions needing clarification</a>, then check this entry again.</Text>}
          </Stack>
        </Grid>
      </>}
      {review.correction_count > 0 && <Box as="details" borderTopWidth="1px" pt={4}>
        <Box as="summary" cursor="pointer">Extraction correction history ({review.correction_count})</Box>
        <Text fontSize="sm" color="muted" mt={2}>Showing the latest {review.corrections.length} corrections. The downloadable extraction bundle retains the original extraction and full history.</Text>
        <Stack gap={4} mt={3}>{review.corrections.slice().reverse().map((change, index) => <Box key={index} bg="canvas" p={4} borderRadius="8px">
          <Text fontWeight="600">{change.title}</Text>
          <Text fontSize="sm">{new Date(change.reviewed_at).toLocaleString()} · {change.reason}</Text>
          <Text fontSize="xs" color="muted">Admin: {change.reviewed_by}</Text>
          <Grid templateColumns={{ base: "1fr", lg: "1fr 1fr" }} gap={3} mt={3}
            css={{ "& table": { width: "100%", borderCollapse: "collapse" }, "& td, & th": { border: "1px solid #aab4bf", padding: "8px" } }}>
            {["before", "after"].map((field) => <Box key={field} minW={0} overflowX="auto">
              <Text fontSize="sm" fontWeight="600" mb={2}>{field === "before" ? "Before" : "After"}</Text>
              {change[`${field}_html`] ? <Box fontSize="sm" dangerouslySetInnerHTML={{ __html: change[`${field}_html`] }} />
                : <Text fontSize="sm" whiteSpace="pre-wrap" overflowWrap="anywhere">{change[field]}</Text>}
            </Box>)}
          </Grid>
          {change.truncated && <Text fontSize="xs" mt={2}>Preview shortened; the full entry is retained in the extraction bundle.</Text>}
        </Box>)}</Stack>
      </Box>}
      <Box as="details" borderTopWidth="1px" pt={4}>
        <Box as="summary" cursor="pointer">Illustration identity review</Box>
        <Box as="fieldset" disabled={disabled} mt={4} p={0} minW={0} border={0}>
          <VisualReview document={document} onSaved={async () => { onLoaded(false); await onUpdated?.(); }} />
        </Box>
      </Box>
    </>}
    {asking && <QuestionDialog context={{
      document_id: document.id, source_revision: document.source_revision, source_type: document.source_type,
      title: asking.title.slice(0, 300), source_page: document.source_type === "pdf" ? page : null,
      excerpt: (asking.excerpt || asking.text || "").slice(0, 2000),
    }} onClose={() => setAsking(null)} onSaved={() => decide("needs_clarification", false, asking)} />}
  </Stack>;
}
