"use client";
import Pagination, { usePagination } from "@/components/admin/Pagination";
import { Suspense, useState } from "react";
import NextLink from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import FileModal from "@/components/modals/FileModal";
import DocumentTestSummary from "@/components/admin/DocumentTestSummary";
import DocumentTagManager from "@/components/admin/DocumentTagManager";
import { AdminSelect } from "@/components/admin/NativeControls";
import { useContent } from "@/components/ContentProvider";
import { documentJourney, coverageNames } from "@/lib/adminJourney.mjs";
import { matchesTestFilter } from "@/lib/documentTestFollowUp.mjs";

export default function DocumentsPage() {
  return (
    <Suspense fallback={<Text p={8}>Opening reference library…</Text>}>
      <DocumentLibrary />
    </Suspense>
  );
}
function DocumentLibrary() {
  const { documents, knowledge, uploadDocuments, refresh, loading, documentTests, documentTestError } = useContent();
  const search = useSearchParams();
  const router = useRouter();
  const [uploadOpen, setUploadOpen] = useState(search.get("add") === "1");
  const [query, setQuery] = useState("");
  const [tagsOpen, setTagsOpen] = useState(false);
  const [filter, setFilter] = useState("current");
  const preferredVehicle = search.get("vehicle") || "";
  const testFilter = filter.startsWith("tests:") ? filter.slice(6) : "";
  const rows = documents
    .filter((document) => {
      const journey = documentJourney(document, knowledge);
      const summary = documentTests?.[document.id];
      const testsNeedAttention = !document.superseded_by_id && !documentTestError && matchesTestFilter(summary, "attention");
      const text = [
        document.name,
        document.original_filename,
        ...(document.tags || []),
        ...coverageNames(document.id, knowledge),
      ]
        .join(" ")
        .toLowerCase();
      const matchesFilter =
        filter === "all" ||
        (filter === "current" && !document.superseded_by_id) ||
        (filter === "unfinished" &&
          (!["available", "replaced", "preparing"].includes(journey.stage) ||
            testsNeedAttention)) ||
        filter === journey.stage ||
        (testFilter && !documentTestError && !document.superseded_by_id && matchesTestFilter(summary, testFilter));
      return text.includes(query.trim().toLowerCase()) && matchesFilter;
    })
    .sort(
      (a, b) =>
        new Date(b.updated_at || b.created_at) -
        new Date(a.updated_at || a.created_at),
    );
  const pagination = usePagination(rows, JSON.stringify([query, filter]));
  return (
    <AdminLayout
      title="Reference Library"
      description="Keep manuals and safety references up to date. Open a document to see its coverage, progress and next step."
    >
      <Stack gap={5}>
        <Flex gap={3} align="center" justify="space-between" wrap="wrap">
          <Heading as="h2" size="lg">
            Your Documents
          </Heading>
          <Flex gap={3} wrap="wrap">
            <Button variant="outline" disabled={loading} onClick={() => setTagsOpen(true)}>Manage tags</Button>
            <Button
              variant="outline"
              onClick={() => refresh({ documentsOnly: true })}
            >
              Refresh
            </Button>
            <Button onClick={() => setUploadOpen(true)}>Add document</Button>
          </Flex>
        </Flex>
        <Flex gap={4} align="end" wrap="wrap">
          <Box as="label" flex="1" minW="200px">
            Find a document
            <Input
              placeholder="Search by title, vehicle, topic or filename"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </Box>
          <Box as="label" minW="200px">
            Show
            <AdminSelect
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="current">Current documents</option>
              <option value="unfinished">Needs your attention</option>
              <option value="preparing">Being prepared</option>
              <option value="available">Published documents</option>
              <option value="tests:attention">Tests needing follow-up</option>
              <option value="tests:needs_fixing">Test answers needing fixes</option>
              <option value="tests:outdated">Outdated test results</option>
              <option value="tests:failed">Failed test runs</option>
              <option value="replaced">Previous versions</option>
              <option value="all">All documents</option>
            </AdminSelect>
          </Box>
        </Flex>
        {!loading && !documents.length && (
          <Box bg="white" p={8} borderRadius="12px">
            <Heading size="lg">Add Your First Reference</Heading>
            <Text mt={2} color="muted">
              Start with a trusted manual or safety document. After uploading,
              choose which vehicles or topics it covers and check it before
              making it available.
            </Text>
            <Button mt={5} onClick={() => setUploadOpen(true)}>
              Add document
            </Button>
          </Box>
        )}
        {documents.length > 0 && !rows.length && (
          <Box bg="white" p={6} borderRadius="12px">
            <Text>{(testFilter || filter === "unfinished") && (documentTestError || !documentTests)
              ? "Test follow-up could not be checked. Retry loading before using this filter."
              : "No documents match this search."}</Text>
            <Button
              mt={3}
              variant="outline"
              onClick={() => {
                setQuery("");
                setFilter("current");
              }}
            >
              Clear search and filters
            </Button>
          </Box>
        )}
        <Stack as="ul" gap={3} listStyleType="none" m={0} p={0}>
          {pagination.items.map((document) => {
            const journey = documentJourney(document, knowledge);
            const names = coverageNames(document.id, knowledge);
            return (
              <Box
                as="li"
                key={document.id}
                bg="white"
                p={{ base: 5, md: 6 }}
                borderRadius="12px"
              >
                <Flex
                  justify="space-between"
                  gap={5}
                  align="center"
                  wrap="wrap"
                >
                  <Box flex="1" minW="min(100%, 240px)">
                    <Badge colorPalette={journey.color} mb={2}>
                      {journey.label}
                    </Badge>
                    <Heading as="h3" size="md">
                      <NextLink href={`/admin/kb/${document.id}`}>
                        {document.name}
                      </NextLink>
                    </Heading>
                    <Text mt={2} color="muted" fontSize="sm">
                      {names.length
                        ? names.join("; ")
                        : knowledge
                          ? "Vehicle or topic not chosen yet"
                          : "Loading coverage…"}
                    </Text>
                    <Text fontSize="sm" color="muted" mt={1}>
                      {document.replacement_for_id ? "Updated version · " : ""}
                      {document.document_type?.replaceAll("_", " ")} · Added{" "}
                      {document.date}
                    </Text>
                    {document.original_filename?.startsWith('website-') && <Text fontSize="sm" color="muted">Website article snapshot</Text>}
                    <DocumentTestSummary documentId={document.id} documentName={document.name} summary={documentTests?.[document.id]}
                      error={documentTestError} loading={loading} filter={testFilter} />
                  </Box>
                  <Button
                    asChild
                    variant={
                      ["available", "replaced"].includes(journey.stage)
                        ? "outline"
                        : "solid"
                    }
                  >
                    <NextLink
                      href={`/admin/kb/${document.superseded_by_id || document.id}${journey.stage === "review" ? "#document-review" : ""}`}
                    >
                      {journey.next}
                      <Box as="span" srOnly>
                        {" "}
                        for {document.name}
                      </Box>
                    </NextLink>
                  </Button>
                </Flex>
              </Box>
            );
          })}
        </Stack>
        <Pagination {...pagination} label="Reference Documents" />
      </Stack>
      {uploadOpen && (
        <FileModal
          isOpen
          preferredVehicle={preferredVehicle}
          tags={documents.flatMap((document) => document.tags || [])}
          onClose={() => setUploadOpen(false)}
          onSave={uploadDocuments}
          onUploadedDone={(documents) => {
            const document = documents[0];
            if (documents.length === 1 && document)
              router.push(
                `/admin/kb/${document.id}${preferredVehicle ? `?vehicle=${encodeURIComponent(preferredVehicle)}` : ""}`,
              );
          }}
        />
      )}
      {tagsOpen && <DocumentTagManager onClose={() => setTagsOpen(false)} />}
    </AdminLayout>
  );
}
