"use client";

import { useState } from "react";
import { Dialog, Button, Text } from "@chakra-ui/react";

export default function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  itemName,
}) {
  const [busy, setBusy] = useState(false);
  async function confirm() {
    if (busy) return;
    setBusy(true);
    try { await onConfirm(); } finally { setBusy(false); }
  }
  return (
    <Dialog.Root open={isOpen} onOpenChange={(e) => !e.open && !busy && onClose()}>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>
            <Dialog.Title>Confirm Deletion</Dialog.Title>
          </Dialog.Header>

          <Dialog.Body>
            <Text fontSize="sm" color="gray.600">
              Are you sure you want to delete <strong>{itemName}</strong>?
              This removes the saved record and its associated stored files where applicable.
            </Text>
          </Dialog.Body>

          <Dialog.Footer>
            <Button variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button colorPalette="red" onClick={confirm} loading={busy}>
              Delete
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
