"use client";

import { useEffect, useState } from "react";
import { Badge, Box, Button, Flex, Input, Stack, Text } from "@chakra-ui/react";
import FormField from "@/components/admin/FormField";
import { AdminSelect } from "@/components/admin/NativeControls";
import MaintenanceItemEditor from "@/components/admin/MaintenanceItemEditor";
import type { MaintenanceItem } from "@/api/admin";
import type { Suggestion } from "@/api/maintenanceAssistance";

export default function TaskCheck({
  suggestion,
  items,
  blockedItems,
  disabled,
  onDirty,
  onItem,
  onNavigate,
  onSave,
  onAsk,
}: {
  suggestion: Suggestion;
  items: MaintenanceItem[];
  disabled: boolean;
  onDirty: (dirty: boolean) => void;
  onItem: (item: MaintenanceItem) => void;
  blockedItems: (string | null)[];
  onNavigate: (page: number) => void;
  onSave: (body: {
    status: Suggestion["status"];
    edited_name: string;
    mapped_item_id: string | null;
  }) => void;
  onAsk: (task: Suggestion) => void;
}) {
  const [name, setName] = useState(
    suggestion.edited_name || suggestion.suggested_name,
  );
  const exact = suggestion.catalogue_matches.find(
    (match) => match.method === "exact_text",
  );
  const [mapped, setMapped] = useState(
    suggestion.mapped_item_id || exact?.item_id || "",
  );
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    setName(suggestion.edited_name || suggestion.suggested_name);
    setMapped(suggestion.mapped_item_id || exact?.item_id || "");
  }, [
    suggestion.edited_name,
    suggestion.suggested_name,
    suggestion.mapped_item_id,
    exact?.item_id,
  ]);
  const dirty =
    name !== (suggestion.edited_name || suggestion.suggested_name) ||
    mapped !== (suggestion.mapped_item_id || exact?.item_id || "");
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  const matches = new Set(
    suggestion.catalogue_matches.map((match) => match.item_id),
  );
  const blocked = blockedItems.includes(null) || blockedItems.includes(mapped);
  return (
    <Box bg="canvas" borderRadius="8px" p={4}>
      <Stack gap={4}>
        <Badge alignSelf="start">
          {suggestion.status === "accepted"
            ? "Accepted"
            : suggestion.status === "rejected"
              ? "Skipped"
              : "Needs checking"}
        </Badge>
        <Text fontWeight="600" whiteSpace="pre-wrap">
          From the manual:{" "}
          {suggestion.original_text || suggestion.suggested_name}
        </Text>
        {suggestion.pages?.map((page) => (
          <Button
            key={page}
            variant="outline"
            size="sm"
            alignSelf="start"
            onClick={() => onNavigate(page)}
          >
            Check original page {page}
          </Button>
        ))}
        {(suggestion.potential_duplicate ||
          suggestion.uncertainty.length > 0) && (
          <Text fontSize="sm" color="orange.800">
            {suggestion.potential_duplicate
              ? "A similar task appears elsewhere too. "
              : ""}
            Check the wording and any surrounding notes in the original before
            accepting.
          </Text>
        )}
        <FormField label="Task name">
          <Input
            disabled={disabled}
            maxLength={500}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </FormField>
        <FormField
          label="Which service task does this mean?"
          hint="Choose the inspection, replacement or service that matches the manual. Similar names are suggestions, not confirmed matches."
        >
          <AdminSelect
            disabled={disabled}
            value={mapped}
            onChange={(event) => setMapped(event.target.value)}
          >
            <option value="">Choose a matching service task</option>
            {[...items]
              .filter((item) => item.active || item.id === mapped)
              .sort(
                (a, b) => Number(matches.has(b.id)) - Number(matches.has(a.id)),
              )
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {matches.has(item.id) ? "Suggested: " : ""}
                  {item.title} · {item.action}
                </option>
              ))}
          </AdminSelect>
        </FormField>
        <Button
          alignSelf="start"
          variant="plain"
          size="sm"
          disabled={disabled}
          onClick={() => setCreating(true)}
        >
          Add a missing service task
        </Button>
        <Button
          alignSelf="start"
          variant="outline"
          size="sm"
          disabled={disabled || !dirty || !name.trim()}
          onClick={() =>
            onSave({
              status: "suggested",
              edited_name: name.trim(),
              mapped_item_id: mapped || null,
            })
          }
        >
          Save task for later
        </Button>
        {blocked && (
          <Text fontSize="sm" color="orange.800">
            A saved question affects this task. Record its clarification below
            before accepting the task.
          </Text>
        )}
        <Flex gap={3} wrap="wrap">
          <Button
            disabled={disabled || blocked || !name.trim() || !mapped}
            onClick={() =>
              onSave({
                status: "accepted",
                edited_name: name.trim(),
                mapped_item_id: mapped,
              })
            }
          >
            Use this task
          </Button>
          <Button
            variant="outline"
            disabled={disabled || !name.trim()}
            onClick={() =>
              onSave({
                status: "rejected",
                edited_name: name.trim(),
                mapped_item_id: mapped || null,
              })
            }
          >
            Skip this task
          </Button>
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() =>
              onAsk({
                ...suggestion,
                edited_name: name,
                mapped_item_id: mapped || null,
              })
            }
          >
            Needs clarification
          </Button>
        </Flex>
      </Stack>
      {creating && (
        <MaintenanceItemEditor
          initialTitle={name}
          categories={[
            ...new Set(items.map((item) => item.category).filter(Boolean)),
          ]}
          onClose={() => setCreating(false)}
          onSaved={(item) => {
            onItem(item);
            setMapped(item.id);
            setCreating(false);
          }}
        />
      )}
    </Box>
  );
}
