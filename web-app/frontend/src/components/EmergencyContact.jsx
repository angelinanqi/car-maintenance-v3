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
} from "@chakra-ui/react";

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
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function save(event) {
    event.preventDefault();
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
      isEditing: false,
    });
    setEditing(false);
    } catch (error) { setError(error.message); }
    finally { setSaving(false); }
  }

  function cancel() {
    setName(contact.name);
    setPhone(contact.phone);
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
                  onChange={(event) => setName(event.target.value)}
                />
              </Field.Root>
              <Field.Root required>
                <Field.Label>Phone number</Field.Label>
                <Input
                  type="tel"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                />
              </Field.Root>
              {error && (
                <Text role="alert" color="red.600">
                  {error}
                </Text>
              )}
              <Flex gap={2}>
                <Button type="submit" colorPalette="blue" loading={saving}>
                  Save contact
                </Button>
                <Button type="button" variant="outline" onClick={cancel}>
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
            </Box>
            <Flex gap={2}>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setName(contact.name);
                  setPhone(contact.phone);
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
