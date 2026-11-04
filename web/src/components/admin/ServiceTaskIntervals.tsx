"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import { Badge, Box, Button, Flex, Stack, Text } from "@chakra-ui/react";
import { loadCatalogue, loadMaintenanceIntervals, type Schedule, type Vehicle } from "@/api/admin";
import { taskIntervals } from "@/lib/maintenanceIntervals.mjs";
import { serviceInstruction } from "@/lib/adminJourney.mjs";

export function useMaintenanceIntervals() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([loadCatalogue(), loadMaintenanceIntervals()])
      .then(([catalogue, rows]) => {
        if (!active) return;
        setVehicles(catalogue.vehicles);
        setSchedules(rows);
      })
      .catch((cause: Error) => { if (active) setError(cause.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [attempt]);
  return { schedules, vehicles, loading, error, reload: () => setAttempt((value) => value + 1) };
}

export default function ServiceTaskIntervals({ itemId, schedules, vehicles, vehicleId, loading, error }: {
  itemId: string;
  schedules: Schedule[];
  vehicles: Vehicle[];
  vehicleId: string;
  loading: boolean;
  error: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const intervals = taskIntervals(schedules, itemId, vehicleId);
  return <Box bg="canvas" p={3} borderRadius="6px" mt={4}>
    <Text fontSize="sm" fontWeight="600" mb={2}>Maintenance intervals</Text>
    {loading ? <Text fontSize="sm">Loading vehicle intervals…</Text>
      : error ? <Text fontSize="sm">Intervals could not be loaded. Retry above.</Text>
      : <Stack gap={3}>
        {(expanded ? intervals : intervals.slice(0, 2)).map(({ schedule, entry, index }) => {
          const vehicle = vehicles.find((row) => row.id === schedule.vehicle_id);
          return <Box key={schedule.id}>
            <Flex gap={2} wrap="wrap" align="center">
              <Text fontSize="sm" fontWeight="600">
                {vehicle ? [vehicle.name, vehicle.year, vehicle.variant].filter(Boolean).join(" · ") : "Vehicle unavailable"}
              </Text>
              <Badge colorPalette={schedule.status === "published" ? "green" : "orange"}>
                {schedule.status === "published" ? "Available to drivers" : "Draft · needs review"}
              </Badge>
            </Flex>
            <Text fontSize="sm" mt={1}>{serviceInstruction(entry)}</Text>
            {entry.rule.conditions && entry.rule.type !== "informational" &&
              <Text fontSize="sm" color="muted">Applies when: {entry.rule.conditions}</Text>}
            {entry.rule.notes && entry.rule.type !== "informational" &&
              <Text fontSize="sm" color="muted">{entry.rule.notes}</Text>}
            <Button asChild size="sm" variant="plain" mt={1}>
              <NextLink href={`/admin/schedules?vehicle=${schedule.vehicle_id}&schedule=${schedule.id}&item=${itemId}#schedule-task-${index + 1}`}>
                {schedule.status === "published" ? "Review or update interval" : "Edit interval and check source"}
              </NextLink>
            </Button>
          </Box>;
        })}
        {intervals.length > 2 && <Button size="sm" variant="plain" alignSelf="start"
          aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show fewer vehicles" : `Show all ${intervals.length} vehicle intervals`}
        </Button>}
        {!intervals.length && <Text fontSize="sm" color="muted">
          Interval unset{vehicleId ? " for this vehicle" : ""} · needs source review. Check the vehicle’s manual before setting a distance, time or condition.
        </Text>}
        <Button asChild size="sm" variant="outline" alignSelf="start">
          <NextLink href={`/admin/schedules${vehicleId ? `?vehicle=${vehicleId}` : ""}`}>
            {vehicleId ? "Open vehicle schedule" : "Choose a vehicle to set intervals"}
          </NextLink>
        </Button>
      </Stack>}
  </Box>;
}
