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
  initialTitle = "",
  categories,
  onClose,
  onSaved,
}: {
  row?: MaintenanceItem;
  initialTitle?: string;
  categories: string[];
  onClose: () => void;
  onSaved: (row: MaintenanceItem) => void;
}) {
  const original = {
    title: row?.title || initialTitle,
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
      title={row ? "Edit service task" : "Add service task"}
      description="Give the service task a clear name, such as Replace engine oil. You will set when it is needed in the vehicle’s service schedule."
      busy={busy}
      dirty={JSON.stringify(draft) !== JSON.stringify(original)}
      error={error}
      onClose={onClose}
      onSubmit={submit}
      saveLabel={row ? "Save item" : "Add item"}
    >
      <FormField
        label="Service task name"
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
        hint="Choose or enter a group such as Engine and fluids to help find this task later."
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
