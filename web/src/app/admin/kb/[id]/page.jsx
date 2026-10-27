"use client";

import { Suspense, useEffect, useState } from "react";
import NextLink from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Stack,
  Text,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import { useContent } from "@/components/ContentProvider";
import { Checkbox } from "@/components/ui/checkbox";
import FileModal from "@/components/modals/FileModal";
import DocumentCoverage from "@/components/admin/DocumentCoverage";
import DocumentReview from "@/components/admin/DocumentReview";
import DocumentAvailability from "@/components/admin/DocumentAvailability";
import DocumentImpact from "@/components/admin/DocumentImpact";
import ReviewQuestions, {
  QuestionDialog,
} from "@/components/admin/ReviewQuestions";
import {
  documentJourney,
  documentCoverage,
  coverageNames,
  documentSourceIds,
} from "@/lib/adminJourney.mjs";
import {
  downloadDocumentUrl,
  publishDocument,
  unpublishDocument,
  stageReplacement,
} from "@/api/documents.mjs";
import { request } from "@/api/client.mjs";

export default function DocumentPage() {
  return (
    <Suspense fallback={<Text p={8}>Opening document…</Text>}>
      <DocumentWorkspace />
    </Suspense>
  );
}

function DocumentWorkspace() {
  const { id } = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const {
    documents,
    knowledge,
    reviewQuestions,
    loading,
    refresh,
    processDocuments,
    saveDocument,
    deleteDocument,
  } = useContent();
  const document = documents.find((row) => row.id === id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [coverageDirty, setCoverageDirty] = useState(false);
  const [editingCoverage, setEditingCoverage] = useState(false);
  const [reviewLoaded, setReviewLoaded] = useState(false);
  const [checked, setChecked] = useState(false);
  const [modal, setModal] = useState("");
  const [askingQuestion, setAskingQuestion] = useState(false);
  const sourceIds = documentSourceIds(document, documents);
  const openQuestions = reviewQuestions.filter(
    (question) => sourceIds.has(question.document_id) && !question.vehicle_id,
  );
  useEffect(() => {
    setChecked(false);
  }, [document?.source_revision, reviewQuestions]);
  if (!document || !knowledge)
    return (
      <AdminLayout title="Document workspace">
        <Text>
          {loading
            ? "Opening your document…"
            : !document
              ? "This document could not be found. Return to the library or retry loading above."
              : "Vehicle and topic details could not be loaded. Retry loading above."}
        </Text>
        <Button asChild mt={4} variant="outline">
          <NextLink href="/admin/kb">Back to reference library</NextLink>
        </Button>
      </AdminLayout>
    );
  const journey = documentJourney(document, knowledge);
  const coverage = documentCoverage(document.id, knowledge);
  const hasCoverage =
    coverage.vehicle_ids.length + coverage.category_ids.length > 0;
  const isPreparing = ["processing", "awaiting_index"].includes(document.status);
  const ready =
    document.status === "processed" &&
    document.indexed_revision === document.source_revision &&
    document.chunk_count > 0;
  const previous = documents.find(
    (row) => row.id === document.replacement_for_id,
  );
  const existingReplacement = documents.find(
    (row) =>
      row.replacement_for_id === document.id &&
      !row.superseded_by_id &&
      !row.published,
  );
  const currentStep = !hasCoverage
    ? 0
    : !ready
      ? 1
      : !document.source_fidelity_verified
        ? 2
        : 3;

  async function act(action, success) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh({ documentsOnly: true });
      setNotice(success);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminLayout
      title={document.name}
      description="Everything needed to check this document and make it useful to drivers."
    >
      <Stack gap={6}>
        <Flex gap={3} justify="space-between" align="center" wrap="wrap">
          <Button asChild variant="outline">
            <NextLink href="/admin/kb">Back to reference library</NextLink>
          </Button>
          <Flex gap={3} align="center" wrap="wrap">
            <Badge colorPalette={journey.color}>{journey.label}</Badge>
            {document.published &&
              !document.superseded_by_id &&
              (existingReplacement ? (
                <Button asChild>
                  <NextLink href={`/admin/kb/${existingReplacement.id}`}>
                    Continue replacement
                  </NextLink>
                </Button>
              ) : (
                <Button
                  disabled={busy || isPreparing || coverageDirty}
                  onClick={() => setModal("replace")}
                >
                  Replace document
                </Button>
              ))}
          </Flex>
        </Flex>
        {error && <Text role="alert">{error}</Text>}
        {notice && <Text role="status">{notice}</Text>}
        {document.superseded_by_id ? (
          <Box bg="white" p={6} borderRadius="12px">
            <Heading size="lg">A newer version is in use</Heading>
            <Text mt={2}>
              This version is kept so earlier references can still be checked.
            </Text>
            <Button asChild mt={4}>
              <NextLink href={`/admin/kb/${document.superseded_by_id}`}>
                Open current version
              </NextLink>
            </Button>
          </Box>
        ) : (
          <>
            {document.replacement_for_id && (
              <Box bg="brand.100" p={5} borderRadius="12px">
                <Heading size="md">
                  Updating {previous?.name || "an earlier document"}
                </Heading>
                <Text mt={2}>
                  {previous?.published
                    ? "The current document stays available while you check this replacement."
                    : "This replacement is not yet available to drivers."}{" "}
                  Vehicle and topic selections were copied; confirm they still
                  match the new manual.
                </Text>
                <Text mt={2} fontSize="sm">
                  Replacing this document does not update service schedules or
                  learning guides automatically. Check related guidance against
                  the new manual.
                </Text>
                <Button asChild variant="outline" mt={3}>
                  <a href="#document-impact">
                    See which schedules reference earlier versions
                  </a>
                </Button>
                {previous && (
                  <Button asChild variant="outline" mt={3}>
                    <NextLink href={`/admin/kb/${previous.id}`}>
                      View previous document
                    </NextLink>
                  </Button>
                )}
              </Box>
            )}
            {!document.published && (
              <Flex
                as="ol"
                aria-label="Document progress"
                gap={3}
                wrap="wrap"
                p={0}
                m={0}
                listStyleType="none"
              >
                {[
                  "Confirm coverage",
                  "Prepare document",
                  "Check document",
                  "Make available",
                ].map((label, index) => (
                  <Box
                    as="li"
                    key={label}
                    flex="1"
                    minW="140px"
                    p={3}
                    borderTopWidth="3px"
                    borderColor={
                      index <= currentStep ? "brand.500" : "gray.200"
                    }
                    aria-current={index === currentStep ? "step" : undefined}
                  >
                    <Text
                      fontSize="sm"
                      fontWeight={index === currentStep ? "650" : "400"}
                    >
                      {index + 1}. {label}
                    </Text>
                  </Box>
                ))}
              </Flex>
            )}
            <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
              <Flex
                justify="space-between"
                gap={3}
                align="center"
                mb={3}
                wrap="wrap"
              >
                <Heading size="lg">
                  Which vehicles or topics does it cover?
                </Heading>
                {hasCoverage && (
                  <Button
                    variant="outline"
                    disabled={busy || isPreparing}
                    onClick={() => {
                      if (
                        editingCoverage &&
                        coverageDirty &&
                        !window.confirm("Discard unsaved coverage changes?")
                      )
                        return;
                      setEditingCoverage((value) => !value);
                    }}
                  >
                    {editingCoverage
                      ? "Hide coverage details"
                      : "Change coverage"}
                  </Button>
                )}
              </Flex>
              {hasCoverage && (
                <Stack gap={1} mb={4}>
                  {coverageNames(document.id, knowledge).map((name) => (
                    <Text key={name}>{name}</Text>
                  ))}
                </Stack>
              )}
              {(!hasCoverage || editingCoverage) && (
                <DocumentCoverage
                  key={document.id}
                  document={document}
                  preferredVehicle={search.get("vehicle") || ""}
                  onDirty={setCoverageDirty}
                  disabled={busy || isPreparing}
                />
              )}
            </Box>
            {!document.published && (
              <>
                <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                  <Heading size="lg" mb={3}>
                    Prepare the document
                  </Heading>
                  {isPreparing ? (
                    <>
                      {document.error && (
                        <Box mb={3}>
                          <Text role="alert">
                            Indexing could not finish. The index worker will retry
                            automatically while it is running. If this continues,
                            check the worker logs using the details below.
                          </Text>
                          <Box as="details" mt={2}>
                            <Box as="summary">Problem details</Box>
                            <Text fontSize="sm">{document.error}</Text>
                          </Box>
                        </Box>
                      )}
                      <Text role="status">
                        Your document is being prepared for the chatbot. You can
                        leave this page and return later; progress updates
                        automatically.
                      </Text>
                      <Text mt={3} color="muted">
                        When it is ready, it will appear on Home under “Needs
                        your attention”.
                      </Text>
                    </>
                  ) : ready ? (
                    <Text>The document is ready to check below.</Text>
                  ) : (
                    <>
                      <Text color="muted">
                        The system will read the document so you can check it
                        before the chatbot uses it.
                      </Text>
                      {document.error && (
                        <Box mt={3}>
                          <Text role="alert">
                            The document needs attention. Try preparing it
                            again. If the problem continues, use a clearer copy.
                          </Text>
                          <Box as="details" mt={2}>
                            <Box as="summary">Problem details</Box>
                            <Text fontSize="sm">{document.error}</Text>
                          </Box>
                        </Box>
                      )}
                      {(!hasCoverage || coverageDirty) && (
                        <Text mt={3}>
                          Save the vehicle or topic selections above to
                          continue.
                        </Text>
                      )}
                      <Button
                        mt={4}
                        disabled={!hasCoverage || coverageDirty || busy}
                        loading={busy}
                        onClick={() =>
                          act(async () => {
                            const results = await processDocuments(
                              [document.id],
                              document.status === "processed",
                            );
                            if (results[0]?.error)
                              throw new Error(results[0].error);
                          }, "Preparation requested. You can leave this page and return later.")
                        }
                      >
                        {document.status === "failed"
                          ? "Try preparing again"
                          : "Prepare document"}
                      </Button>
                    </>
                  )}
                </Box>
                {ready && (
                  <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                    <Heading size="lg" mb={3}>
                      Check that the document was read correctly
                    </Heading>
                    <DocumentReview
                      key={document.source_revision}
                      document={document}
                      onLoaded={setReviewLoaded}
                      onUpdated={() => refresh({ documentsOnly: true })}
                    />
                    {document.source_fidelity_verified ? (
                      <Text role="status" mt={4}>
                        The document has been marked as checked.
                      </Text>
                    ) : (
                      <Stack gap={3} mt={5}>
                        <Checkbox
                          checked={checked}
                          disabled={
                            !reviewLoaded || busy || openQuestions.length > 0
                          }
                          onCheckedChange={(event) =>
                            setChecked(event.checked === true)
                          }
                        >
                          I checked the important instructions, numbers, units
                          and tables against the original.
                        </Checkbox>
                        <Button
                          alignSelf="start"
                          loading={busy}
                          disabled={
                            !checked ||
                            !reviewLoaded ||
                            coverageDirty ||
                            busy ||
                            openQuestions.length > 0
                          }
                          onClick={() =>
                            act(
                              () =>
                                request(`/documents/${document.id}`, {
                                  method: "PATCH",
                                  body: { source_fidelity_verified: true },
                                }),
                              "Your check is saved. The document is ready for the final step.",
                            )
                          }
                        >
                          Save document check
                        </Button>
                        <Text fontSize="sm" color="muted">
                          Not sure about something? Leave this step unfinished.
                          You can return from Home after confirming the
                          information.
                        </Text>
                      </Stack>
                    )}
                  </Box>
                )}
                <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                  <Heading size="lg" mb={3}>
                    Make this document available
                  </Heading>
                  {openQuestions.length > 0 && (
                    <Text mb={3} color="orange.800">
                      There are open questions about this document. Resolve them
                      below before approving it.
                    </Text>
                  )}
                  <Text>
                    Publishing makes this reference available for its selected
                    vehicles and topics. Chatbot access is shown here after
                    publication.
                  </Text>
                  {document.replacement_for_id && (
                    <Text mt={3}>
                      This will replace the previous document. Its service
                      schedules and related learning guides still need to be
                      checked separately.
                    </Text>
                  )}
                  {(!ready ||
                    !document.source_fidelity_verified ||
                    !hasCoverage ||
                    coverageDirty) && (
                    <Text mt={3} color="muted">
                      Finish and save the steps above before making this
                      document available.
                    </Text>
                  )}
                  <Button
                    mt={4}
                    disabled={
                      !ready ||
                      !document.source_fidelity_verified ||
                      !hasCoverage ||
                      coverageDirty ||
                      openQuestions.length > 0 ||
                      busy
                    }
                    loading={busy}
                    onClick={() => {
                      if (
                        window.confirm(
                          document.replacement_for_id
                            ? "Make this checked replacement available and retire the previous document? Related service guidance is not changed automatically."
                            : "Make this checked document available for the selected vehicles and topics?",
                        )
                      )
                        act(
                          () => publishDocument(document.id),
                          "Document published. Check chatbot availability below.",
                        );
                    }}
                  >
                    {document.replacement_for_id
                      ? "Use this replacement"
                      : "Make document available"}
                  </Button>
                </Box>
              </>
            )}
            {document.published && (
              <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                <Heading size="lg" mb={3}>
                  What drivers can use
                </Heading>
                <DocumentAvailability document={document} />
              </Box>
            )}
            <DocumentImpact document={document} />
          </>
        )}
        <Box bg="brand.50" p={5} borderRadius="12px">
          <Flex justify="space-between" gap={3} wrap="wrap" align="center">
            <Box>
              <Heading size="md">
                Something in this document needs checking?
              </Heading>
              <Text mt={1}>
                Save the question and its source now, then return when you have
                clarification.
              </Text>
            </Box>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setAskingQuestion(true)}
            >
              Save a question
            </Button>
          </Flex>
          {document.published && openQuestions.length > 0 && (
            <Text mt={3} color="orange.800">
              This document is still available to drivers. Use “Take document
              offline” below if its guidance may be incorrect.
            </Text>
          )}
        </Box>
        <ReviewQuestions documentId={document.id} />
        <Box as="details" bg="white" p={5} borderRadius="12px">
          <Box as="summary">Document details and other actions</Box>
          <Stack mt={4} gap={3} align="start">
            <Text fontSize="sm">
              Original file: {document.original_filename}. Added {document.date}
              .
            </Text>
            <Flex gap={3} wrap="wrap">
              <Button asChild variant="outline">
                <a
                  href={downloadDocumentUrl(document.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Download original
                </a>
              </Button>
              <Button
                variant="outline"
                disabled={busy || isPreparing}
                onClick={() => setModal("edit")}
              >
                Edit title and details
              </Button>
              {!document.published && ready && (
                <Button
                  variant="outline"
                  disabled={busy || coverageDirty}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Prepare this document again? You will need to check it again before making it available.",
                      )
                    )
                      act(async () => {
                        const results = await processDocuments(
                          [document.id],
                          true,
                        );
                        if (results[0]?.error)
                          throw new Error(results[0].error);
                        setChecked(false);
                      }, "Preparation requested again.");
                  }}
                >
                  Prepare document again
                </Button>
              )}
              {!document.superseded_by_id &&
                (existingReplacement ? (
                  <Button asChild>
                    <NextLink href={`/admin/kb/${existingReplacement.id}`}>
                      Continue unfinished replacement
                    </NextLink>
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    disabled={busy || isPreparing || coverageDirty}
                    onClick={() => setModal("replace")}
                  >
                    Replace document
                  </Button>
                ))}
              {document.published && (
                <Button
                  variant="outline"
                  disabled={busy || isPreparing}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Take this document offline? The chatbot and manual library will stop offering it. Service schedules are managed separately.",
                      )
                    )
                      act(
                        () => unpublishDocument(document.id),
                        "Document taken offline. Related service schedules have not changed.",
                      );
                  }}
                >
                  Take document offline
                </Button>
              )}
              <Button
                variant="outline"
                colorPalette="red"
                disabled={busy || isPreparing}
                onClick={() => {
                  if (
                    window.confirm(
                      `Permanently delete ${document.name} and its files? Documents used by service schedules or version history must be kept.`,
                    )
                  )
                    act(async () => {
                      await deleteDocument(document.id);
                      router.push("/admin/kb");
                    }, "Document deleted.");
                }}
              >
                Delete document
              </Button>
            </Flex>
          </Stack>
        </Box>
      </Stack>
      {askingQuestion && (
        <QuestionDialog
          context={{
            document_id: document.id,
            source_revision: document.source_revision,
            source_type: document.source_type,
            title: document.name.slice(0, 300),
          }}
          onClose={() => setAskingQuestion(false)}
          onSaved={() => {
            setChecked(false);
            setNotice(
              "Question saved. You can find it here or on Home when you return.",
            );
          }}
        />
      )}
      {modal && (
        <FileModal
          key={`${document.id}:${modal}`}
          isOpen
          editData={document}
          replacementFor={modal === "replace" ? document.id : null}
          onClose={() => setModal("")}
          onSave={async (data) => {
            if (modal === "replace") {
              try {
                const replacement = await stageReplacement(
                  document.id,
                  data.files[0],
                );
                await refresh({ documentsOnly: true });
                router.push(`/admin/kb/${replacement.id}`);
              } catch (cause) {
                await refresh({ documentsOnly: true });
                throw cause;
              }
            } else await saveDocument(document, data);
          }}
        />
      )}
    </AdminLayout>
  );
}
