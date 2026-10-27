"use client";

import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Collapsible,
  Flex,
  Grid,
  Heading,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import FormField from "./FormField";
import { AdminSelect } from "./NativeControls";
import { scheduleEntryIssues, serviceInstruction } from "@/lib/adminJourney.mjs";
import { loadReview, type Review } from "@/api/maintenanceAssistance";
import type {
  MaintenanceItem,
  ScheduleEntry,
  SourceDocument,
} from "@/api/admin";

export default function ServiceTaskEditor({
  entry,
  index,
  items,
  sources,
  disabled,
  onChange,
  onRemove,
  onSource,
  onClarify,
}: {
  entry: ScheduleEntry;
  index: number;
  items: MaintenanceItem[];
  sources: SourceDocument[];
  disabled: boolean;
  onChange: (entry: ScheduleEntry) => void;
  onRemove: () => void;
  onSource: (documentId?: string, page?: number) => void;
  onClarify: () => void;
}) {
  const item = items.find((item) => item.id === entry.itemId);
  const source = sources.find(
    (document) => document.id === entry.rule.sourceDocumentId,
  );
  const issues = scheduleEntryIssues(entry, sources);
  const replacement = source
    ? sources.find((document) => document.id === source.superseded_by_id) ||
      sources.find(
        (document) =>
          document.replacement_for_id === source.id &&
          !document.superseded_by_id,
      )
    : undefined;
  function ruleChange(values: Partial<ScheduleEntry["rule"]>) {
    onChange({ ...entry, rule: { ...entry.rule, ...values } });
  }
  return (
    <Box id={`schedule-task-${index + 1}`} bg="white" borderWidth="1px" borderRadius="10px" p={5}>
      <Collapsible.Root defaultOpen={!entry.itemId}>
        <Heading size="md">
          {index + 1}. {item?.title || "New service task"}
        </Heading>
        <Text mt={2}>{serviceInstruction(entry)}</Text>
        {entry.rule.conditions && entry.rule.type !== "informational" && (
          <Text fontSize="sm" color="muted" mt={1}>
            Applies when: {entry.rule.conditions}
          </Text>
        )}
        <Text mt={2} fontSize="sm" color="muted">
          {source
            ? `Reference: ${source.name}${entry.rule.sourcePage ? `, page ${entry.rule.sourcePage}` : ""}`
            : "Choose the manual that supports this instruction."}
        </Text>
        {!disabled && issues.length > 0 && (
          <Text mt={2} color="orange.800">
            Before publishing: {issues.join(" ")}
          </Text>
        )}
        {source?.superseded_by_id && (
          <Text mt={2} color="orange.800" fontSize="sm">
            This task still references an older manual. Check it against the
            replacement and update its reference when confirmed.
          </Text>
        )}
        {replacement && !disabled && (
          <Box bg="brand.50" p={3} borderRadius="8px" mt={3}>
            <Text fontSize="sm">
              An updated manual is available. Switching references keeps this
              task’s interval and conditions for you to check, and clears the
              old page.
            </Text>
            <Button
              variant="outline"
              size="sm"
              mt={2}
              onClick={() => {
                ruleChange({
                  sourceDocumentId: replacement.id,
                  sourceRevision: replacement.source_revision,
                  sourcePage: null,
                  sourceTableId: null,
                  sourceSuggestionId: null,
                });
                onSource(replacement.id, 1);
              }}
            >
              Check this task against the updated manual
            </Button>
          </Box>
        )}
        <Button
          mt={3}
          variant="plain"
          size="sm"
          disabled={!source}
          onClick={onClarify}
        >
          Something unclear? Save a question
        </Button>
        <Collapsible.Trigger asChild>
          <Button mt={3} variant="outline" size="sm">
            {disabled ? "View task details" : "Edit task details"}
          </Button>
        </Collapsible.Trigger>
        <Collapsible.Content pt={4}>
          <Stack gap={4}>
            <FormField
              label="What needs to be done?"
              hint="Choose an inspection, replacement or service task. The action belongs to the selected task."
            >
              <AdminSelect
                disabled={disabled}
                value={entry.itemId || ""}
                onChange={(event) => {
                  const next = items.find(
                    (item) => item.id === event.target.value,
                  );
                  onChange({
                    ...entry,
                    itemId: next?.id || null,
                    action: next?.action || "replace",
                    rule: { ...entry.rule, sourceSuggestionId: null },
                  });
                }}
              >
                <option value="">Choose a service task</option>
                {items
                  .filter((item) => item.active || item.id === entry.itemId)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title} (
                      {item.action === "inspect"
                        ? "inspect"
                        : item.action === "replace"
                          ? "replace"
                          : "service"}
                      )
                    </option>
                  ))}
              </AdminSelect>
            </FormField>
            <FormField label="When is it needed?">
              <AdminSelect
                disabled={disabled}
                value={entry.rule.type}
                onChange={(event) =>
                  ruleChange({
                    type: event.target.value as ScheduleEntry["rule"]["type"],
                    distanceKm: null,
                    months: null,
                    distanceMilestones: [],
                    monthMilestones: [],
                    vehicleStartDate: null,
                  })
                }
              >
                <option value="recurring">
                  At a regular distance or time interval
                </option>
                <option value="milestone">
                  At specific mileages or vehicle ages
                </option>
                <option value="informational">
                  Only when a stated condition applies
                </option>
              </AdminSelect>
            </FormField>
            {entry.rule.type === "recurring" && (
              <>
                <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={4}>
                  {(["distanceKm", "months"] as const).map((key) => (
                    <FormField
                      key={key}
                      label={
                        key === "distanceKm"
                          ? "Every how many kilometres?"
                          : "Every how many months?"
                      }
                    >
                      <Input
                        disabled={disabled}
                        type="number"
                        min={1}
                        step={1}
                        value={entry.rule[key] ?? ""}
                        placeholder={
                          key === "distanceKm" ? "e.g. 10000" : "e.g. 6"
                        }
                        onChange={(event) =>
                          ruleChange({
                            [key]: event.target.value
                              ? Number(event.target.value)
                              : null,
                          })
                        }
                      />
                    </FormField>
                  ))}
                </Grid>
                <Text fontSize="sm" color="muted">
                  Enter the interval stated in the manual. If both are given,
                  whichever comes first applies.
                </Text>
              </>
            )}
            {entry.rule.type === "milestone" && (
              <>
                <ServicePoints
                  key={`km:${entry.itemId}`}
                  label="At these mileages (km)"
                  values={entry.rule.distanceMilestones}
                  disabled={disabled}
                  onChange={(values) =>
                    ruleChange({ distanceMilestones: values })
                  }
                />
                <ServicePoints
                  key={`months:${entry.itemId}`}
                  label="At these vehicle ages (months)"
                  values={entry.rule.monthMilestones}
                  disabled={disabled}
                  onChange={(values) => ruleChange({ monthMilestones: values })}
                />
              </>
            )}
            <FormField
              label="Does this apply only in certain conditions?"
              hint="Copy relevant conditions from the manual, such as frequent short journeys. Leave blank if no special conditions are stated."
            >
              <Textarea
                disabled={disabled}
                value={entry.rule.conditions}
                onChange={(event) =>
                  ruleChange({ conditions: event.target.value })
                }
              />
            </FormField>
            <FormField
              label="Additional guidance for drivers (optional)"
              hint="Keep the manufacturer’s meaning. These notes appear in the guidance; use clear language."
            >
              <Textarea
                disabled={disabled}
                value={entry.rule.notes}
                onChange={(event) => ruleChange({ notes: event.target.value })}
              />
            </FormField>
            <FormField label="Which manual supports this instruction?">
              <AdminSelect
                disabled={disabled}
                value={entry.rule.sourceDocumentId || ""}
                onChange={(event) =>
                  ruleChange({
                    sourceDocumentId: event.target.value || null,
                    sourceRevision:
                      sources.find((source) => source.id === event.target.value)
                        ?.source_revision || null,
                    sourceTableId: null,
                    sourceSuggestionId: null,
                    sourcePage: null,
                  })
                }
              >
                <option value="">Choose a reference document</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                    {source.superseded_by_id
                      ? " (previous version)"
                      : source.replacement_for_id
                        ? " (updated version)"
                        : ""}
                  </option>
                ))}
              </AdminSelect>
            </FormField>
            {source?.source_type === "md" && !source.superseded_by_id && (
              <SourceSectionField
                key={`${source.id}:${source.source_revision}`}
                source={source}
                value={entry.rule.sourceTableId || ""}
                disabled={disabled}
                onChange={(tableId) =>
                  ruleChange({
                    sourceTableId: tableId || null,
                    sourceSuggestionId: null,
                    sourceRevision: source.source_revision,
                    sourcePage: null,
                  })
                }
              />
            )}
            {source?.source_type !== "md" && (
              <FormField
                label="Page in the manual"
                hint="Required to publish. Enter the PDF page that supports this task's interval and conditions."
              >
                <Input
                  disabled={disabled}
                  type="number"
                  min={1}
                  step={1}
                  value={entry.rule.sourcePage ?? ""}
                  onChange={(event) =>
                    ruleChange({
                      sourcePage: event.target.value
                        ? Number(event.target.value)
                        : null,
                    })
                  }
                />
              </FormField>
            )}
            <Flex gap={3} wrap="wrap">
              <Button
                variant="outline"
                disabled={!source}
                onClick={() => onSource()}
              >
                Check original instruction
              </Button>
              <Button
                variant="outline"
                colorPalette="red"
                disabled={disabled}
                onClick={onRemove}
              >
                Remove task from draft
              </Button>
            </Flex>
          </Stack>
        </Collapsible.Content>
      </Collapsible.Root>
    </Box>
  );
}

