"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Stack,
  Text,
} from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { scheduleStatus } from "@/lib/adminJourney.mjs";

export default function DocumentImpact({ document }) {
  const sourceId = document.replacement_for_id || document.id;
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setUsage(null);
    setError("");
    request(`/documents/${sourceId}/usage`, { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setUsage(result);
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(cause.message);
      });
    return () => controller.abort();
  }, [sourceId, document.published, attempt]);
  const current =
    usage?.schedules.filter((schedule) => schedule.status !== "superseded") ||
    [];
  const previous =
    usage?.schedules.filter((schedule) => schedule.status === "superseded") ||
    [];
  function scheduleCard(schedule) {
    const query = new URLSearchParams({
      vehicle: schedule.vehicle_id,
      schedule: schedule.id,
      source: document.id,
    });
    return (
      <Box key={schedule.id} borderWidth="1px" borderRadius="8px" p={4}>
        <Badge mb={2}>{scheduleStatus(schedule.status)}</Badge>
        <Heading size="md">
          {schedule.vehicle_name} · Version {schedule.revision}
        </Heading>
        <Text mt={2}>
          {schedule.tasks.length}{" "}
          {schedule.tasks.length === 1 ? "task references" : "tasks reference"}{" "}
          {document.replacement_for_id
            ? "the earlier document"
            : "this document"}
          :
        </Text>
        <Stack as="ul" pl={5} gap={1} mt={2}>
          {schedule.tasks.map((task, index) => (
            <Text as="li" key={`${task.item_id}:${index}`} fontSize="sm">
              {task.title}
              {task.page ? ` · page ${task.page}` : ""}
              {task.source_document_name
                ? ` · ${task.source_document_name}`
                : ""}
            </Text>
          ))}
        </Stack>
        <Button asChild variant="outline" size="sm" mt={3}>
          <NextLink href={`/admin/schedules?${query}`}>
            Check this schedule
          </NextLink>
        </Button>
      </Box>
    );
  }
  return (
    <Box
      id="document-impact"
      bg="white"
      p={{ base: 5, md: 7 }}
      borderRadius="12px"
      scrollMarginTop="20px"
    >
      <Heading size="lg" mb={3}>
        {document.replacement_for_id
          ? "What Needs Checking with This Replacement?"
          : "Where This Document Is Referenced"}
      </Heading>
      <Text color="muted" mb={4}>
        These are saved references, not a comparison of the manuals. Replacing a
        file does not change the service instructions below.
      </Text>
      {error && (
        <Box role="alert">
          <Text>{error}</Text>
          <Button
            variant="outline"
            mt={2}
            onClick={() => setAttempt((value) => value + 1)}
          >
            Retry reference check
          </Button>
        </Box>
      )}
      {!usage && !error && (
        <Text role="status">Finding schedules that reference this manual…</Text>
      )}
      <Stack gap={3}>{current.map(scheduleCard)}</Stack>
      {usage && !current.length && (
        <Text>
          No current schedules or drafts reference{" "}
          {document.replacement_for_id
            ? "the earlier document"
            : "this document"}
          .
        </Text>
      )}
      {previous.length > 0 && (
        <Box as="details" mt={4}>
          <Box as="summary">
            References in Previous Schedules ({previous.length})
          </Box>
          <Stack gap={3} mt={3}>
            {previous.map(scheduleCard)}
          </Stack>
        </Box>
      )}
      {usage?.related_guides.length > 0 && (
        <Box mt={5}>
          <Heading size="md" mb={2}>
            Learning Guides Sharing These Service Tasks
          </Heading>
          <Text fontSize="sm" color="muted" mb={3}>
            These guides link to the same service tasks. This does not confirm
            that they cite this manual or need changing; check their advice if
            relevant.
          </Text>
          <Stack gap={3}>
            {usage.related_guides.map((guide) => (
              <Flex
                key={guide.id}
                justify="space-between"
                gap={3}
                wrap="wrap"
                align="center"
              >
                <Text>{guide.title}</Text>
                <Button asChild size="sm" variant="outline">
                  <NextLink href={`/admin/learn-cards/create?edit=${guide.id}`}>
                    Review guide
                  </NextLink>
                </Button>
              </Flex>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
