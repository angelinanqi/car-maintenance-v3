import { Box, Stack, Text } from "@chakra-ui/react";
import type { MaintenanceItem, Schedule, ScheduleEntry } from "@/api/admin";
import { serviceInstruction } from "@/lib/adminJourney.mjs";

function changedFields(before: ScheduleEntry, after: ScheduleEntry) {
  const fields = [];
  if (before.action !== after.action) fields.push("action");
  const a = before.rule;
  const b = after.rule;
  if (a.type !== b.type || a.distanceKm !== b.distanceKm || a.months !== b.months ||
      a.distanceMilestones.join() !== b.distanceMilestones.join() ||
      a.monthMilestones.join() !== b.monthMilestones.join() || a.vehicleStartDate !== b.vehicleStartDate)
    fields.push("timing");
  if (a.conditions !== b.conditions) fields.push("conditions");
  if (a.notes !== b.notes) fields.push("notes");
  if (a.sourceDocumentId !== b.sourceDocumentId || a.sourceRevision !== b.sourceRevision ||
      a.sourcePage !== b.sourcePage || a.sourceTableId !== b.sourceTableId ||
      a.sourceSuggestionId !== b.sourceSuggestionId) fields.push("source reference");
  return fields;
}

export default function ScheduleChanges({ published, entries, items }: {
  published: Schedule; entries: ScheduleEntry[]; items: MaintenanceItem[];
}) {
  const added = entries.filter((entry) => !published.entries.some((old) => old.itemId === entry.itemId));
  const removed = published.entries.filter((entry) => !entries.some((next) => next.itemId === entry.itemId));
  const changed = entries.flatMap((entry) => {
    const before = published.entries.find((old) => old.itemId === entry.itemId);
    if (!before) return [];
    const fields = changedFields(before, entry);
    return fields.length ? [{ before, entry, fields }] : [];
  });
  const title = (entry: ScheduleEntry) => items.find((item) => item.id === entry.itemId)?.title || "Unselected task";
  return <Box as="details" borderWidth="1px" borderRadius="10px" p={4}>
    <Box as="summary" cursor="pointer" fontWeight="600">
      Changes From Published Version {published.revision}: {added.length} Added, {changed.length} Changed, {removed.length} Removed
    </Box>
    <Stack gap={3} mt={3} fontSize="sm">
      <Text color="muted">Compares the current editor with the published schedule. Save your draft before final approval.</Text>
      {added.map((entry, index) => <Text key={`added-${index}`}>Added: {title(entry)} — {serviceInstruction(entry)}</Text>)}
      {removed.map((entry, index) => <Text key={`removed-${index}`}>Removed: {title(entry)} — {serviceInstruction(entry)}</Text>)}
      {changed.map(({ before, entry, fields }, index) => <Box key={`changed-${index}`}>
        <Text fontWeight="600">{title(entry)}: {fields.join(", ")} changed</Text>
        {fields.includes("timing") && <>
          <Text>Published: {serviceInstruction(before)}</Text>
          <Text>Current: {serviceInstruction(entry)}</Text>
        </>}
      </Box>)}
      {!added.length && !removed.length && !changed.length && <Text>No task changes from the published schedule.</Text>}
    </Stack>
  </Box>;
}
