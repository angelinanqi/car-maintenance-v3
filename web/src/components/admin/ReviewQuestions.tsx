"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { useContent } from "@/components/ContentProvider";
import { originalDocumentUrl } from "@/api/documents.mjs";
import {
  createQuestion,
  decideQuestion,
  loadQuestions,
  type QuestionDraft,
  type ReviewQuestion,
} from "@/api/reviewQuestions";
import { questionHref } from "@/lib/adminJourney.mjs";
import RecordDialog from "./RecordDialog";
import FormField from "./FormField";

export type QuestionContext = Pick<
  QuestionDraft,
  "document_id" | "source_revision" | "title"
> &
  Partial<QuestionDraft> & { source_type?: string };

export function QuestionDialog({
  context,
  onClose,
  onSaved,
}: {
  context: QuestionContext;
  onClose: () => void;
  onSaved?: (question: ReviewQuestion) => void;
}) {
  const { refresh } = useContent();
  const [question, setQuestion] = useState(context.question || "");
  const [excerpt, setExcerpt] = useState(context.excerpt || "");
  const [page, setPage] = useState(context.source_page?.toString() || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <RecordDialog
      title="Leave a question for clarification"
      description="Save what is unclear and where you found it. This note is private to admins and will appear on Home when you return."
      busy={busy}
      dirty={Boolean(
        question ||
        excerpt !== (context.excerpt || "") ||
        page !== (context.source_page?.toString() || ""),
      )}
      error={error}
      onClose={onClose}
      saveLabel="Save question for later"
      onSubmit={async (event) => {
        event.preventDefault();
        if (busy) return;
        setBusy(true);
        setError("");
        try {
          const saved = await createQuestion({
            document_id: context.document_id,
            source_revision: context.source_revision,
            vehicle_id: context.vehicle_id || null,
            schedule_id: context.schedule_id || null,
            item_id: context.item_id || null,
            title: context.title,
            question: question.trim(),
            excerpt: excerpt.trim(),
            source_page:
              context.source_type === "md" ? null : page ? Number(page) : null,
          });
          await refresh({
            resources: ["reviewQuestions", "scheduleDrafts", "documents"],
          });
          onSaved?.(saved);
          onClose();
        } catch (cause) {
          setError((cause as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Text fontWeight="600">{context.title}</Text>
      <FormField label="What needs to be clarified?">
        <Textarea
          required
          maxLength={4000}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="For example: Does this symbol mean inspect or replace?"
        />
      </FormField>
      {context.source_type !== "md" && (
        <FormField label="Page in the manual (optional)">
          <Input
            type="number"
            min={1}
            step={1}
            value={page}
            onChange={(event) => setPage(event.target.value)}
          />
        </FormField>
      )}
      <FormField label="Relevant words, symbols or instructions (optional)">
        <Textarea
          maxLength={2000}
          value={excerpt}
          onChange={(event) => setExcerpt(event.target.value)}
        />
      </FormField>
      <Text fontSize="sm" color="muted">
        Open questions prevent approval of the affected document or service
        tasks. Information already available to drivers stays live until you
        take it offline.
      </Text>
    </RecordDialog>
  );
}

export default function ReviewQuestions({
  documentId,
  vehicleId,
  onSource,
  title = "Questions needing clarification",
}: {
  documentId?: string;
  vehicleId?: string;
  onSource?: (question: ReviewQuestion) => void;
  title?: string;
}) {
  const { refresh, reviewQuestions } = useContent();
  const [rows, setRows] = useState<ReviewQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [resolving, setResolving] = useState<ReviewQuestion | null>(null);
  const [resolution, setResolution] = useState("");
  const [busy, setBusy] = useState(false);
  const [decisionError, setDecisionError] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const filters: Record<string, string> = {};
    if (documentId) filters.document_id = documentId;
    if (vehicleId) filters.vehicle_id = vehicleId;
    loadQuestions(filters)
      .then((rows) => {
        if (active)
          setRows(
            rows.sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
          );
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
  }, [documentId, vehicleId, reviewQuestions, attempt]);
  const open = rows.filter((row) => row.status === "open");
  const resolved = rows.filter((row) => row.status === "resolved");
  async function decide(
    question: ReviewQuestion,
    status: ReviewQuestion["status"],
    answer: string,
  ) {
    if (busy) return;
    setBusy(true);
    setDecisionError("");
    setError("");
    try {
      await decideQuestion(question, status, answer);
      await refresh({ resources: ["reviewQuestions", "scheduleDrafts"] });
      setAttempt((value) => value + 1);
      setResolving(null);
    } catch (cause) {
      if (resolving) setDecisionError((cause as Error).message);
      else setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function card(question: ReviewQuestion) {
    return (
      <Box key={question.id} borderWidth="1px" p={4} borderRadius="8px">
        <Badge colorPalette={question.status === "open" ? "orange" : "green"}>
          {question.status === "open" ? "Needs clarification" : "Clarified"}
        </Badge>
        <Heading size="md" mt={2}>
          {question.title}
        </Heading>
        {documentId && question.document_id !== documentId && (
          <Text mt={2} fontSize="sm" color="orange.800">
            Saved against an earlier version of this document. Check whether the
            replacement clarifies it before resolving.
          </Text>
        )}
        <Text fontSize="sm" color="muted" mt={1}>
          {[question.vehicle_name, question.document_name]
            .filter(Boolean)
            .join(" · ")}
        </Text>
        {question.source_changed && (
          <Text mt={2} fontSize="sm" color="orange.800">
            This document has been prepared or changed since the question was
            saved. Use the retained quotation and check the current original
            before resolving it.
          </Text>
        )}
        <Text mt={2} whiteSpace="pre-wrap">
          {question.question}
        </Text>
        {question.excerpt && (
          <Box
            as="blockquote"
            mt={3}
            borderLeftWidth="2px"
            borderColor="brand.500"
            pl={3}
          >
            <Text fontSize="sm" whiteSpace="pre-wrap">
              {question.excerpt}
            </Text>
          </Box>
        )}
        <Text fontSize="sm" color="muted" mt={3}>
          {question.source_page ? `Manual page ${question.source_page} · ` : ""}
          Updated {new Date(question.updated_at).toLocaleDateString("en-GB")}
        </Text>
        {question.resolution && (
          <Text mt={3} whiteSpace="pre-wrap">
            Clarification: {question.resolution}
          </Text>
        )}
        <Flex gap={3} wrap="wrap" mt={3}>
          {onSource ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onSource(question)}
            >
              Check the source
            </Button>
          ) : (
            <Button asChild size="sm" variant="outline">
              <a
                href={`${originalDocumentUrl(question.document_id)}${question.source_page ? `#page=${question.source_page}` : ""}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open original document
              </a>
            </Button>
          )}
          {!documentId && !vehicleId && (
            <Button asChild size="sm" variant="outline">
              <NextLink href={questionHref(question)}>
                Open related work
              </NextLink>
            </Button>
          )}
          {question.status === "open" ? (
            <Button
              size="sm"
              disabled={busy}
              onClick={() => {
                setResolving(question);
                setResolution(question.resolution || "");
                setDecisionError("");
              }}
            >
              Record clarification
            </Button>
          ) : (
            <Button
              size="sm"
              variant="plain"
              disabled={busy}
              onClick={() => decide(question, "open", question.resolution)}
            >
              Reopen question
            </Button>
          )}
        </Flex>
      </Box>
    );
  }
  return (
    <Box
      id="questions"
      bg="white"
      p={{ base: 5, md: 7 }}
      borderRadius="12px"
      scrollMarginTop="20px"
    >
      <Flex justify="space-between" gap={3} wrap="wrap" align="center" mb={3}>
        <Heading size="lg">{title}</Heading>
        <Button
          size="sm"
          variant="outline"
          onClick={() => refresh({ resources: ["reviewQuestions"] })}
        >
          Refresh questions
        </Button>
      </Flex>
      <Text color="muted" mb={4}>
        Keep the question and its reference together. Record the answer after
        checking it with a reliable source or someone qualified. Resolving a
        question does not change the guidance automatically.
      </Text>
      {loading && <Text role="status">Opening saved questions…</Text>}
      {error && <Text role="alert">{error}</Text>}
      <Stack gap={3}>{open.map(card)}</Stack>
      {!loading && !error && !open.length && (
        <Text>No open questions here.</Text>
      )}
      {resolved.length > 0 && (
        <Box as="details" mt={4}>
          <Box as="summary">Previously clarified ({resolved.length})</Box>
          <Stack gap={3} mt={3}>
            {resolved.map(card)}
          </Stack>
        </Box>
      )}
      {resolving && (
        <RecordDialog
          title="Record what was clarified"
          description="Explain the answer and the manual, reference, or qualified advice you used. Then correct any affected guidance before approving it."
          busy={busy}
          dirty={resolution !== resolving.resolution}
          error={decisionError}
          onClose={() => setResolving(null)}
          saveLabel="Mark as clarified"
          onSubmit={(event) => {
            event.preventDefault();
            decide(resolving, "resolved", resolution);
          }}
        >
          <Text fontWeight="600">{resolving.question}</Text>
          <FormField label="What did you confirm, and how?">
            <Textarea
              required
              maxLength={4000}
              value={resolution}
              onChange={(event) => setResolution(event.target.value)}
            />
          </FormField>
        </RecordDialog>
      )}
    </Box>
  );
}
