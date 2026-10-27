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
      {document.document_type === "owners_manual" &&
        document.mobile_visible && (
          <Text fontWeight="600">
            This owner’s manual is available in the mobile manual library for
            its covered vehicles
            {document.vehicle_independent ? " and as general guidance" : ""}.
          </Text>
        )}
      <Text>
        The document is published. Chatbot access also depends on whether each
        vehicle or topic is enabled below.
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
                  ? "Available in the chatbot"
                  : enabled
                    ? "Enabled. Refresh availability to check chatbot access."
                    : "Not available in the chatbot"}
              </Text>
            </Box>
            {kind === "category" && !row.published ? (
              <Button asChild variant="outline">
                <NextLink href="/admin/learn-cards/manage-cat">
                  Make learning topic available
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