function SourceSectionField({
  source,
  value,
  disabled,
  onChange,
}: {
  source: SourceDocument;
  value: string;
  disabled: boolean;
  onChange: (tableId: string) => void;
}) {
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    loadReview(source.id, source.source_revision, controller.signal)
      .then(setReview)
      .catch((cause) => {
        if (!controller.signal.aborted) setError(cause.message);
      });
    return () => controller.abort();
  }, [source.id, source.source_revision, attempt]);
  const locations = [
    ...(review?.selections || []).map((selection) => ({
      id: selection.table_id,
      title:
        review?.catalogue.tables.find(
          (table) => table.table_id === selection.table_id,
        )?.title || "Checked service table",
    })),
    ...(review?.bookmarks || []).map((bookmark) => ({
      id: bookmark.table_id,
      title: bookmark.section || bookmark.title,
    })),
  ];
  return (
    <FormField
      label="Where in this document is the instruction?"
      hint="Choose a checked table or recorded section. To record a section, use ‘Help me find service tasks’ and enter the task from the manual."
    >
      {error && <Text role="alert">{error}</Text>}
      <AdminSelect
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose a table or section</option>
        {value && !locations.some((location) => location.id === value) && (
          <option value={value}>Previously checked location</option>
        )}
        {locations.map((location) => (
          <option key={location.id} value={location.id}>
            {location.title}
          </option>
        ))}
      </AdminSelect>
      <Button
        variant="plain"
        size="sm"
        disabled={disabled}
        onClick={() => setAttempt((attempt) => attempt + 1)}
      >
        Refresh recorded sections
      </Button>
    </FormField>
  );
}

function ServicePoints({
  label,
  values,
  disabled,
  onChange,
}: {
  label: string;
  values: number[];
  disabled: boolean;
  onChange: (values: number[]) => void;
}) {
  const [text, setText] = useState(values.join(", "));
  const [error, setError] = useState("");
  return (
    <FormField
      label={label}
      hint="Separate the service points with commas, for example 1000, 10000, 20000."
    >
      <Input
        disabled={disabled}
        value={text}
        aria-invalid={Boolean(error)}
        onChange={(event) => {
          const text = event.target.value;
          setText(text);
          const values = text.trim()
            ? text.split(",").map((value) => Number(value.trim()))
            : [];
          const invalid = values.some(
            (value, index) =>
              !Number.isSafeInteger(value) ||
              value <= 0 ||
              (index > 0 && value <= values[index - 1]),
          );
          setError(
            invalid
              ? "Enter positive whole numbers in increasing order, with no repeats."
              : "",
          );
          onChange(invalid ? [-1] : values);
        }}
      />
      {error && <Text role="alert">{error}</Text>}
    </FormField>
  );
}
