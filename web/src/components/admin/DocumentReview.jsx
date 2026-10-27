"use client";

import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Flex,
  Grid,
  Heading,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { originalDocumentUrl } from "@/api/documents.mjs";
import VisualReview from './VisualReview';

export default function DocumentReview({ document, onLoaded, onUpdated }) {
  const [review, setReview] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    onLoaded(false);
    setReview(null);
    setError("");
    request(
      `/documents/${document.id}/review?revision=${document.source_revision}`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setReview(result);
          onLoaded(true);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(cause.message);
      });
    return () => {
      controller.abort();
      onLoaded(false);
    };
  }, [document.id, document.source_revision, attempt, onLoaded]);
  const blocks =
    review?.blocks.filter(
      (block) =>
        !query ||
        (block.text || "").toLowerCase().includes(query.toLowerCase()) ||
        block.kind === "table",
    ) || [];
  return (
    <Stack gap={4}>
      <VisualReview key={`${document.id}:${document.source_revision}`} document={document}
        onSaved={async () => { onLoaded(false); await onUpdated?.(); }} />
      <Text>
        Compare important instructions, numbers, units and table relationships
        with the original. Illustrations must be checked in the original. If
        anything is unclear, leave this document unfinished and return after
        checking it.
      </Text>
      {error && (
        <Box role="alert">
          <Text>{error}</Text>
          <Button
            mt={2}
            variant="outline"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Try opening again
          </Button>
        </Box>
      )}
      <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={5}>
        <Box minW={0}>
          <Flex
            justify="space-between"
            mb={3}
            align="center"
            gap={2}
            wrap="wrap"
          >
            <Heading size="md">Original document</Heading>
            <Button asChild variant="outline" size="sm">
              <a
                href={originalDocumentUrl(document.id)}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open in a new tab
              </a>
            </Button>
          </Flex>
          <Box
            asChild
            w="100%"
            h={{ base: "360px", xl: "620px" }}
            borderWidth="1px"
            borderRadius="8px"
            bg="white"
          >
            <iframe
              title={`Original: ${document.name}`}
              src={originalDocumentUrl(document.id)}
            />
          </Box>
        </Box>
        <Box minW={0}>
          <Heading size="md" mb={3}>
            What the system read
          </Heading>
          <Input
            aria-label="Find text in the prepared document"
            placeholder="Find a word or instruction"
            mb={3}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Box
            h={{ base: "400px", xl: "560px" }}
            overflow="auto"
            bg="canvas"
            p={4}
            borderRadius="8px"
            css={{
              "& table": {
                width: "100%",
                borderCollapse: "collapse",
                marginBlock: "12px",
              },
              "& td, & th": {
                border: "1px solid #aab4bf",
                padding: "8px",
                minWidth: "80px",
              },
            }}
          >
            {!review && !error && (
              <Text role="status">Opening the prepared document…</Text>
            )}
            {blocks.map((block, index) =>
              block.kind === "table" && block.html ? (
                <Box
                  key={index}
                  overflowX="auto"
                  dangerouslySetInnerHTML={{ __html: block.html }}
                />
              ) : (
                <Text
                  key={index}
                  whiteSpace="pre-wrap"
                  mb={3}
                  color={block.kind === "image" ? "muted" : "ink"}
                >
                  {block.text}
                </Text>
              ),
            )}
            {review && !blocks.length && (
              <Text>No matching text. Try a different word.</Text>
            )}
          </Box>
        </Box>
      </Grid>
    </Stack>
  );
}
