"use client";

import {
  useEffect,
  useId,
  useRef,
  type FormEvent,
  type ReactNode,
} from "react";
import { Fieldset,  Button, Dialog, Stack, Text } from "@chakra-ui/react";
import useUnsavedChanges from "./useUnsavedChanges";

export default function RecordDialog({
  title,
  description,
  busy,
  dirty,
  error,
  onClose,
  onSubmit,
  children,
  saveLabel = "Save changes",
}: {
  title: string;
  description: string;
  busy: boolean;
  dirty: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
  saveLabel?: string;
}) {
  const formId = useId();
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (error)
      form.current
        ?.querySelector<HTMLElement>('[aria-invalid="true"]')
        ?.focus();
  }, [error]);
  useUnsavedChanges(dirty);
  function close() {
    if (busy) return;
    if (!dirty || window.confirm("Discard the unsaved changes in this form?"))
      onClose();
  }
  return (
    <Dialog.Root
      open
      size="lg"
      scrollBehavior="inside"
      closeOnInteractOutside={false}
      closeOnEscape={!busy}
      onOpenChange={({ open }) => {
        if (!open) close();
      }}
      initialFocusEl={() =>
        form.current?.querySelector<HTMLElement>(
          "input:not(:disabled), textarea:not(:disabled), select:not(:disabled)",
        ) ?? null
      }
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>
            <Dialog.Title>{title}</Dialog.Title>
          </Dialog.Header>
          {error && <Text role="alert" mx={6} mb={3}>{error}</Text>}
          <Dialog.Body>
            <Dialog.Description mb={5} color="muted">
              {description}
            </Dialog.Description>
            <form id={formId} ref={form} onSubmit={onSubmit}>
              <Fieldset.Root disabled={busy}>
                <Stack gap={5}>{children}</Stack>
              </Fieldset.Root>
            </form>
          </Dialog.Body>
          <Dialog.Footer>
            <Button variant="outline" onClick={close} disabled={busy}>
              Cancel
            </Button>
            <Button
              type="submit"
              form={formId}
              loading={busy}
              loadingText="Saving"
            >
              {saveLabel}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
