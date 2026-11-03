"use client";
import Pagination, { usePagination } from "@/components/admin/Pagination";

import { useState } from "react";
import NextLink from "next/link";
import {
  Box,
  Button,
  Flex,
  Heading,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useContent } from "@/components/ContentProvider";
import { request } from "@/api/client.mjs";

export default function KnowledgeScopes() {
  const { knowledge, refresh } = useContent();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pagination = usePagination(knowledge?.categories || []);
  async function save(action, message) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh({ documentsOnly: true });
      setNotice(message);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }
  if (!knowledge)
    return (
      <Text>
        Vehicle and topic settings are unavailable. Retry loading the workspace
        above.
      </Text>
    );
  return (
    <Stack gap={6}>
      {error && <Text role="alert">{error}</Text>}
      {notice && <Text role="status">{notice}</Text>}
      <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading size="lg" mb={3}>
          Documents Belong with Their Vehicles and Topics
        </Heading>
        <Text color="muted">
          To change where a reference is used, open it in the reference library.
          Its coverage, document check and availability are together in one
          place.
        </Text>
        <Button asChild variant="outline" mt={4}>
          <NextLink href="/admin/kb">Open reference library</NextLink>
        </Button>
      </Box>
      <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading size="lg" mb={3}>
          Learning Topics in the Chatbot
        </Heading>
        <Text color="muted" mb={5}>
          Enable a topic when you want drivers to ask questions about its
          published guides and reference documents.
        </Text>
        <Stack gap={4}>
          {pagination.items.map((category) => (
            <Flex
              key={category.id}
              justify="space-between"
              align="center"
              gap={3}
              wrap="wrap"
            >
              <Box>
                <Text fontWeight="600">{category.name}</Text>
                <Text fontSize="sm" color="muted">
                  {category.archived
                    ? "Archived. Restore this learning topic before enabling it."
                    : !category.published
                    ? "Make the learning topic available first."
                    : category.knowledge_published
                      ? "Enabled in the chatbot; needs published content."
                      : "Not enabled in the chatbot."}
                </Text>
              </Box>
              {!category.published ? (
                <Button asChild variant="outline" size="sm">
                  <NextLink href="/admin/learn-cards/manage-cat">
                    Manage learning topic
                  </NextLink>
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    save(
                      () =>
                        request(
                          `/knowledge/categories/${category.id}/publication`,
                          {
                            method: "PATCH",
                            body: { published: !category.knowledge_published },
                          },
                        ),
                      "Chatbot topic settings saved.",
                    )
                  }
                >
                  {category.knowledge_published
                    ? "Disable in chatbot"
                    : "Enable in chatbot"}
                </Button>
              )}
            </Flex>
          ))}
        </Stack>
        <Pagination {...pagination} label="Chatbot Topics" />
        {!knowledge.categories.length && (
          <Text>Add a learning topic in Learning topics first.</Text>
        )}
      </Box>
    </Stack>
  );
}
