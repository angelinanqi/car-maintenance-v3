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

export default function EmergencyContact({
  contact,
  isNew = false,
  onSave,
  onCancel,
  onDelete,
}) {
  const [editing, setEditing] = useState(isNew);
  const [name, setName] = useState(contact.name);
  const [phone, setPhone] = useState(contact.phone);
  const [description, setDescription] = useState(contact.description || "");
  const [displayOrder, setDisplayOrder] = useState(contact.display_order || 0);
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
    setSaving(true);
    try {
      await onSave({
        ...contact,
        name: name.trim(),
        phone: phone.trim(),
        description: description.trim(),
        display_order: displayOrder,
        isEditing: false,
      });
      setEditing(false);
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
    setName(contact.name);
    setPhone(contact.phone);
    setDescription(contact.description || "");
    setDisplayOrder(contact.display_order || 0);
    setError("");
    setEditing(false);
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
                  onChange={(event) => setName(event.target.value)}
                />
              </Field.Root>
              <Field.Root required>
                <Field.Label>Phone number</Field.Label>
                <Input
                  type="tel"
                  required
                  disabled={saving}
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Description / coverage</Field.Label>
                <Textarea
                  value={description}
                  disabled={saving}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Display order</Field.Label>
                <Input
                  type="number"
                  min={0}
                  step={1}
                  required
                  value={displayOrder}
                  disabled={saving}
                  onChange={(event) =>
                    setDisplayOrder(Number(event.target.value))
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
                  setName(contact.name);
                  setPhone(contact.phone);
                  setDescription(contact.description || "");
                  setDisplayOrder(contact.display_order || 0);
                  setEditing(true);
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
