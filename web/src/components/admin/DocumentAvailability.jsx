"use client";

import { useState } from "react";
import NextLink from "next/link";
import { Box, Button, Flex, Stack, Text } from "@chakra-ui/react";
import { useContent } from "@/components/ContentProvider";
import { request } from "@/api/client.mjs";
import { documentCoverage } from "@/lib/adminJourney.mjs";

export default function DocumentAvailability({ document }) {
  const { knowledge, configuration, refresh } = useContent();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const coverage = documentCoverage(document.id, knowledge);
  const manualAvailable = document.document_type === "owners_manual" &&
    document.mobile_visible && document.published && document.status === "processed" &&
    document.indexed_revision === document.source_revision && document.chunk_count > 0;
  const destinations = [
    ...knowledge.vehicles
      .filter((row) => coverage.vehicle_ids.includes(row.id))
      .map((row) => ({ row, kind: "vehicle", enabled: row.published })),
    ...knowledge.categories
      .filter((row) => coverage.category_ids.includes(row.id))
      .map((row) => ({
        row,
        kind: "category",
        enabled: row.knowledge_published && row.published,
      })),
  ];
  async function enable({ row, kind }) {
    if (busy) return;
    setBusy(row.id);
    setError("");
    try {
      if (kind === "vehicle") {
        const body = Object.fromEntries(
          [
            "code",
            "name",
            "year",
            "engine",
            "variant",
            "model_id",
            "powertrain",
            "active",
          ]
            .filter((key) => row[key] !== undefined)
            .map((key) => [key, row[key]]),
        );
        await request(`/knowledge/vehicles/${row.id}`, {
          method: "PATCH",
          body: { ...body, published: true },
        });
      } else {
        await request(`/knowledge/categories/${row.id}/publication`, {
          method: "PATCH",
          body: { published: true },
        });
      }
      await refresh({ documentsOnly: true });
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <Stack gap={3}>
      <Text fontWeight="600">Document: Published</Text>
      <Text>
        Mobile manual library: {manualAvailable
          ? `Available for covered vehicles${document.vehicle_independent ? " and as general guidance" : ""}.`
          : document.document_type === "owners_manual"
            ? "Not currently available. The manual must be visible and fully prepared."
            : "Not listed. Only owner’s manuals appear in this library."}
      </Text>
      <Text fontWeight="600">Chatbot access</Text>
      <Text>Publication and chatbot access are separate. Check the vehicle and topic settings below.</Text>
      <Text fontSize="sm" color="muted">
        General chat uses topic documents only when they are marked as vehicle-independent guidance.
      </Text>
      {error && <Text role="alert">{error}</Text>}
      {destinations.map((destination) => {
        const { row, kind, enabled } = destination;
        const actual = configuration?.knowledge_scopes?.find(
          (scope) => scope.scope_id === row.id && scope.scope_type === kind,
        );
        return (
          <Flex
            key={`${kind}:${row.id}`}
            gap={3}
            justify="space-between"
            align="center"
            wrap="wrap"
            bg="canvas"
            p={4}
            borderRadius="8px"
          >
            <Box>
              <Text fontWeight="600">{row.name}</Text>
              <Text fontSize="sm" color="muted">
                {actual?.available
                  ? "Scope enabled with published content"
                  : enabled
                    ? "Enabled. Refresh availability to check chatbot access."
                    : "Scope not enabled in the chatbot"}
              </Text>
            </Box>
            {kind === "category" && !row.published ? (
              <Button asChild variant="outline">
                <NextLink href="/admin/learn-cards/manage-cat">
                  Manage topic publication
                </NextLink>
              </Button>
            ) : !enabled ? (
              <Button
                variant="outline"
                loading={busy === row.id}
                disabled={Boolean(busy)}
                onClick={() => enable(destination)}
              >
                Enable {kind === "vehicle" ? "vehicle" : "topic"} in chatbot
              </Button>
            ) : null}
          </Flex>
        );
      })}
      <Text fontSize="sm" color="muted">
        Enabling a vehicle or topic allows the chatbot to use its other
        published information too.
      </Text>
      <Flex gap={3} wrap="wrap">
        <Button asChild>
          <NextLink href="/admin/chatbot">Try the chatbot</NextLink>
        </Button>
        <Button
          variant="outline"
          onClick={() => refresh({ documentsOnly: true })}
        >
          Refresh availability
        </Button>
      </Flex>
    </Stack>
  );
}
