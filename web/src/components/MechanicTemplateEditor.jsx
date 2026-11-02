"use client";
import { useEffect, useState } from "react";
import { Button, Field, Input, Stack, Text, Textarea } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { Checkbox } from "./ui/checkbox";
import useUnsavedChanges from './admin/useUnsavedChanges';

export default function MechanicTemplateEditor() {
  const [loaded, setLoaded] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [questions, setQuestions] = useState(
    [0, 1, 2].map(() => ({ question: "", reason: "" })),
  );
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [revision, setRevision] = useState(null);
  const [saved, setSaved] = useState(null);
  const [reload, setReload] = useState(0);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState(null);
  const current = JSON.stringify({ enabled, questions, details });
  useUnsavedChanges(saved !== null && current !== saved);
  useEffect(() => {
    let active = true;
    request("/admin/companion-settings")
      .then((data) => {
        if (!active) return;
        setEnabled(!!data.mechanic_template);
        if (data.mechanic_template)
          setQuestions(data.mechanic_template.questions);
        setDetails(data.mechanic_details.join("\n"));
        setRevision(data.updated_at);
        setSaved(JSON.stringify({ enabled: !!data.mechanic_template,
          questions: data.mechanic_template?.questions || [0, 1, 2].map(() => ({ question: '', reason: '' })),
          details: data.mechanic_details.join('\n') }));
        setMessage('');
        setLoaded(true);
      })
      .catch((error) => {
        if (active) setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, [reload]);
  async function save() {
    if (!loaded || busy) return;
    if (enabled && questions.some(item => !item.question.trim() || !item.reason.trim())) {
      setMessage('Complete every checklist question and its reason before saving.');
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const result = await request("/admin/companion-settings", {
        method: "PUT",
        body: {
          expected_updated_at: revision,
          mechanic_template: enabled
            ? { concern_summary: "Owner preparation checklist", questions }
            : null,
          mechanic_details: details
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
        },
      });
      setRevision(result.updated_at);
      setSaved(current);
      setConflict(false);
      setLatest(null);
      setMessage("Preparation content saved.");
    } catch (error) {
      setMessage(error.message);
      if (error.status === 409) setConflict(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Stack gap={4}>
      <Text fontSize="xl" fontWeight="semibold">
        Mechanic preparation content
      </Text>
      <Text>
        Publish an optional checklist for when personalised generation is
        unavailable. The owner's concern is inserted separately.
      </Text>
      <Checkbox
        checked={enabled}
        disabled={!loaded || busy}
        onCheckedChange={(event) => setEnabled(event.checked === true)}
      >
        Enable the administrator checklist
      </Checkbox>
      {enabled &&
        questions.map((item, index) => (
          <Stack key={index} gap={2}>
            <Field.Root>
              <Field.Label>Question {index + 1}</Field.Label>
              <Input
                disabled={busy}
                maxLength={300}
                value={item.question}
                onChange={(event) =>
                  setQuestions(
                    questions.map((old, at) =>
                      at === index
                        ? { ...old, question: event.target.value }
                        : old,
                    ),
                  )
                }
              />
            </Field.Root>
            <Field.Root>
              <Field.Label>Why this question helps</Field.Label>
              <Input
                disabled={busy}
                maxLength={300}
                value={item.reason}
                onChange={(event) =>
                  setQuestions(
                    questions.map((old, at) =>
                      at === index
                        ? { ...old, reason: event.target.value }
                        : old,
                    ),
                  )
                }
              />
            </Field.Root>
          </Stack>
        ))}
      <Field.Root>
        <Field.Label>Things to bring or note (one per line)</Field.Label>
        <Textarea
          disabled={!loaded || busy}
          value={details}
          onChange={(event) => setDetails(event.target.value)}
        />
      </Field.Root>
      <Button alignSelf="start" disabled={!loaded || busy} onClick={save}>
        Save preparation content
      </Button>
      {message && <Text role="status">{message}</Text>}
      {!loaded && message && <Button variant="outline" onClick={() => setReload(value => value + 1)}>Retry loading preparation content</Button>}
      {conflict && <Button variant="outline" disabled={busy} onClick={async () => {
        setBusy(true);
        try {
          const data = await request('/admin/companion-settings');
          setRevision(data.updated_at);
          setLatest(data);
          setConflict(false);
          setMessage('Latest saved version loaded. Your edits are kept; review before saving again.');
        } catch (error) { setMessage(error.message); }
        finally { setBusy(false); }
      }}>Reload saved version and keep my edits</Button>}
      {latest && <Stack aria-label="Latest saved preparation content">
        <Text fontWeight="semibold">Latest saved version</Text>
        {(latest.mechanic_template?.questions || []).map((item, index) => <Text key={index}>{item.question} — {item.reason}</Text>)}
        <Text>{latest.mechanic_template ? 'Checklist enabled' : 'Checklist disabled'}</Text>
        <Text whiteSpace="pre-wrap">{latest.mechanic_details.join('\n')}</Text>
      </Stack>}
    </Stack>
  );
}
