"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Badge, Box, Button, Flex, Grid, Heading, Stack, Text, Textarea } from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import { request } from "@/api/client.mjs";
import { originalDocumentUrl } from "@/api/documents.mjs";
import { API_URL } from "@/lib/config.mjs";
import ChatAnswer from "@/components/chatbot/ChatAnswer";
import FormField from "./FormField";
import { AdminSelect } from "./NativeControls";
import useUnsavedChanges from "./useUnsavedChanges";
import { useContent } from "@/components/ContentProvider";

const decisions = { not_reviewed: "Not reviewed", passed: "Passed", needs_fixing: "Needs fixing" };
const outcomes = { manual_only: "Answer from the document", insufficient_information: "Insufficient evidence or clarification needed",
  reference_only: "Original reference provided", general_information: "General explanation", mixed_sources: "Document and general explanation",
  restricted: "Restricted request", emergency: "Emergency guidance", out_of_scope: "Outside this context", chat: "Conversation response",
  generation_error: "Answer generation failed", retrieval_error: "Document retrieval failed" };
const reasons = {
  unverified_measurement: "An exact specification requires a saved source check. Check the extraction against the original, then rerun this test.",
  unsupported_number: "The answer contained a value that could not be matched to its cited evidence. Compare the original values, units and number formatting before reviewing this result.",
  insufficient_evidence: "The available evidence did not establish an answer. Check whether the relevant passage or table was extracted and retrieved.",
  invalid_citation: "The generated answer did not provide valid supporting citations. Retry and inspect the retrieved evidence.",
  clarification_required: "The question needs clarification before the pipeline can give a supported answer.",
};
const emptyForm = { question: "", expected: "", context: "" };

function fields(question) {
  return question ? { question: question.question, expected: question.expected, context: `${question.scope_type}:${question.scope_id}` } : emptyForm;
}

