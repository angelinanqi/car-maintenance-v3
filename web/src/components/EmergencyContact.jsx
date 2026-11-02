"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Card,
  Field,
  Flex,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import useUnsavedChanges from "./admin/useUnsavedChanges";
import useEmergencyDraft from "./admin/useEmergencyDraft";

export default function EmergencyContact({
  contact,
  isNew = false,
  onSave,
  onCancel,
  onDelete,
}) {
  const initial = {
    name: contact.name, phone: contact.phone, description: contact.description || "",
    display_order: contact.display_order || 0, base_updated_at: contact.updated_at || null,
  };
  const [draft, setDraft, recoveryWarning] = useEmergencyDraft(isNew ? "new-contact-fields" : "contact", isNew ? initial : null, contact.id);
  const editing = draft !== null;
  const { name, phone, description, display_order: displayOrder } = draft || initial;
  const setField = (field, value) => setDraft(previous => ({ ...previous, [field]: value }));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const dirty =
    editing &&
    (name !== contact.name ||
      phone !== contact.phone ||
      description !== (contact.description || "") ||
      displayOrder !== (contact.display_order || 0));
  useUnsavedChanges(dirty && !saving);

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setError("");
    if (
      !name.trim() ||
      !phone.trim() ||
      !/^[+\d\s().-]+$/.test(phone.trim()) ||
      phone.replace(/\D/g, "").length < 3
    ) {
      setError("Enter a contact name and a valid phone number.");
      return;
    }
    if (!Number.isInteger(displayOrder) || displayOrder < 0 || displayOrder > 2147483647) {
      setError("Display order must be a whole number from 0 to 2147483647.");
      return;
    }
    setSaving(true);
    try {
      await onSave({
        ...contact,
        name: name.trim(),
        phone: phone.trim(),
        description: description.trim(),
        display_order: displayOrder,
        base_updated_at: draft.base_updated_at,
        isEditing: false,
      });
      setDraft(null);
    } catch (error) {
      setError(error.message);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    if (
      saving ||
      (dirty && !window.confirm("Discard unsaved contact changes?"))
    )
      return;
    setError("");
    setDraft(null);
    onCancel?.();
  }

  return (
    <Card.Root variant="outline" bg="white">
      <Card.Body p={4}>
        {editing ? (
          <form onSubmit={save}>
            <Stack gap={3}>
              <Field.Root required>
                <Field.Label>Contact name</Field.Label>
                <Input
                  value={name}
                  required
                  disabled={saving}
                  maxLength={200}
                  onChange={(event) => setField("name", event.target.value)}
                />
              </Field.Root>
              <Field.Root required>
                <Field.Label>Phone number</Field.Label>
                <Input
                  type="tel"
                  required
                  disabled={saving}
                  value={phone}
                  maxLength={100}
                  onChange={(event) => setField("phone", event.target.value)}
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Description / coverage</Field.Label>
                <Textarea
                  value={description}
                  disabled={saving}
                  maxLength={10000}
                  onChange={(event) => setField("description", event.target.value)}
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Display order</Field.Label>
                <Input
                  type="number"
                  min={0}
                  max={2147483647}
                  step={1}
                  required
                  value={displayOrder}
                  disabled={saving}
                  onChange={(event) =>
                    setField("display_order", Number(event.target.value))
                  }
                />
                <Field.HelperText>
                  Lower numbers appear first in the mobile directory.
                </Field.HelperText>
              </Field.Root>
              {error && (
                <Text role="alert" color="red.600">
                  {error}
                </Text>
              )}
              {recoveryWarning && <Text role="alert" color="red.600">{recoveryWarning}</Text>}
              <Text fontSize="sm">Unsaved contact edits are kept for this admin session. After a conflict, cancel to review the latest saved contact before editing again.</Text>
              <Flex gap={2}>
                <Button type="submit" colorPalette="brand" loading={saving}>
                  Save contact
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={saving}
                  onClick={cancel}
                >
                  Cancel
                </Button>
              </Flex>
            </Stack>
          </form>
        ) : (
          <Flex justify="space-between" align="center" gap={3} wrap="wrap">
            <Box>
              <Text fontWeight="bold">{contact.name}</Text>
              <Text color="gray.600">{contact.phone}</Text>
              {contact.description && <Text>{contact.description}</Text>}
              <Text fontSize="sm">
                Display order: {contact.display_order || 0}
              </Text>
            </Box>
            <Flex gap={2}>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setDraft(initial);
                  setError("");
                }}
              >
                Edit
              </Button>
              <Button
                size="sm"
                variant="outline"
                colorPalette="red"
                onClick={onDelete}
              >
                Remove
              </Button>
            </Flex>
          </Flex>
        )}
      </Card.Body>
    </Card.Root>
  );
}
