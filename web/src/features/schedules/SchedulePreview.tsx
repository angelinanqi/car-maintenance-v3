import { Box, Heading, Stack, Text } from "@chakra-ui/react";
import { serviceInstruction } from "@/lib/adminJourney.mjs";
import type {
  Schedule,
  ScheduleEntry,
  MaintenanceItem,
  SourceDocument,
} from "@/api/admin";

export default function SchedulePreview({
  schedule,
  entries,
  items,
  documents,
}: {
  schedule: Schedule | null;
  entries: ScheduleEntry[];
  items: MaintenanceItem[];
  documents: SourceDocument[];
}) {
  return (
    <Box bg="white" p={6} borderRadius="12px">
      <Heading size="lg" mb={2}>
        Review the instructions
      </Heading>
      <Text color="muted" mb={5}>
        A readable preview of this{" "}
        {schedule?.status === "published"
          ? "published schedule"
          : "draft"}
        . The mobile app also uses drivers’ own service history to
        calculate what is due.
      </Text>
      <Stack gap={5}>
        {entries.map((entry, index) => (
          <Box key={index} borderBottomWidth="1px" pb={4}>
            <Heading size="md">
              {items.find((item) => item.id === entry.itemId)
                ?.title || "Task not chosen"}
            </Heading>
            <Text mt={2}>{serviceInstruction(entry)}</Text>
            {entry.rule.conditions && (
              <Text mt={1}>
                Applies when: {entry.rule.conditions}
              </Text>
            )}
            {entry.rule.notes && (
              <Text mt={1}>{entry.rule.notes}</Text>
            )}
            <Text fontSize="sm" color="muted" mt={2}>
              Reference:{" "}
              {documents.find(
                (document) =>
                  document.id === entry.rule.sourceDocumentId,
              )?.name || "Not chosen"}
              {entry.rule.sourcePage
                ? `, page ${entry.rule.sourcePage}`
                : ""}
            </Text>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}
