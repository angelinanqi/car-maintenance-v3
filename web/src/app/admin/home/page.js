"use client";
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
import { useContent } from "@/components/ContentProvider";
import {
  documentJourney,
  coverageNames,
  questionHref,
} from "@/lib/adminJourney.mjs";

export default function Home() {
  const {
    documents,
    cards,
    knowledge,
    scheduleDrafts,
    reviewQuestions,
    loading,
    error,
  } = useContent();
  const tasks = documents
    .map((document) => ({
      document,
      journey: documentJourney(document, knowledge),
    }))
    .filter(
      ({ journey }) =>
        !["available", "replaced", "preparing"].includes(journey.stage),
    );
  const preparing = documents.filter((document) =>
    ["processing", "awaiting_index"].includes(document.status),
  );
  const drafts = cards.filter((card) => card.status === "draft");
  return (
    <AdminLayout
      title="Welcome back"
      description="Pick up where you left off, or start an update. Saved work stays here between visits."
    >
      <Grid
        templateColumns={{
          base: "1fr",
          xl: "minmax(0, 1.6fr) minmax(260px, 1fr)",
        }}
        gap={6}
        alignItems="start"
      >
        <Stack gap={6}>
          <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
            <Heading as="h2" size="xl" mb={2}>
              Needs your attention
            </Heading>
            <Text color="muted" mb={5}>
              Documents, service schedules and learning drafts you can continue
              now.
            </Text>
            {loading ? (
              <Text role="status">Finding your unfinished work…</Text>
            ) : !knowledge ? (
              <Text>
                We couldn’t load document coverage. Retry loading the workspace
                above.
              </Text>
            ) : (
              <Stack gap={4}>
                {!tasks.length &&
                  !drafts.length &&
                  !scheduleDrafts.length &&
                  !reviewQuestions.length && (
                    <Text>
                      {error
                        ? "Some work could not be loaded. Retry loading above to check for outstanding tasks."
                        : "No unfinished work needs attention. You can start an update below."}
                    </Text>
                  )}
                {reviewQuestions.map((question) => (
                  <Flex
                    key={question.id}
                    justify="space-between"
                    align="center"
                    gap={3}
                    wrap="wrap"
                    borderBottomWidth="1px"
                    pb={4}
                  >
                    <Box flex="1">
                      <Badge colorPalette="orange" mb={2}>
                        Needs clarification
                      </Badge>
                      <Text fontWeight="600">{question.title}</Text>
                      <Text fontSize="sm" color="muted">
                        {[question.vehicle_name, question.document_name]
                          .filter(Boolean)
                          .join(" · ")}
                      </Text>
                      <Text fontSize="sm" color="muted" mt={1} lineClamp={3}>
                        {question.question}
                      </Text>
                      <Text fontSize="sm" color="muted">
                        {question.source_page
                          ? `Manual page ${question.source_page} · `
                          : ""}
                        Saved{" "}
                        {new Date(question.updated_at).toLocaleDateString(
                          "en-GB",
                        )}
                      </Text>
                    </Box>
                    <Button asChild size="sm" variant="outline">
                      <NextLink href={questionHref(question)}>
                        Continue checking
                      </NextLink>
                    </Button>
                  </Flex>
                ))}
                {scheduleDrafts.map((schedule) => (
                  <Flex
                    key={schedule.id}
                    justify="space-between"
                    align="center"
                    gap={3}
                    wrap="wrap"
                  >
                    <Box>
                      <Badge mb={2}>Service schedule draft</Badge>
                      <Text fontWeight="600">
                        {knowledge.vehicles.find(
                          (vehicle) => vehicle.id === schedule.vehicle_id,
                        )?.name || "Vehicle service schedule"}
                      </Text>
                      <Text fontSize="sm" color="muted">
                        Version {schedule.revision} · Not available to drivers
                      </Text>
                      {schedule.updated_at && (
                        <Text fontSize="sm" color="muted">
                          Last saved{" "}
                          {new Date(schedule.updated_at).toLocaleDateString(
                            "en-GB",
                          )}
                        </Text>
                      )}
                      {schedule.admin_note && (
                        <Text
                          fontSize="sm"
                          mt={1}
                          whiteSpace="pre-wrap"
                          lineClamp={3}
                        >
                          Left to do: {schedule.admin_note}
                        </Text>
                      )}
                    </Box>
                    <Button asChild variant="outline" size="sm">
                      <NextLink
                        href={`/admin/schedules?vehicle=${schedule.vehicle_id}&schedule=${schedule.id}`}
                      >
                        Continue schedule
                      </NextLink>
                    </Button>
                  </Flex>
                ))}
                {tasks.map(({ document, journey }) => (
                  <Flex
                    key={document.id}
                    justify="space-between"
                    align="center"
                    gap={4}
                    wrap="wrap"
                    borderBottomWidth="1px"
                    borderColor="gray.100"
                    pb={4}
                  >
                    <Box flex="1">
                      <Badge colorPalette={journey.color} mb={2}>
                        {journey.label}
                      </Badge>
                      <Heading as="h3" size="md">
                        {document.name}
                      </Heading>
                      <Text mt={1} color="muted" fontSize="sm">
                        {coverageNames(document.id, knowledge).join("; ") ||
                          "Choose the vehicles or topics this document covers."}
                      </Text>
                      {document.replacement_for_id && (
                        <Text fontSize="sm">
                          Unfinished document replacement
                        </Text>
                      )}
                    </Box>
                    <Button asChild size="sm">
                      <NextLink href={`/admin/kb/${document.id}`}>
                        {journey.next}
                        <Box as="span" srOnly>
                          {" "}
                          for {document.name}
                        </Box>
                      </NextLink>
                    </Button>
                  </Flex>
                ))}
                {drafts.map((card) => (
                  <Flex
                    key={card.id}
                    justify="space-between"
                    align="center"
                    gap={3}
                    wrap="wrap"
                  >
                    <Box>
                      <Badge mb={2}>Learning draft</Badge>
                      <Text fontWeight="600">{card.title}</Text>
                    </Box>
                    <Button asChild variant="outline" size="sm">
                      <NextLink
                        href={`/admin/learn-cards/create?edit=${card.id}`}
                      >
                        Continue guide
                        <Box as="span" srOnly>
                          : {card.title}
                        </Box>
                      </NextLink>
                    </Button>
                  </Flex>
                ))}
              </Stack>
            )}
          </Box>
          {preparing.length > 0 && (
            <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
              <Heading as="h2" size="lg" mb={2}>
                Being prepared
              </Heading>
              <Text mb={4} color="muted">
                You can work on something else. These will move to “Needs your
                attention” when ready to check.
              </Text>
              <Stack gap={3}>
                {preparing.map((document) => (
                  <Flex
                    key={document.id}
                    justify="space-between"
                    align="center"
                    gap={3}
                  >
                    <Text>{document.name}</Text>
                    <Button asChild size="sm" variant="outline">
                      <NextLink href={`/admin/kb/${document.id}`}>
                        View progress
                      </NextLink>
                    </Button>
                  </Flex>
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
        <Stack gap={4}>
          <Box bg="brand.100" p={{ base: 5, md: 7 }} borderRadius="12px">
            <Heading as="h2" size="lg" mb={4}>
              What would you like to do?
            </Heading>
            <Stack gap={3}>
              <Button asChild justifyContent="start">
                <NextLink href="/admin/vehicles">
                  Update a vehicle or its service schedule
                </NextLink>
              </Button>
              <Button asChild variant="outline" justifyContent="start">
                <NextLink href="/admin/kb?add=1">
                  Add a manual or safety reference
                </NextLink>
              </Button>
              <Button asChild variant="outline" justifyContent="start">
                <NextLink href="/admin/kb">
                  Replace an existing document
                </NextLink>
              </Button>
              <Button asChild variant="outline" justifyContent="start">
                <NextLink href="/admin/learn-cards">
                  Update learning content
                </NextLink>
              </Button>
            </Stack>
          </Box>
          <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
            <Heading as="h2" size="lg" mb={2}>
              Check the result
            </Heading>
            <Text color="muted" mb={4}>
              Try questions about a vehicle or topic to see how the chatbot uses
              the information you’ve made available.
            </Text>
            <Button asChild variant="outline">
              <NextLink href="/admin/chatbot">Try the chatbot</NextLink>
            </Button>
          </Box>
        </Stack>
      </Grid>
    </AdminLayout>
  );
}
