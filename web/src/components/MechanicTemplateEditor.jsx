"use client";
import { useEffect, useState } from "react";
import { Button, Field, Input, Stack, Text, Textarea } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { Checkbox } from "./ui/checkbox";

export default function MechanicTemplateEditor() {
  const [loaded, setLoaded] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [questions, setQuestions] = useState(
    [0, 1, 2].map(() => ({ question: "", reason: "" })),
  );
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    request("/admin/companion-settings")
      .then((data) => {
        if (!active) return;
        setEnabled(!!data.mechanic_template);
        if (data.mechanic_template)
          setQuestions(data.mechanic_template.questions);
        setDetails(data.mechanic_details.join("\n"));
        setLoaded(true);
      })
      .catch((error) => {
        if (active) setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function save() {
    setBusy(true);
    setMessage("");
    try {
      await request("/admin/companion-settings", {
        method: "PUT",
        body: {
          mechanic_template: enabled
            ? { concern_summary: "Owner preparation checklist", questions }
            : null,
          mechanic_details: details
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
        },
      });
      setMessage("Preparation content saved.");
    } catch (error) {
      setMessage(error.message);
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
        disabled={!loaded}
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
          value={details}
          onChange={(event) => setDetails(event.target.value)}
        />
      </Field.Root>
      <Button alignSelf="start" disabled={!loaded || busy} onClick={save}>
        Save preparation content
      </Button>
      {message && <Text role="status">{message}</Text>}
    </Stack>
  );
}
