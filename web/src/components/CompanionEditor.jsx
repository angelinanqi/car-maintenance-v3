"use client";

import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Field,
  Flex,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { Checkbox } from "./ui/checkbox";
import { AdminSelect } from "./admin/NativeControls";
import TiptapEditor from "./editor/TipTapEditor";

export default function CompanionEditor({
  value,
  onChange,
  content,
  uploadImage,
}) {
  const [sections, setSections] = useState([]);
  const [preview, setPreview] = useState(null);
  const [previewAnswer, setPreviewAnswer] = useState(null);
  useEffect(() => {
    const document = new DOMParser().parseFromString(content, "text/html");
    setSections(
      [...document.querySelectorAll("h2[data-section-id]")].map((heading) => {
        let sectionContent = heading.outerHTML;
        for (
          let sibling = heading.nextElementSibling;
          sibling && sibling.tagName !== "H2";
          sibling = sibling.nextElementSibling
        )
          sectionContent += sibling.outerHTML;
        return {
          id: heading.getAttribute("data-section-id"),
          title: heading.textContent,
          content: sectionContent,
        };
      }),
    );
  }, [content]);
  const steps = value.exploration?.steps || [];
  function update(patch) {
    onChange({ ...value, ...patch });
  }
  function setSteps(next) {
    update({ exploration: next.length ? { version: 1, steps: next } : null });
  }
  function editStep(index, patch) {
    setSteps(
      steps.map((step, at) => (at === index ? { ...step, ...patch } : step)),
    );
  }
  function editActivity(index, patch) {
    editStep(index, { activity: { ...steps[index].activity, ...patch } });
  }
  function editOption(index, optionIndex, patch) {
    editActivity(index, {
      options: steps[index].activity.options.map((option, at) =>
        at === optionIndex ? { ...option, ...patch } : option,
      ),
    });
  }
  return (
    <Stack gap={5} bg="gray.50" p={5} borderRadius="lg">
      <Text fontSize="xl" fontWeight="semibold">
        Learning companion
      </Text>
      <Text>
        Use H2 headings in the guide to create reusable learning sections.
        Examples and activity feedback are authored here and published with this
        guide.
      </Text>
      <Checkbox
        checked={value.beginner_friendly}
        onCheckedChange={(event) =>
          update({ beginner_friendly: event.checked === true })
        }
      >
        Suitable for beginners
      </Checkbox>
      <Checkbox
        checked={value.featured_in_companion}
        onCheckedChange={(event) =>
          update({ featured_in_companion: event.checked === true })
        }
      >
        Feature as a companion starting point
      </Checkbox>
      <Field.Root>
        <Field.Label>Learning outcomes (one per line)</Field.Label>
        <Textarea
          value={value.learning_outcomes.join("\n")}
          onChange={(event) =>
            update({ learning_outcomes: event.target.value.split("\n") })
          }
        />
      </Field.Root>
      {steps.map((step, index) => (
        <Stack key={step.id} gap={4} bg="white" p={5} borderRadius="lg">
          <Flex gap={2} align="center" wrap="wrap">
            <Text flex="1" fontWeight="semibold">
              {sections.find((section) => section.id === step.section_id)
                ?.title || "Select a section"}
            </Text>
            <Button
              variant="outline"
              disabled={index === 0}
              onClick={() => {
                const next = [...steps];
                [next[index - 1], next[index]] = [next[index], next[index - 1]];
                setSteps(next);
              }}
            >
              Move up
            </Button>
            <Button
              variant="outline"
              disabled={index === steps.length - 1}
              onClick={() => {
                const next = [...steps];
                [next[index], next[index + 1]] = [next[index + 1], next[index]];
                setSteps(next);
              }}
            >
              Move down
            </Button>
            <Button
              variant="ghost"
              onClick={() => setSteps(steps.filter((_, at) => at !== index))}
            >
              Remove
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setPreview(preview === step.id ? null : step.id);
                setPreviewAnswer(null);
              }}
            >
              Preview learner view
            </Button>
          </Flex>
          <Field.Root>
            <Field.Label>Guide section</Field.Label>
            <AdminSelect
              value={step.section_id}
              onChange={(event) =>
                editStep(index, { section_id: event.target.value })
              }
            >
              <option value="">Choose an H2 section</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.title}
                </option>
              ))}
            </AdminSelect>
          </Field.Root>
          <Text fontWeight="semibold">Optional example</Text>
          <TiptapEditor
            content={step.example_html}
            onChange={(html) => editStep(index, { example_html: html })}
            uploadImage={uploadImage}
          />
          <Checkbox
            checked={!!step.activity}
            onCheckedChange={(event) =>
              editStep(index, {
                activity: event.checked
                  ? {
                      prompt: "",
                      expected_option_id: "a",
                      options: [
                        { id: "a", text: "", feedback: "" },
                        { id: "b", text: "", feedback: "" },
                      ],
                    }
                  : null,
              })
            }
          >
            Include an optional situation to try
          </Checkbox>
          {step.activity && (
            <>
              <Field.Root>
                <Field.Label>Situation and question</Field.Label>
                <Textarea
                  value={step.activity.prompt}
                  onChange={(event) =>
                    editActivity(index, { prompt: event.target.value })
                  }
                />
              </Field.Root>
              {step.activity.options.map((option, optionIndex) => (
                <Box key={option.id}>
                  <Field.Root mb={2}>
                    <Field.Label>Answer option {optionIndex + 1}</Field.Label>
                    <Input
                      value={option.text}
                      onChange={(event) =>
                        editOption(index, optionIndex, {
                          text: event.target.value,
                        })
                      }
                    />
                  </Field.Root>
                  <Field.Root>
                    <Field.Label>
                      Explanation after choosing this answer
                    </Field.Label>
                    <Textarea
                      value={option.feedback}
                      onChange={(event) =>
                        editOption(index, optionIndex, {
                          feedback: event.target.value,
                        })
                      }
                    />
                  </Field.Root>
                </Box>
              ))}
              <Field.Root>
                <Field.Label>Expected answer</Field.Label>
                <AdminSelect
                  value={step.activity.expected_option_id}
                  onChange={(event) =>
                    editActivity(index, {
                      expected_option_id: event.target.value,
                    })
                  }
                >
                  {step.activity.options.map((option, optionIndex) => (
                    <option key={option.id} value={option.id}>
                      {option.text || `Answer option ${optionIndex + 1}`}
                    </option>
                  ))}
                </AdminSelect>
              </Field.Root>
              <Text fontSize="sm">
                The learner sees the question, choices and your explanatory
                feedback. No score or mastery claim is shown.
              </Text>
            </>
          )}
          {preview === step.id && (
            <Stack gap={3} bg="gray.50" p={4}>
              <Text fontWeight="semibold">Learner preview</Text>
              <TiptapEditor
                key={`preview-${step.section_id}-${content}`}
                readOnly
                content={
                  sections.find((section) => section.id === step.section_id)
                    ?.content || "<p>Select a section.</p>"
                }
              />
              {step.example_html && (
                <>
                  <Text fontWeight="semibold">An example</Text>
                  <TiptapEditor
                    key={`example-${step.example_html}`}
                    readOnly
                    content={step.example_html}
                  />
                </>
              )}
              {step.activity && (
                <>
                  <Text>{step.activity.prompt}</Text>
                  {step.activity.options.map((option) => (
                    <Button
                      key={option.id}
                      variant="outline"
                      whiteSpace="normal"
                      height="auto"
                      py={3}
                      onClick={() => setPreviewAnswer(option.id)}
                    >
                      {option.text || "Answer text"}
                    </Button>
                  ))}
                  {previewAnswer && (
                    <Text role="status">
                      {
                        step.activity.options.find(
                          (option) => option.id === previewAnswer,
                        )?.feedback
                      }
                    </Text>
                  )}
                </>
              )}
            </Stack>
          )}
        </Stack>
      ))}
      <Button
        alignSelf="start"
        variant="outline"
        disabled={!sections.length || steps.length >= 30}
        onClick={() =>
          setSteps([
            ...steps,
            {
              id: crypto.randomUUID(),
              section_id:
                sections.find(
                  (section) =>
                    !steps.some((step) => step.section_id === section.id),
                )?.id || sections[0].id,
              example_html: "",
              activity: null,
            },
          ])
        }
      >
        Add exploration section
      </Button>
      {!sections.length && (
        <Text>
          Add an H2 heading in the content editor to create the first section.
        </Text>
      )}
    </Stack>
  );
}
