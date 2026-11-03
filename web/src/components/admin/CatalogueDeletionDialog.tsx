"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import { Box, Button, Dialog, Flex, Stack, Text } from "@chakra-ui/react";
import {
  catalogueDeletionPreview, deactivateCatalogueEntry, deleteCatalogueEntry,
  type CatalogueDeletionImpact, type CatalogueKind, type Manufacturer,
} from "@/api/admin";

export default function CatalogueDeletionDialog({ kind, entry, onClose, onComplete }: {
  kind: CatalogueKind;
  entry: Manufacturer;
  onClose: () => void;
  onComplete: (action: "deleted" | "deactivated") => void;
}) {
  const [impact, setImpact] = useState<CatalogueDeletionImpact | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<"delete" | "deactivate" | null>(null);
  const busy = pending !== null;
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setImpact(null);
    catalogueDeletionPreview(kind, entry.id, controller.signal)
      .then((value) => { if (!controller.signal.aborted) setImpact(value); })
      .catch((cause: Error) => { if (!controller.signal.aborted) setError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [kind, entry.id, attempt]);

  async function act(permanent: boolean) {
    if (busy || !impact || (permanent && !impact.deletable)) return;
    setPending(permanent ? "delete" : "deactivate");
    setError("");
    try {
      if (permanent) await deleteCatalogueEntry(kind, entry.id, impact.fingerprint);
      else await deactivateCatalogueEntry(kind, entry.id);
      onComplete(permanent ? "deleted" : "deactivated");
    } catch (cause) {
      const failure = cause as Error & { status?: number };
      if (failure.status === 404) {
        onComplete("deleted");
        return;
      }
      setError(failure.message);
      if (failure.status === 409) {
        setImpact(null);
        setAttempt((value) => value + 1);
      }
    } finally { setPending(null); }
  }

  return (
    <Dialog.Root open size="lg" closeOnInteractOutside={false} closeOnEscape={!busy}
      onOpenChange={({ open }) => { if (!open && !busy) onClose(); }}>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content maxH="85vh" overflowY="auto">
          <Dialog.Header><Dialog.Title>Delete {impact?.entry.name || entry.name}?</Dialog.Title></Dialog.Header>
          <Dialog.Body>
            <Stack gap={4}>
              {error && <Text role="alert" color="red.600">{error}</Text>}
              {loading && <Text role="status">Checking linked records…</Text>}
              {!loading && !impact && <Button variant="outline" onClick={() => { setError(""); setAttempt((value) => value + 1); }}>Retry usage check</Button>}
              {impact && (impact.deletable ? (
                <Box bg="orange.50" p={4} borderRadius="md">
                  <Text fontWeight="600">No linked records were found.</Text>
                  <Text mt={2}>Permanently deleting this unused entry cannot be undone. You can also deactivate it to keep it in the catalogue.</Text>
                </Box>
              ) : (
                <>
                  <Text>This entry is in use and cannot be deleted. Deactivate it to hide it from new vehicle selections while preserving its linked records.</Text>
                  <Stack as="ul" m={0} pl={5} gap={3}>
                    {impact.blockers.map((blocker) => (
                      <Box as="li" key={blocker.key}>
                        <Text fontWeight="600">{blocker.count} · {blocker.label}</Text>
                        {blocker.href && <NextLink href={blocker.href} onClick={(event) => { if (busy) event.preventDefault(); else onClose(); }} style={{ textDecoration: "underline" }}>Review linked records</NextLink>}
                        {blocker.items.length > 0 && <Stack gap={1} mt={1}>
                          {blocker.items.map((item) => <NextLink key={item.href} href={item.href}
                            onClick={(event) => { if (busy) event.preventDefault(); else onClose(); }}
                            style={{ textDecoration: "underline" }}>{item.name}</NextLink>)}
                        </Stack>}
                      </Box>
                    ))}
                  </Stack>
                  {(impact.references.user_vehicles > 0 || impact.references.chats > 0) &&
                    <Text fontSize="sm" color="muted">Private user records are included in these counts. Their contents stay private.</Text>}
                  {!impact.entry.active && <Text>This entry is already inactive. Its references must remain intact.</Text>}
                </>
              ))}
            </Stack>
          </Dialog.Body>
          <Dialog.Footer>
            <Flex gap={3} wrap="wrap" justify="end">
              <Button variant="outline" disabled={busy} onClick={onClose}>Cancel</Button>
              {impact?.entry.active && <Button variant="outline" disabled={loading || busy} loading={pending === "deactivate"} onClick={() => act(false)}>Deactivate</Button>}
              <Button colorPalette="red" disabled={loading || busy || !impact?.deletable} loading={pending === "delete"}
                onClick={() => act(true)}>Permanently delete</Button>
            </Flex>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
