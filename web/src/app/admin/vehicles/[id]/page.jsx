"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import NextLink from "next/link";
import {
  Badge,
  Box,
  Button,
  Flex,
  Grid,
  Heading,
  Stack,
  Text,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import { VehicleEditor } from "@/components/admin/CatalogueEditors";
import CatalogueDeletionDialog from "@/components/admin/CatalogueDeletionDialog";
import { useContent } from "@/components/ContentProvider";
import { loadCatalogue, loadSchedules } from "@/api/admin";
import { documentJourney, scheduleStatus } from "@/lib/adminJourney.mjs";
import { vehicleAvailability } from "@/lib/catalogue.mjs";

export default function VehicleWorkspace() {
  const { id } = useParams();
  const router = useRouter();
  const { documents, knowledge, configuration, refresh } = useContent();
  const [catalogue, setCatalogue] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([loadCatalogue(), loadSchedules(id)])
      .then(([data, rows]) => {
        if (active) {
          setCatalogue(data);
          setSchedules(rows);
        }
      })
      .catch((cause) => {
        if (active) setError(cause.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, attempt]);
  const vehicle = catalogue?.vehicles.find((row) => row.id === id);
  const linked = documents.filter((document) =>
    knowledge?.document_vehicles.some(
      (link) => link.vehicle_id === id && link.document_id === document.id,
    ),
  );
  const current = linked.filter((document) => !document.superseded_by_id);
  const drafts = schedules.filter((schedule) => schedule.status === "draft");
  const published = schedules.find(
    (schedule) => schedule.status === "published",
  );
  const chat = configuration?.knowledge_scopes?.find(
    (scope) => scope.scope_type === "vehicle" && scope.scope_id === id,
  );
  return (
    <AdminLayout
      title={vehicle?.name || "Vehicle Overview"}
      description={
        vehicle
          ? [
              vehicle.year,
              vehicle.engine,
              vehicle.variant,
              vehicle.powertrain === "diesel" ? "Diesel" : "Petrol",
            ]
              .filter(Boolean)
              .join(" · ")
          : "Manuals, service guidance and availability for this vehicle."
      }
    >
      <Stack gap={6}>
        <Flex justify="space-between" gap={3} wrap="wrap">
          <Button asChild variant="outline">
            <NextLink href="/admin/vehicles">Back to vehicles</NextLink>
          </Button>
          {vehicle && (
            <Flex gap={3} wrap="wrap">
            <Button variant="outline" onClick={() => setEditing(true)}>
              Edit vehicle details
            </Button>
            <Button variant="outline" colorPalette="red" onClick={() => setDeleting(true)}>Delete vehicle</Button>
            </Flex>
          )}
        </Flex>
        {loading && (
          <Text role="status">Opening this vehicle’s information…</Text>
        )}
        {error && (
          <Box role="alert">
            <Text>{error}</Text>
            <Button
              mt={3}
              variant="outline"
              onClick={() => setAttempt((value) => value + 1)}
            >
              Try again
            </Button>
          </Box>
        )}
        {!loading && catalogue && !vehicle && (
          <Text>This vehicle could not be found.</Text>
        )}
        {vehicle && (
          <>
            <Box bg="brand.100" p={{ base: 5, md: 7 }} borderRadius="12px">
              <Heading as="h2" size="lg" mb={3}>
                What Drivers Can Use
              </Heading>
              <Stack gap={2}>
                <Text>
                  Vehicle selection:{" "}
                  {vehicleAvailability(
                    vehicle,
                    catalogue.models,
                    catalogue.manufacturers,
                  )}
                </Text>
                <Text>
                  Owner’s manual:{" "}
                  {vehicle.manual_available ? "Available" : "Not available yet"}
                </Text>
                <Text>
                  Service schedule:{" "}
                  {published ? "Available" : "Not available yet"}
                </Text>
                <Text>
                  Chatbot: {chat?.available ? "Available" : "Not available yet"}
                </Text>
              </Stack>
              {!vehicle.published && (
                <Text mt={3}>
                  To offer this vehicle in the chatbot, enable it in vehicle
                  details. It also needs published reference material or other
                  supported content.
                </Text>
              )}
              <Button asChild variant="outline" mt={4}>
                <NextLink href="/admin/chatbot">Try the chatbot</NextLink>
              </Button>
            </Box>
            <Grid
              templateColumns={{ base: "1fr", xl: "1.3fr 1fr" }}
              gap={6}
              alignItems="start"
            >
              <Box id="vehicle-documents" scrollMarginTop="100px" bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                <Flex
                  justify="space-between"
                  gap={3}
                  align="center"
                  wrap="wrap"
                  mb={4}
                >
                  <Heading as="h2" size="lg">
                    Manuals and References
                  </Heading>
                  <Button asChild size="sm">
                    <NextLink href={`/admin/kb?add=1&vehicle=${id}`}>
                      Add document
                    </NextLink>
                  </Button>
                </Flex>
                {!knowledge ? (
                  <Text>
                    Document coverage is unavailable. Retry loading above.
                  </Text>
                ) : !current.length ? (
                  <Text color="muted">
                    Add the owner’s manual or service booklet for this exact
                    model year and version. You’ll confirm its coverage before
                    it is used.
                  </Text>
                ) : (
                  <Stack gap={4}>
                    {current.map((document) => {
                      const journey = documentJourney(document, knowledge);
                      return (
                        <Box key={document.id} borderBottomWidth="1px" pb={4}>
                          <Badge colorPalette={journey.color} mb={2}>
                            {journey.label}
                          </Badge>
                          <Text fontWeight="600">{document.name}</Text>
                          <Button asChild variant="outline" size="sm" mt={3}>
                            <NextLink href={`/admin/kb/${document.id}`}>
                              {journey.next}
                            </NextLink>
                          </Button>
                        </Box>
                      );
                    })}
                  </Stack>
                )}
                {linked.some((document) => document.superseded_by_id) && (
                  <Box as="details" mt={4}>
                    <Box as="summary">Previous Document Versions</Box>
                    <Stack mt={3}>
                      {linked
                        .filter((document) => document.superseded_by_id)
                        .map((document) => (
                          <NextLink
                            key={document.id}
                            href={`/admin/kb/${document.id}`}
                            style={{ textDecoration: "underline" }}
                          >
                            {document.name}
                          </NextLink>
                        ))}
                    </Stack>
                  </Box>
                )}
              </Box>
              <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                <Heading as="h2" size="lg" mb={3}>
                  Service Schedule
                </Heading>
                <Text color="muted" mb={4}>
                  Check service tasks and intervals against this vehicle’s
                  manufacturer reference.
                </Text>
                {published && (
                  <Text mb={3}>
                    Version {published.revision} is available to drivers.
                  </Text>
                )}
                {drafts.length > 0 && (
                  <Text mb={3} fontWeight="600">
                    {drafts.length} unfinished{" "}
                    {drafts.length === 1 ? "draft" : "drafts"} to continue.
                  </Text>
                )}
                <Button asChild>
                  <NextLink href={`/admin/schedules?vehicle=${id}`}>
                    {drafts.length
                      ? "Continue service schedule"
                      : published
                        ? "Review or update schedule"
                        : "Start service schedule"}
                  </NextLink>
                </Button>
                {schedules.length > 0 && (
                  <Box as="details" mt={4}>
                    <Box as="summary">Saved Versions</Box>
                    <Stack mt={3}>
                      {schedules.map((schedule) => (
                        <Text key={schedule.id} fontSize="sm">
                          Version {schedule.revision}:{" "}
                          {scheduleStatus(schedule.status)}
                        </Text>
                      ))}
                    </Stack>
                  </Box>
                )}
              </Box>
            </Grid>
          </>
        )}
      </Stack>
      {deleting && vehicle && <CatalogueDeletionDialog kind="vehicles" entry={vehicle}
        onClose={() => setDeleting(false)} onComplete={(action) => {
          setDeleting(false);
          if (action === "deleted") router.push("/admin/vehicles");
          else setCatalogue((previous) => ({ ...previous, vehicles: previous.vehicles.map((row) => row.id === id ? { ...row, active: false } : row) }));
          void refresh({ documentsOnly: true });
        }} />}
      {editing && vehicle && (
        <VehicleEditor
          data={catalogue}
          row={vehicle}
          onClose={() => setEditing(false)}
          onSaved={async () => {
            setEditing(false);
            setAttempt((value) => value + 1);
            await refresh({ documentsOnly: true });
          }}
        />
      )}
    </AdminLayout>
  );
}
