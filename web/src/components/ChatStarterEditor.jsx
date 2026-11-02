"use client";

import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Collapsible,
  Field,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { toaster } from "./ui/toaster";
import useUnsavedChanges from "./admin/useUnsavedChanges";

export default function ChatStarterEditor() {
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [revision, setRevision] = useState(null);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState(null);
  const dirty = saved !== null && text !== saved;
  useUnsavedChanges(dirty);

  useEffect(() => {
    let active = true;
    request("/admin/chat-starters")
      .then((data) => {
        if (!active) return;
        const value = data.questions.join("\n");
        setText(value);
        setSaved(value);
        setRevision(data.updated_at);
      })
      .catch((cause) => {
        if (active) setError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [reload]);

  async function save() {
    if (busy || saved === null) return;
    const questions = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (
      questions.length > 20 ||
      questions.some((question) => question.length > 300) ||
      new Set(questions).size !== questions.length
    ) {
      setError("Use up to 20 unique questions, at most 300 characters each.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await request("/admin/chat-starters", {
        method: "PUT",
        body: { questions, expected_updated_at: revision },
      });
      const value = result.questions.join("\n");
      setText(value);
      setSaved(value);
      setRevision(result.updated_at);
      setConflict(false);
      setLatest(null);
      toaster.create({
        title: "Mobile starter questions saved",
        type: "success",
      });
    } catch (cause) {
      setError(cause.message);
      if (cause.status === 409) setConflict(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box mb={6}>
      <Collapsible.Root>
        <Collapsible.Trigger asChild>
          <Button variant="outline">Mobile starter questions</Button>
        </Collapsible.Trigger>
        <Collapsible.Content pt={4}>
          <Stack gap={3}>
            <Field.Root disabled={busy || saved === null}>
              <Field.Label>
                Starter questions, one per line in display order
              </Field.Label>
              <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={5}
              />
              <Field.HelperText>
                Add, edit, remove or reorder examples for the mobile chat
                welcome screen. An empty list hides them. Devices update when
                chat sources refresh and keep the last synced list offline.
              </Field.HelperText>
            </Field.Root>
            <Button
              alignSelf="start"
              variant="solid"
              onClick={save}
              loading={busy}
              disabled={saved === null || !dirty}
            >
              Save starter questions
            </Button>
          </Stack>
        </Collapsible.Content>
      </Collapsible.Root>
      {error && (
        <Text role="alert" mt={3}>
          {error}
        </Text>
      )}
      {conflict && <Button variant="outline" disabled={busy} onClick={async () => {
        setBusy(true);
        try {
          const data = await request('/admin/chat-starters');
          setRevision(data.updated_at);
          setSaved(data.questions.join('\n'));
          setLatest(data.questions.join('\n'));
          setConflict(false);
          setError('Latest saved version loaded. Your edits are kept; compare them before saving again.');
        } catch (cause) { setError(cause.message); }
        finally { setBusy(false); }
      }}>Reload saved version and keep my edits</Button>}
      {latest !== null && <Text whiteSpace="pre-wrap" mt={2}>Latest saved questions: {latest || '(empty)'}</Text>}
      {error && saved === null && <Button mt={3} variant="outline" onClick={() => { setError(""); setReload((value) => value + 1); }}>Retry loading starter questions</Button>}
    </Box>
  );
}