export default function DocumentTests({ document, onDirty }) {
  const search = useSearchParams();
  const requestedQuestion = search.get("testQuestion") || "";
  const requestedRun = search.get("testRun") || "";
  const linkKey = `${document.id}:${requestedQuestion}:${requestedRun}`;
  const { refresh } = useContent();
  const [work, setWork] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [reviewDirty, setReviewDirty] = useState(false);
  const [chosen, setChosen] = useState([]);
  const [runId, setRunId] = useState("");
  const [running, setRunning] = useState(null);
  const stop = useRef(false);
  const mounted = useRef(true);
  const busyRef = useRef(false);
  const openedLink = useRef("");
  const scrolledLink = useRef("");
  const linkedQuestionRef = useRef(null);
  const resultRef = useRef(null);
  const dirty = showForm && JSON.stringify(form) !== JSON.stringify(fields(editing));
  const locked = loading || !!running || dirty || reviewDirty;
  const ready = work?.ready && document.status === "processed" && work.source_revision === document.source_revision;
  const activeRun = work?.runs.find((run) => run.id === runId) ||
    (requestedQuestion && !runId ? work?.runs.find((run) => run.question_id === requestedQuestion) : work?.runs[0]);
  const stale = activeRun && (activeRun.outdated || activeRun.source_revision !== document.source_revision ||
    activeRun.source_verified !== document.source_fidelity_verified || document.status !== "processed");
  const savedRunning = work?.runs.some((run) => run.status === "running");
  useUnsavedChanges(dirty || reviewDirty);
  useEffect(() => { onDirty?.(dirty || reviewDirty); return () => onDirty?.(false); }, [dirty, reviewDirty, onDirty]);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; stop.current = true; }; }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const query = requestedRun ? `?${new URLSearchParams({ run_id: requestedRun })}` : "";
      const data = await request(`/documents/${document.id}/tests${query}`);
      if (mounted.current) setWork(data);
    } catch (cause) {
      if (mounted.current) setError(cause.message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }

  useEffect(() => {
    if ((!requestedQuestion && !requestedRun) || openedLink.current === linkKey || dirty || reviewDirty || running) return;
    openedLink.current = linkKey;
    setRunId(requestedRun);
    setChosen(requestedQuestion ? [requestedQuestion] : []);
    load();
  }, [linkKey, dirty, reviewDirty, running]);

  useEffect(() => {
    if (!work || (!requestedQuestion && !requestedRun) || scrolledLink.current === linkKey) return;
    const target = requestedRun && activeRun?.id === requestedRun ? resultRef.current : linkedQuestionRef.current;
    if (target) {
      target.scrollIntoView({ block: "start" });
      target.focus({ preventScroll: true });
      scrolledLink.current = linkKey;
    }
  }, [work, activeRun?.id, linkKey]);

  useEffect(() => {
    if (!savedRunning || running || dirty || reviewDirty || loading) return;
    const timer = setTimeout(load, 3000);
    return () => clearTimeout(timer);
  }, [savedRunning, running, dirty, reviewDirty, loading, work]);

  function edit(question = null) {
    setEditing(question);
    setForm(fields(question));
    setShowForm(true);
    setNotice("");
  }

  async function saveQuestion(active = true, question = editing) {
    if (busyRef.current) return;
    busyRef.current = true;
    setLoading(true);
    setError("");
    const [scope_type, scope_id] = (active ? form.context : `${question.scope_type}:${question.scope_id}`).split(":");
    try {
      await request(`/documents/${document.id}/tests/questions${question ? `/${question.id}` : ""}`, {
        method: question ? "PATCH" : "POST", body: {
          question: active ? form.question : question.question, expected: active ? form.expected : question.expected,
          scope_type, scope_id, active, ...(question ? { version: question.version } : {}),
        },
      });
      refresh({ resources: ["documentTests"] });
      if (!mounted.current) return;
      setShowForm(false);
      setForm(emptyForm);
      setEditing(null);
      if (!active) setChosen((previous) => previous.filter((id) => id !== question.id));
      setNotice(active ? "Test question saved." : "Question archived. Its previous results remain in the history.");
      await load();
    } catch (cause) {
      if (mounted.current) setError(cause.message);
    } finally {
      busyRef.current = false;
      if (mounted.current) setLoading(false);
    }
  }

  async function runQuestions(questions) {
    if (busyRef.current || locked || !ready || savedRunning || !questions.length) return;
    busyRef.current = true;
    stop.current = false;
    setError("");
    setNotice("");
    let completed = 0;
    try {
      for (const question of questions.slice(0, 10)) {
        if (stop.current || !mounted.current) break;
        setRunning({ name: question.question, position: completed + 1, total: Math.min(questions.length, 10) });
        const result = await request(`/documents/${document.id}/tests/questions/${question.id}/run`, { method: "POST", body: {
          run_id: crypto.randomUUID(), source_revision: work.source_revision, question_version: question.version,
        } });
        if (!mounted.current) break;
        setWork((previous) => ({ ...previous, runs: [result, ...previous.runs.filter((run) => run.id !== result.id)].slice(0, 50) }));
        setRunId(result.id);
        completed += 1;
        if (result.outdated || result.status === "running") break;
      }
      if (mounted.current) setNotice(`${completed} test${completed === 1 ? "" : "s"} saved. Review the results below.`);
    } catch (cause) {
      if (mounted.current) {
        setError(`${cause.message} Completed results are saved. Reload saved tests before retrying an unconfirmed request.`);
      }
    } finally {
      busyRef.current = false;
      if (mounted.current) setRunning(null);
      refresh({ resources: ["documentTests"] });
    }
  }

  async function saveReview(run, body) {
    setLoading(true);
    setError("");
    try {
      const result = await request(`/documents/${document.id}/tests/runs/${run.id}/review`, { method: "PATCH", body });
      refresh({ resources: ["documentTests"] });
      if (!mounted.current) return false;
      setWork((previous) => ({ ...previous, runs: previous.runs.map((row) => row.id === result.id ? result : row) }));
      setNotice("Test review saved. Publication is a separate decision.");
      return true;
    } catch (cause) {
      if (mounted.current) setError(cause.message);
      return false;
    } finally {
      if (mounted.current) setLoading(false);
    }
  }

  return <Box id="document-tests" scrollMarginTop="130px" bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
    <Heading size="lg" mb={3}>Test This Document</Heading>
    <Text color="muted">Ask saved questions using this document and its selected vehicle or topic. Tests use the normal answer pipeline with only this reference available. Results and review notes are private.</Text>
    {error && <Text role="alert" mt={3}>{error}</Text>}
    {notice && <Text role="status" mt={3}>{notice}</Text>}
    {!work ? <Button mt={4} loading={loading} onClick={load}>Open document tests</Button> : <Stack gap={5} mt={5}>
      {work.linked_run_unavailable && <Text role="alert">The linked test result is no longer available for this document. Other saved results are shown below.</Text>}
      {requestedQuestion && !work.questions.some((question) => question.id === requestedQuestion) && <Text role="status">The linked question is no longer active. Its saved results remain in the history when available.</Text>}
      <Flex gap={3} align="center" wrap="wrap">
        <Badge colorPalette={ready ? "green" : "orange"}>{ready ? "Current revision indexed" : "Wait for current indexing"}</Badge>
        <Badge colorPalette={document.source_fidelity_verified ? "green" : "orange"}>{document.source_fidelity_verified ? "Source check saved" : "Source check required for exact specifications"}</Badge>
        <Button size="sm" variant="outline" disabled={locked} onClick={load}>Reload saved tests</Button>
      </Flex>
      {!ready && <Text fontSize="sm">Finish indexing and reload these tests before running questions. Previous results remain available below.</Text>}
      {!work.contexts.length && <Text fontSize="sm">Assign a vehicle or topic under document coverage before adding a test question.</Text>}
      {document.source_revision !== work.source_revision && <Text role="status">This document changed. Reload saved tests to use its latest revision.</Text>}
      <Flex gap={3} wrap="wrap">
        <Button variant="outline" disabled={locked || !work.contexts.length} onClick={() => edit()}>Add test question</Button>
        <Button disabled={locked || !ready || savedRunning || !chosen.some((id) => work.questions.some((question) => question.id === id))}
          onClick={() => runQuestions(work.questions.filter((question) => chosen.includes(question.id)))}>Run selected questions ({chosen.filter((id) => work.questions.some((question) => question.id === id)).length})</Button>
      </Flex>
      {showForm && <Stack gap={3} p={4} bg="canvas" borderRadius="8px">
        <Heading size="sm">{editing ? "Edit Test Question" : "New Test Question"}</Heading>
        <FormField label="Test context"><AdminSelect value={form.context} disabled={loading || !!running} onChange={(event) => setForm({ ...form, context: event.target.value })}>
          <option value="">Choose a covered vehicle or topic</option>
          {work.contexts.map((context) => <option key={`${context.scope_type}:${context.scope_id}`} value={`${context.scope_type}:${context.scope_id}`}>{context.label} · {context.scope_type}</option>)}
        </AdminSelect></FormField>
        <FormField label="Test question"><Textarea value={form.question} maxLength={4000} disabled={loading || !!running} onChange={(event) => setForm({ ...form, question: event.target.value })} /></FormField>
        <FormField label="Expected behavior or reference note (optional)" hint="A note for the reviewer. It is not sent to the answer model."><Textarea value={form.expected} maxLength={2000} disabled={loading || !!running} onChange={(event) => setForm({ ...form, expected: event.target.value })} /></FormField>
        <Flex gap={3} wrap="wrap"><Button disabled={loading || !!running || !form.question.trim() || !form.context || reviewDirty} onClick={() => saveQuestion()}>Save test question</Button>
          <Button variant="outline" disabled={loading || !!running} onClick={() => { setShowForm(false); setForm(emptyForm); setEditing(null); }}>Discard question edits</Button></Flex>
      </Stack>}
      <Stack gap={3} aria-label="Saved test questions">
        {work.questions.map((question) => {
          const latest = work.runs.find((run) => run.question_id === question.id);
          return <Box key={question.id} ref={question.id === requestedQuestion ? linkedQuestionRef : null}
            tabIndex={question.id === requestedQuestion ? -1 : undefined} scrollMarginTop="130px"
            borderWidth="1px" borderColor={question.id === requestedQuestion ? "blue.500" : undefined} borderRadius="8px" p={4}>
            <Flex gap={3} align="start"><Checkbox checked={chosen.includes(question.id)} disabled={locked || !chosen.includes(question.id) && chosen.length >= 10}
              onCheckedChange={(event) => setChosen(event.checked === true ? [...chosen, question.id] : chosen.filter((id) => id !== question.id))}>
                <Box as="span" srOnly>Select {question.question}</Box>
              </Checkbox>
              <Stack gap={2} flex={1} minW={0}><Text fontWeight="600" overflowWrap="anywhere">{question.question}</Text>
                <Text fontSize="xs" color="muted">Context: {work.contexts.find((context) => context.scope_type === question.scope_type && context.scope_id === question.scope_id)?.label || "No longer available — edit before testing"}</Text>
                {question.expected && <Text fontSize="sm" color="muted">Expected: {question.expected}</Text>}
                <Flex gap={2} wrap="wrap"><Button size="xs" disabled={locked || !ready || savedRunning} onClick={() => runQuestions([question])}>Run question</Button>
                  <Button size="xs" variant="outline" disabled={locked} onClick={() => edit(question)}>Edit question</Button>
                  {latest && <Button size="xs" variant="outline" disabled={locked} onClick={() => setRunId(latest.id)}>View latest result</Button>}
                  <Button size="xs" variant="plain" disabled={locked} onClick={() => saveQuestion(false, question)}>Archive question</Button></Flex>
              </Stack></Flex>
          </Box>;
        })}
        {!work.questions.length && <Text>No saved questions yet. Add a question about an instruction, condition or table in this reference.</Text>}
      </Stack>
      <Text fontSize="sm" color="muted">Select up to 10 questions per batch. Each completed result is saved independently. Passing a test records your review; it does not establish that every instruction in the document is correct.</Text>
      {running && <Flex gap={3} align="center" wrap="wrap"><Text role="status">Running {running.position} of {running.total}: {running.name}</Text>
        <Button size="sm" variant="outline" onClick={() => { stop.current = true; setNotice("The batch will stop after the current question finishes."); }}>Stop after current test</Button></Flex>}
      {savedRunning && !running && <Text role="status">A saved test is still running. Results refresh automatically.</Text>}
      {!!work.runs.length && <>
        <FormField label="Saved test results" hint="The latest 50 runs, plus the linked result when it is older."><AdminSelect value={activeRun?.id || ""} disabled={locked} onChange={(event) => setRunId(event.target.value)}>
          {!activeRun && <option value="">Choose a saved result</option>}
          {work.runs.map((run) => <option key={run.id} value={run.id}>{new Date(run.started_at).toLocaleString()} · {run.question_snapshot.question.slice(0, 80)} · {run.outdated ? "Out of date" : run.status} · {decisions[run.decision]}</option>)}
        </AdminSelect></FormField>
        {activeRun && <Box ref={resultRef} tabIndex={-1} scrollMarginTop="130px"><TestResult key={`${activeRun.id}:${activeRun.review_version}`} run={activeRun} document={document} stale={stale}
          disabled={loading || !!running || dirty} onDirty={setReviewDirty} onSave={(body) => saveReview(activeRun, body)} /></Box>}
      </>}
    </Stack>}
  </Box>;
}

