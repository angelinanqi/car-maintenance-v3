"use client";

import { Checkbox } from "@/components/ui/checkbox";

import { useState, type FormEvent } from "react";
import { Box, Input, Text, Textarea } from "@chakra-ui/react";
import FormField from "./FormField";
import RecordDialog from "./RecordDialog";
import { AdminSelect } from "./NativeControls";
import CategoryInput from "./CategoryInput";
import { saveItem, type MaintenanceItem } from "@/api/admin";

export default function MaintenanceItemEditor({
  row,
  categories,
  onClose,
  onSaved,
}: {
  row?: MaintenanceItem;
  categories: string[];
  onClose: () => void;
  onSaved: (row: MaintenanceItem) => void;
}) {
  const original = {
    title: row?.title || "",
    category: row?.category || "",
    description: row?.description || "",
    action: row?.action || "inspect",
    active: row?.active ?? true,
  };
  const [draft, setDraft] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [titleError, setTitleError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!draft.title.trim()) {
      setTitleError("Enter a name for this operation.");
      return;
    }
    setBusy(true);
    setError("");
    setTitleError("");
    try {
      onSaved(
        await saveItem(row?.id || "", {
          ...draft,
          title: draft.title.trim(),
          category: draft.category.trim(),
          description: draft.description.trim(),
        }),
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <RecordDialog
      title={row ? "Edit maintenance item" : "Add maintenance item"}
      description="Define one reusable operation. Distance and time intervals belong in a vehicle’s Service schedules, not in this item."
      busy={busy}
      dirty={JSON.stringify(draft) !== JSON.stringify(original)}
      error={error}
      onClose={onClose}
      onSubmit={submit}
      saveLabel={row ? "Save item" : "Add item"}
    >
      <FormField
        label="Item name"
        error={titleError}
        hint="Name the operation clearly, for example Inspect tyre pressure or Replace engine oil."
      >
        <Input
          required
          maxLength={200}
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
        />
      </FormField>
      <FormField
        label="Action"
        hint={
          row
            ? "This action is fixed to preserve existing schedules and service history. Add a separate item if the action should be different."
            : "Inspection checks a condition; replacement changes a part or fluid; service covers other maintenance work."
        }
      >
        <AdminSelect
          disabled={Boolean(row)}
          value={draft.action}
          onChange={(e) =>
            setDraft({
              ...draft,
              action: e.target.value as MaintenanceItem["action"],
            })
          }
        >
          <option value="inspect">Inspect</option>
          <option value="replace">Replace</option>
          <option value="service">Service</option>
        </AdminSelect>
      </FormField>
      <FormField
        label="Category (optional)"
        hint="Choose an existing category or enter a new one. This groups maintenance items; it does not create a learning category."
      >
        <CategoryInput
          options={categories}
          value={draft.category}
          onChange={(category) => setDraft({ ...draft, category })}
          placeholder="e.g. Engine and fluids"
        />
      </FormField>
      <FormField
        label="Description (optional)"
        hint="Explain what the operation covers. Use source-reviewed vehicle schedules for intervals."
      >
        <Textarea
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
      </FormField>
      <Box bg="canvas" p={4} borderRadius="8px">
        <Checkbox
          checked={draft.active}
          onCheckedChange={(e) =>
            setDraft({ ...draft, active: e.checked === true })
          }
        >
          Available for new schedules and item selections
        </Checkbox>
        <Text color="muted" fontSize="sm" mt={2}>
          Deactivate an obsolete item instead of deleting it. Existing records
          and references are preserved.
        </Text>
      </Box>
    </RecordDialog>
  );
}
