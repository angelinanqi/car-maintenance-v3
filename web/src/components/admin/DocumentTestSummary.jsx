"use client";

import NextLink from "next/link";
import { Box, Button, Text } from "@chakra-ui/react";
import { documentTestHref, testNeedsAttention, testSummaryText } from "@/lib/documentTestFollowUp.mjs";

export default function DocumentTestSummary({ documentId, documentName, summary, error, loading, filter }) {
  if (error || !summary) return <Text mt={2} fontSize="sm" color="muted">
    {loading && !error ? "Loading document tests…" : "Document test status unavailable. Retry loading to check follow-up work."}
  </Text>;
  const attention = testNeedsAttention(summary);
  const state = filter && filter !== "attention" ? filter : null;
  return <Box mt={2}>
    <Text fontSize="sm" color={attention ? "orange.800" : "muted"}>Tests: {testSummaryText(summary)}</Text>
    {attention && <Button asChild size="xs" variant="outline" mt={2}>
      <NextLink href={documentTestHref(documentId, summary, state)}>Review test results
        <Box as="span" srOnly> for {documentName}</Box>
      </NextLink>
    </Button>}
  </Box>;
}