function TestResult({ run, document, stale, disabled, onDirty, onSave }) {
  const [decision, setDecision] = useState(run.decision);
  const [note, setNote] = useState(run.review_note);
  const dirty = decision !== run.decision || note !== run.review_note;
  const result = run.result;
  useEffect(() => { onDirty(dirty); return () => onDirty(false); }, [dirty, onDirty]);
  const reviewable = !stale && run.status === "completed";
  return <Stack gap={4} borderTopWidth="1px" pt={5}>
    <Heading size="md">{run.question_snapshot.question}</Heading>
    <Text fontSize="sm">Context: {run.context_label} · Run {new Date(run.started_at).toLocaleString()}</Text>
    {run.question_snapshot.expected && <Text fontSize="sm">Review note: {run.question_snapshot.expected}</Text>}
    <Flex gap={2} wrap="wrap"><Badge colorPalette={stale || run.status === "failed" ? "orange" : "gray"}>{stale ? "Out of date — rerun required" : run.status}</Badge>
      <Badge colorPalette={run.decision === "passed" ? "green" : run.decision === "needs_fixing" ? "orange" : "gray"}>{decisions[run.decision]}</Badge></Flex>
    {stale && <Text fontSize="sm">{run.outdated_reason || "The document or its verification state changed. Rerun this test before reviewing it."} This saved answer remains a historical result.</Text>}
    {run.error && <Text role="alert">{run.error}</Text>}
    {result && <>
      <Heading size="sm">Answer · {outcomes[result.response_type] || result.response_type}</Heading>
      {!result.sources.length && <Text fontSize="sm" color="orange.800">This answer has no document citations. Review whether general information, clarification or insufficient evidence is appropriate for the question.</Text>}
      {reasons[result.diagnostics.reason] && <Text fontSize="sm" color="orange.800">{reasons[result.diagnostics.reason]}</Text>}
      <Box bg="canvas" p={4} borderRadius="8px"><ChatAnswer>{result.answer}</ChatAnswer></Box>
      {result.sources.length > 0 && <Text fontSize="sm">Citations: {result.sources.map((source) => `${source.label}${source.section_path?.length ? ` · ${source.section_path.join(" → ")}` : ""}`).join("; ")}</Text>}
      <Heading size="sm">Retrieved Evidence</Heading>
      <Text fontSize="sm" color="muted">Retrieved content may be unused or excluded. Citation labels identify evidence cited by the answer. Page links appear only where source mapping is available.</Text>
      {result.evidence.map((evidence, index) => <Box as="details" key={`${evidence.chunk_id}:${evidence.element_id}:${index}`} open={index === 0} borderWidth="1px" borderRadius="8px" p={3}>
        <Box as="summary" cursor="pointer">{evidence.label ? `${evidence.label} · ` : ""}{evidence.kind} · {evidence.cited ? "Cited" : evidence.selected_reference ? "Selected Reference" : evidence.eligible ? "Available, Not Cited" : "Not Supplied as Answer Evidence"}</Box>
        <Stack gap={3} mt={3}>
          {evidence.section_path.length > 0 && <Text fontSize="sm">{evidence.section_path.join(" → ")}</Text>}
          {evidence.exclusion && <Text fontSize="sm" color="orange.800">Excluded: {evidence.exclusion}</Text>}
          {evidence.kind === "table" && evidence.html ? <Box overflowX="auto" maxH="400px" css={{ "& table": { width: "100%", borderCollapse: "collapse" }, "& td, & th": { padding: "8px", border: "1px solid #aab4bf" } }} dangerouslySetInnerHTML={{ __html: evidence.html }} />
            : <Text fontSize="sm" whiteSpace="pre-wrap">{evidence.excerpt || evidence.caption || "Inspect the original reference."}</Text>}
          {evidence.kind === "image" && <Text fontSize="xs" color="muted">The description is a search aid. Compare the original illustration and its labels.</Text>}
          {!stale && evidence.image_path && <img src={`${API_URL}${evidence.image_path}`} crossOrigin="use-credentials" alt={evidence.caption || "Retrieved original illustration"} style={{ maxWidth: "100%", maxHeight: 400, objectFit: "contain" }} />}
          {!stale && <Flex gap={2} wrap="wrap">{(evidence.pages.length ? evidence.pages : [null]).map((page) => <Button key={page || "original"} asChild size="xs" variant="outline"><a href={`${originalDocumentUrl(document.id, run.source_revision)}${page ? `#page=${page}` : ""}`} target="_blank" rel="noopener noreferrer">{page ? `Open original page ${page}` : "Open original document"}</a></Button>)}</Flex>}
        </Stack>
      </Box>)}
      {!result.evidence.length && <Text>No document passages were retrieved for this response.</Text>}
      <Box as="details"><Box as="summary" cursor="pointer">Test Details</Box><Text fontSize="sm" mt={2}>Provider: {result.diagnostics.provider || "Not used"} · Model: {result.diagnostics.model || "Not used"} · {(result.diagnostics.elapsed_ms / 1000).toFixed(1)} seconds</Text>
        <Text fontSize="sm">{result.diagnostics.retrieved_count} retrieved; {result.diagnostics.eligible_count} eligible.{result.diagnostics.evidence_truncated ? " Evidence preview limited to 20 records." : ""}{result.diagnostics.fallback_used ? " A fallback provider was used." : ""}</Text>
        {result.diagnostics.reason && <Text fontSize="sm">Decision detail: {result.diagnostics.reason}</Text>}</Box>
    </>}
    {run.status === "completed" ? <Stack gap={3} bg="canvas" p={4} borderRadius="8px">
      <Heading size="sm">Review This Result</Heading>
      <FormField label="Test review decision"><AdminSelect value={decision} disabled={disabled || !reviewable} onChange={(event) => setDecision(event.target.value)}>{Object.entries(decisions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</AdminSelect></FormField>
      <FormField label="Test review note"><Textarea value={note} maxLength={2000} disabled={disabled || !reviewable} onChange={(event) => setNote(event.target.value)} placeholder="Record incorrect values, missing conditions, or evidence to check." /></FormField>
      <Flex gap={3} wrap="wrap"><Button disabled={disabled || !reviewable || !dirty || decision === "needs_fixing" && !note.trim()} onClick={() => onSave({ version: run.review_version, decision, note })}>Save test review</Button>
        {dirty && <Button variant="outline" disabled={disabled} onClick={() => { setDecision(run.decision); setNote(run.review_note); }}>Discard review edits</Button>}</Flex>
    </Stack> : run.review_note && <Text fontSize="sm">Saved review: {run.review_note}</Text>}
  </Stack>;
}
