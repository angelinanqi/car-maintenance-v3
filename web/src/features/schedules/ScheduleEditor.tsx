"use client";

import { useEffect, useRef, useState } from "react";
import useScheduleResources from "./useScheduleResources";
import SchedulePreview from "./SchedulePreview";
import ScheduleChanges from "./ScheduleChanges";
import NextLink from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Badge,
  Box,
  Button,
  Flex,
  Grid,
  Heading,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import AdminLayout from "@/components/layouts/AdminLayout";
import FormField from "@/components/admin/FormField";
import { AdminSelect } from "@/components/admin/NativeControls";
import useUnsavedChanges from "@/components/admin/useUnsavedChanges";
import PublicationChecklist from "@/components/admin/PublicationChecklist";
import ServiceTaskEditor from "@/components/admin/ServiceTaskEditor";
import MaintenanceItemEditor from "@/components/admin/MaintenanceItemEditor";
import MaintenanceAssistance from "./MaintenanceAssistance";
import FrequencyTools from "@/components/admin/FrequencyTools";
import ReviewQuestions, {
  QuestionDialog,
  type QuestionContext,
} from "@/components/admin/ReviewQuestions";
import { useContent } from "@/components/ContentProvider";
import {
  serviceInstruction,
  scheduleStatus,
  scheduleProgress,
  scheduleEntryIssues,
  questionsForSchedule,
} from "@/lib/adminJourney.mjs";
import {
  sourceUrl,
  type Review,
  type Suggestion,
} from "@/api/maintenanceAssistance";
import {
  loadSchedules,
  saveSchedule,
  validateSchedule,
  publishSchedule,
  withdrawSchedule,
  deleteDraftSchedule,
  type Schedule,
  type ScheduleEntry,
} from "@/api/admin";

const newEntry = (): ScheduleEntry => ({
  itemId: null,
  action: "replace",
  rule: {
    type: "recurring",
    distanceKm: null,
    months: null,
    distanceMilestones: [],
    monthMilestones: [],
    vehicleStartDate: null,
    conditions: "",
    notes: "",
    sourceDocumentId: null,
    sourcePage: null,
  },
});

export default function ScheduleEditor() {
  const search = useSearchParams();
  const { refresh, reviewQuestions } = useContent();
  const [vehicleId, setVehicleId] = useState(search.get("vehicle") || "");
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [contentDirty, setDirty] = useState(false);
  const [contextDirty, setContextDirty] = useState(false);
  const [adminNote, setAdminNote] = useState("");
  const [questionContext, setQuestionContext] =
    useState<QuestionContext | null>(null);
  const [assistanceDirty, setAssistanceDirty] = useState(false);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [loadedVehicleId, setLoadedVehicleId] = useState('');
  const [loadError, setLoadError] = useState('');
  const createId = useRef('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sourceNotice, setSourceNotice] = useState("");
  const autoTablePending = useRef(false);
  const [pdfId, setPdfId] = useState(search.get("source") || "");
  const [page, setPage] = useState(
    Math.max(1, Number(search.get("page")) || 1),
  );
  const [reviewed, setReviewed] = useState(false);
  const [preview, setPreview] = useState(false);
  const [creatingItem, setCreatingItem] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const {
    vehicles,
    items,
    setItems,
    documents,
    links,
    loading,
    error: resourceError,
  } = useScheduleResources(reloadKey);
  const dirty = contentDirty || contextDirty;
  useUnsavedChanges(dirty || assistanceDirty);
  const canEdit = !schedule || schedule.status === "draft";
  const locked = busy || loading || scheduleLoading || Boolean(resourceError) ||
    Boolean(loadError) || (Boolean(vehicleId) && loadedVehicleId !== vehicleId);
  const vehicle = vehicles.find((row) => row.id === vehicleId);
  const sources = documents.filter(
    (document) =>
      (!document.superseded_by_id ||
        entries.some((entry) => entry.rule.sourceDocumentId === document.id) ||
        reviewQuestions.some(
          (question) =>
            question.document_id === document.id &&
            (!question.vehicle_id || question.vehicle_id === vehicleId),
        )) &&
      links.some(
        (link) =>
          link.vehicle_id === vehicleId && link.document_id === document.id,
      ),
  );
  const selectedSource = sources.find((document) => document.id === pdfId);
  const openQuestions = questionsForSchedule(
    reviewQuestions,
    vehicleId,
    entries,
    documents,
  );
  const progress = scheduleProgress(entries, documents);
  const publishedSchedule = schedules.find((row) => row.vehicle_id === vehicleId && row.status === "published");
  function viewSource(documentId: string, nextPage = 1) {
    autoTablePending.current = false;
    setSourceNotice("");
    if (documentId !== pdfId || nextPage !== page) {
      setPdfId(documentId);
      setPage(nextPage);
      if (canEdit) setContextDirty(true);
    }
  }
  useEffect(() => {
    setReviewed(false);
  }, [reviewQuestions]);


  useEffect(() => {
    if (!vehicleId) return;
    let active = true;
    setScheduleLoading(true);
    setLoadedVehicleId('');
    setLoadError('');
    loadSchedules(vehicleId)
      .then((rows) => {
        if (!active) return;
        setSchedules(rows);
        setLoadedVehicleId(vehicleId);
        createId.current = '';
        const latest = [...rows].sort((a, b) => b.revision - a.revision);
        const selected =
          rows.find((row) => row.id === search.get("schedule")) ||
          latest.find((row) => row.status === "draft") ||
          latest.find((row) => row.status === "published") ||
          null;
        setSchedule(selected);
        autoTablePending.current = !search.get("page") && !selected?.work_context?.page;
        setSourceNotice("");
        setEntries(selected?.entries || []);
        setAdminNote(selected?.admin_note || "");
        setPdfId(
          search.get("source") || selected?.work_context?.document_id || "",
        );
        setPage(
          Math.max(
            1,
            Number(search.get("page")) || selected?.work_context?.page || 1,
          ),
        );
        setContextDirty(false);
        setDirty(false);
        setReviewed(false);
      })
      .catch((cause) => {
        if (active) setLoadError(cause.message);
      })
      .finally(() => {
        if (active) setScheduleLoading(false);
      });
    return () => {
      active = false;
    };
  }, [vehicleId, reloadKey, search]);

  useEffect(() => {
    if (pdfId) return;
    const available = documents.filter(
      (document) =>
        !document.superseded_by_id &&
        links.some(
          (link) =>
            link.vehicle_id === vehicleId && link.document_id === document.id,
        ),
    );
    const first =
      available.find(
        (document) => document.document_type === "maintenance_booklet",
      ) || available[0];
    if (first) setPdfId(first.id);
  }, [documents, links, vehicleId, pdfId]);

  function canLeaveEdits() {
    return (
      !(dirty || assistanceDirty) ||
      window.confirm("Discard unsaved changes? Saved drafts will be kept.")
    );
  }
  function changeEntry(index: number, next: ScheduleEntry) {
    setEntries((previous) =>
      previous.map((entry, i) => (i === index ? next : entry)),
    );
    setDirty(true);
    setReviewed(false);
    setNotice("");
  }
  function importSuggestions(review: Review, suggestions: Suggestion[]) {
    if (
      !canEdit ||
      locked ||
      review.document_id !== selectedSource?.id ||
      review.source_revision !== selectedSource.source_revision
    )
      return;
    const seen = new Set(entries.map((entry) => entry.itemId));
    const additions: ScheduleEntry[] = [];
    let drafted = 0;
    for (const suggestion of suggestions) {
      if (suggestion.status !== "accepted") continue;
      const aiDraft = suggestion.ai_draft;
      if (aiDraft && (aiDraft.vehicle_id !== vehicleId || aiDraft.manual_entry_required || !aiDraft.reviewed_at || !aiDraft.rule)) continue;
      const item = items.find(
        (item) => item.id === suggestion.mapped_item_id && item.active,
      );
      if (!item || seen.has(item.id) || (aiDraft && aiDraft.action !== item.action)) continue;
      seen.add(item.id);
      const table = review.catalogue.tables.find(
        (table) => table.table_id === suggestion.table_id,
      );
      const bookmark = review.bookmarks.find(
        (bookmark) => bookmark.table_id === suggestion.table_id,
      );
      additions.push({
        ...newEntry(),
        itemId: item.id,
        action: item.action,
        rule: {
          ...newEntry().rule,
          ...(aiDraft?.rule || {}),
          sourceDocumentId: review.document_id,
          sourceRevision: review.source_revision,
          sourceTableId: suggestion.table_id,
          sourceSuggestionId: suggestion.suggestion_id,
          sourcePage:
            aiDraft?.source_page || suggestion.pages?.[0] || table?.pages[0] || bookmark?.page || null,
        },
      });
      if (aiDraft) drafted += 1;
    }
    setEntries([...entries, ...additions]);
    if (additions.length) {
      setDirty(true);
      setReviewed(false);
    }
    setNotice(
      `${additions.length} tasks added.${drafted ? ` ${drafted} include reviewed timing and conditions.` : " Enter each interval from the manual."} Save the schedule draft below to keep these additions. Tasks already present were skipped.`,
    );
  }
  async function saveDraft() {
    if (locked || !vehicleId || !canEdit) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!schedule && !createId.current) createId.current = crypto.randomUUID();
      const saved = await saveSchedule(
        schedule?.id || "",
        vehicleId,
        entries,
        adminNote,
        {
          document_id: pdfId || null,
          source_revision: selectedSource?.source_revision || null,
          page,
        },
        createId.current,
        schedule?.updated_at,
      );
      setSchedule(saved);
      setEntries(saved.entries);
      setContextDirty(false);
      setDirty(false);
      setReviewed(false);
      setSchedules((previous) => [
        ...previous.filter((row) => row.id !== saved.id),
        saved,
      ]);
      setNotice(
        "Draft saved. You can leave and continue from this vehicle later. Drivers will not see this draft.",
      );
      await refresh({
        resources: ["scheduleDrafts", "dashboard", "configuration"],
      });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function checkOrPublish(publishing: boolean) {
    if (
      !schedule ||
      dirty ||
      assistanceDirty ||
      locked ||
      (publishing &&
        (!canEdit || openQuestions.length > 0 || !entries.length || progress.incomplete > 0))
    )
      return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (publishing) {
        if (!reviewed)
          throw new Error(
            "Check every task against its manual before making the schedule available.",
          );
        const saved = await publishSchedule(schedule.id, schedule.updated_at);
        setSchedule(saved);
        setReviewed(false);
        setSchedules((previous) =>
          previous.map((row) =>
            row.id === saved.id
              ? saved
              : row.status === "published"
                ? { ...row, status: "superseded" }
                : row,
          ),
        );
        setNotice(
          "This service schedule is now available to drivers. The previous version is kept for reference.",
        );
        await refresh({
          resources: ["scheduleDrafts", "dashboard", "configuration"],
        });
      } else {
        await validateSchedule(schedule.id);
        setNotice(
          "No missing or invalid details were found. You still need to check the instructions against the original manual.",
        );
      }
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function retire() {
    if (!schedule || dirty || locked) return;
    const draft = schedule.status === "draft";
    if (
      !window.confirm(
        draft
          ? "Delete this unfinished draft?"
          : "Take this service schedule offline? Manufacturer reminders from this version will stop after the driver’s app refreshes. Personal tasks and service history are kept.",
      )
    )
      return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (draft) {
        await deleteDraftSchedule(schedule.id, schedule.updated_at);
        setSchedules((previous) =>
          previous.filter((row) => row.id !== schedule.id),
        );
        setSchedule(null);
        setEntries([]);
        createId.current = '';
      } else {
        const saved = await withdrawSchedule(schedule.id, schedule.updated_at);
        setSchedule(saved);
        setSchedules((previous) =>
          previous.map((row) => (row.id === saved.id ? saved : row)),
        );
      }
      setReviewed(false);
      setNotice(
        draft
          ? "Draft deleted."
          : "Schedule taken offline. Personal tasks and service history are kept.",
      );
      await refresh({
        resources: ["scheduleDrafts", "dashboard", "configuration"],
      });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminLayout
      title={
        vehicle ? `Service schedule: ${vehicle.name}` : "Service Schedules"
      }
      description="Use the manufacturer’s manual to check what needs doing and when. Save an unfinished draft whenever you need to stop."
    >
      <Stack gap={5}>
        {vehicleId && (
          <Button asChild variant="outline" alignSelf="start">
            <NextLink href={`/admin/vehicles/${vehicleId}`}>
              Back to vehicle overview
            </NextLink>
          </Button>
        )}
        {(error || resourceError || loadError) && (
          <Text role="alert">{error || resourceError || loadError}</Text>
        )}
        {notice && <Text role="status">{notice}</Text>}
        <Box bg="white" p={5} borderRadius="12px">
          <FormField label="Which vehicle are you working on?">
            <AdminSelect
              disabled={busy || loading || scheduleLoading}
              value={vehicleId}
              onChange={(event) => {
                if (!canLeaveEdits()) return;
                setVehicleId(event.target.value);
                setSchedules([]);
                setSchedule(null);
                setEntries([]);
                setAdminNote("");
                setContextDirty(false);
                setDirty(false);
                setReviewed(false);
                setPdfId("");
                setPage(1);
                setNotice("");
                setError("");
                setPreview(false);
              }}
            >
              <option value="">Choose a vehicle</option>
              {vehicles.map((row) => (
                <option key={row.id} value={row.id}>
                  {[row.name, row.year, row.engine, row.variant]
                    .filter(Boolean)
                    .join(" · ")}
                </option>
              ))}
            </AdminSelect>
          </FormField>
          {vehicle && (
            <Text mt={3} color="muted">
              {[vehicle.year, vehicle.engine, vehicle.variant]
                .filter(Boolean)
                .join(" · ")}{" "}
              — check that the manual covers this version.
            </Text>
          )}
          <Button
            size="sm"
            variant="plain"
            mt={3}
            disabled={busy || loading || scheduleLoading}
            onClick={() => {
              if (!canLeaveEdits()) return;
              setDirty(false);
              setContextDirty(false);
              setError("");
              setReloadKey((value) => value + 1);
            }}
          >
            Refresh saved work
          </Button>
        </Box>
        {loading || scheduleLoading ? (
          <Text role="status">Opening manuals and saved schedules…</Text>
        ) : (
          vehicleId && (
            <>
              <Box bg="brand.100" p={5} borderRadius="12px">
                <Flex
                  justify="space-between"
                  gap={3}
                  align="center"
                  wrap="wrap"
                >
                  <Box>
                    <Heading size="md">
                      {schedule
                        ? `Version ${schedule.revision}`
                        : "New Service Schedule"}
                    </Heading>
                    <Badge mt={2}>
                      {schedule
                        ? scheduleStatus(schedule.status)
                        : "Not saved yet"}
                    </Badge>
                  </Box>
                  <Flex gap={3} wrap="wrap">
                    {!canEdit && (
                      <Button
                        disabled={locked || assistanceDirty}
                        onClick={() => {
                          setSchedule(null);
                          createId.current = '';
                          setAdminNote("");
                          setEntries(structuredClone(entries));
                          setDirty(true);
                          setReviewed(false);
                          setNotice(
                            "You’re editing a new draft. The current schedule stays available until you approve this update.",
                          );
                        }}
                      >
                        Update this schedule
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      disabled={!entries.length || assistanceDirty || locked}
                      onClick={() => setPreview((value) => !value)}
                    >
                      {preview ? "Return to editing" : "Preview instructions"}
                    </Button>
                  </Flex>
                </Flex>
                {schedule?.status === "draft" && (
                  <Box mt={4}>
                    <Text fontSize="sm">
                      Last saved{" "}
                      {schedule.updated_at
                        ? new Date(schedule.updated_at).toLocaleString("en-GB")
                        : "as a draft"}
                      . {progress.total} service tasks; {progress.incomplete}{" "}
                      still need interval or reference details.
                    </Text>
                    {schedule.admin_note && (
                      <Text mt={2} whiteSpace="pre-wrap">
                        Your return note: {schedule.admin_note}
                      </Text>
                    )}
                  </Box>
                )}
                {progress.olderSources > 0 && (
                  <Text mt={3} color="orange.800">
                    {progress.olderSources} tasks still reference a replaced
                    manual. Check them against the replacement before updating
                    their instructions.
                  </Text>
                )}
                {openQuestions.length > 0 && (
                  <Text mt={3} color="orange.800">
                    {openQuestions.length} open questions affect this schedule.
                    Resolve them below before approval.
                  </Text>
                )}
                {canEdit && (
                  <Text mt={3}>
                    1. Check the manual. 2. Add or correct service tasks. 3.
                    Save, check and make available.
                  </Text>
                )}
                <Box as="details" mt={3}>
                  <Box as="summary">Choose a Different Saved Version</Box>
                  <AdminSelect
                    mt={2}
                    disabled={locked}
                    value={schedule?.id || ""}
                    onChange={(event) => {
                      if (!canLeaveEdits()) return;
                      const next =
                        schedules.find(
                          (row) => row.id === event.target.value,
                        ) || null;
                      setSchedule(next);
                      createId.current = '';
                      setEntries(next?.entries || []);
                      setAdminNote(next?.admin_note || "");
                      setPdfId(next?.work_context?.document_id || "");
                      setPage(next?.work_context?.page || 1);
                      setContextDirty(false);
                      setDirty(false);
                      setReviewed(false);
                      setNotice("");
                    }}
                  >
                    <option value="">Start a new blank draft</option>
                    {schedules.map((row) => (
                      <option key={row.id} value={row.id}>
                        Version {row.revision} · {scheduleStatus(row.status)}
                      </option>
                    ))}
                  </AdminSelect>
                </Box>
              </Box>
              {preview ? (
                <SchedulePreview
                  schedule={schedule}
                  entries={entries}
                  items={items}
                  documents={documents}
                />
              ) : (
                <Grid
                  templateColumns={{
                    base: "1fr",
                    xl: "minmax(0, .9fr) minmax(0, 1.1fr)",
                  }}
                  gap={5}
                  alignItems="start"
                >
                  <Box
                    bg="white"
                    id="schedule-source"
                    scrollMarginTop="20px"
                    p={5}
                    borderRadius="12px"
                    position={{ xl: "sticky" }}
                    top={{ xl: "16px" }}
                  >
                    <Heading size="lg" mb={4}>
                      1. Check the Manual
                    </Heading>
                    <Stack gap={4}>
                      <FormField label="Manufacturer reference">
                        <AdminSelect
                          value={pdfId}
                          disabled={locked}
                          onChange={(event) => {
                            if (
                              assistanceDirty &&
                              !window.confirm(
                                "Discard unsaved table review changes?",
                              )
                            )
                              return;
                            viewSource(event.target.value);
                          }}
                        >
                          <option value="">
                            Choose a manual or service booklet
                          </option>
                          {sources.map((document) => (
                            <option key={document.id} value={document.id}>
                              {document.name}
                              {document.superseded_by_id
                                ? " (previous version)"
                                : document.replacement_for_id
                                  ? " (updated version)"
                                  : ""}
                            </option>
                          ))}
                        </AdminSelect>
                      </FormField>
                      {!sources.length && (
                        <>
                          <Text>
                            No reference document is linked to this vehicle yet.
                            Add one and confirm its vehicle coverage, then
                            return here.
                          </Text>
                          <Button asChild variant="outline">
                            <NextLink
                              href={`/admin/kb?add=1&vehicle=${vehicleId}`}
                            >
                              Add a reference document
                            </NextLink>
                          </Button>
                        </>
                      )}
                      {selectedSource?.source_type === "pdf" && (
                        <FormField label="Page in the manual">
                          <Input
                            type="number"
                            min={1}
                            value={page}
                            onChange={(event) =>
                              viewSource(
                                pdfId,
                                Math.max(1, Number(event.target.value) || 1),
                              )
                            }
                          />
                        </FormField>
                      )}
                      {selectedSource && (
                        <>
                          {sourceNotice && <Box role="status" bg="blueSurface" color="blueInk" borderRadius="14px" p={3}>
                            <Text fontSize="sm">{sourceNotice}</Text>
                          </Box>}
                          <Button asChild variant="outline">
                            <a
                              href={`${sourceUrl(pdfId, selectedSource.source_revision)}${selectedSource.source_type === "pdf" ? `#page=${page}` : ""}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Open original in a new tab
                            </a>
                          </Button>
                          <Box
                            asChild
                            w="100%"
                            h={{ base: "360px", xl: "600px" }}
                          >
                            <iframe
                              title="Original manufacturer reference"
                              src={`${sourceUrl(pdfId, selectedSource.source_revision)}${selectedSource.source_type === "pdf" ? `#page=${page}` : ""}`}
                            />
                          </Box>
                        </>
                      )}
                    </Stack>
                  </Box>
                  <Stack gap={4} minW={0}>
                    <Heading size="lg">2. Service Tasks and Intervals</Heading>
                    {selectedSource && !selectedSource.superseded_by_id && (
                      <Box as="details" bg="white" p={4} borderRadius="10px">
                        <Box as="summary">
                          Draft a Schedule From This Manual
                        </Box>
                        <Text mt={2} mb={4} color="muted">
                          Select a maintenance table to draft tasks and timing with AI,
                          then review the source evidence before adding rows to your schedule.
                        </Text>
                        <MaintenanceAssistance
                          key={`${vehicleId}:${selectedSource.id}:${selectedSource.source_revision}`}
                          document={selectedSource}
                          items={items}
                          disabled={locked || !canEdit}
                          onDirty={setAssistanceDirty}
                          onItem={(item) =>
                            setItems((previous) => [
                              ...previous.filter((row) => row.id !== item.id),
                              item,
                            ])
                          }
                          onNavigate={(nextPage, tableTitle, automatic) => {
                            if (automatic && !autoTablePending.current) return;
                            viewSource(pdfId, nextPage);
                            if (tableTitle) setSourceNotice(
                              'Automatically opened PDF page ' + nextPage + ' for "' + tableTitle + '". Check this detected table against the original before using its instructions.'
                            );
                          }}
                          vehicleId={vehicleId}
                          scheduleId={schedule?.id}
                          existingItemIds={entries.map((entry) => entry.itemId)}
                          currentPage={page}
                          autoOpenTable={autoTablePending.current}
                          onImport={importSuggestions}
                        />
                      </Box>
                    )}
                    {entries.length > 1 && (
                      <Box as="details" bg="white" p={4} borderRadius="10px">
                        <Box as="summary">
                          Set the Same Interval for Several Tasks
                        </Box>
                        <FrequencyTools
                          key={`${vehicleId}:${schedule?.id || "new"}`}
                          entries={entries}
                          schedules={schedules}
                          items={items}
                          disabled={locked || !canEdit}
                          onChange={(next) => {
                            setEntries(next);
                            setDirty(true);
                            setReviewed(false);
                          }}
                        />
                      </Box>
                    )}
                    {entries.map((entry, index) => (
                      <ServiceTaskEditor
                        key={`${vehicleId}:${schedule?.id || "new"}:${index}`}
                        entry={entry}
                        index={index}
                        items={items}
                        sources={sources}
                        disabled={locked || !canEdit}
                        onChange={(next) => changeEntry(index, next)}
                        onClarify={() => {
                          const source = sources.find(
                            (source) =>
                              source.id === entry.rule.sourceDocumentId,
                          );
                          if (!source) return;
                          setQuestionContext({
                            document_id: source.id,
                            source_revision: source.source_revision,
                            source_type: source.source_type,
                            vehicle_id: vehicleId,
                            schedule_id: schedule?.id || null,
                            item_id: entry.itemId,
                            source_page: entry.rule.sourcePage,
                            title: (
                              items.find((item) => item.id === entry.itemId)
                                ?.title || "Service task to check"
                            ).slice(0, 300),
                            excerpt: [
                              serviceInstruction(entry),
                              entry.rule.conditions,
                            ]
                              .filter(Boolean)
                              .join("\n")
                              .slice(0, 2000),
                          });
                        }}
                        onRemove={() => {
                          setEntries(entries.filter((_, i) => i !== index));
                          setDirty(true);
                          setReviewed(false);
                        }}
                        onSource={(documentId, sourcePage) => {
                          if (
                            assistanceDirty &&
                            !window.confirm(
                              "Discard unsaved table review changes?",
                            )
                          )
                            return;
                          viewSource(
                            documentId || entry.rule.sourceDocumentId || "",
                            sourcePage || entry.rule.sourcePage || 1,
                          );
                          document
                            .getElementById("schedule-source")
                            ?.scrollIntoView({ block: "start" });
                        }}
                      />
                    ))}
                    {!entries.length && (
                      <Box bg="white" p={5} borderRadius="10px">
                        <Text>
                          No service tasks yet. Add a task, then copy its
                          interval and conditions from the manual.
                        </Text>
                      </Box>
                    )}
                    <Flex gap={3} wrap="wrap">
                      <Button
                        variant="outline"
                        disabled={locked || !canEdit}
                        onClick={() => {
                          const entry = newEntry();
                          if (selectedSource) {
                            entry.rule.sourceDocumentId = selectedSource.id;
                            entry.rule.sourceRevision =
                              selectedSource.source_revision;
                            entry.rule.sourcePage =
                              selectedSource.source_type === "pdf"
                                ? page
                                : null;
                          }
                          setEntries([...entries, entry]);
                          setDirty(true);
                          setReviewed(false);
                        }}
                      >
                        Add service task
                      </Button>
                      <Button
                        variant="plain"
                        disabled={locked || !canEdit}
                        onClick={() => setCreatingItem(true)}
                      >
                        Task missing from the list?
                      </Button>
                    </Flex>
                  </Stack>
                </Grid>
              )}
              <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
                <Heading size="lg" mb={3}>
                  3. Save and Check Your Work
                </Heading>
                {canEdit ? (
                  <Stack gap={4}>
                    <PublicationChecklist steps={[
                      { label: "Latest draft saved", complete: Boolean(schedule) && !dirty && !assistanceDirty, description: dirty || assistanceDirty ? "Save your changes before the final review." : undefined },
                      { label: "Service tasks and references complete", complete: entries.length > 0 && progress.incomplete === 0, description: entries.length ? String(progress.incomplete) + " tasks need details. See the issue links below." : "Add at least one service task." },
                      { label: "Clarification questions resolved", complete: openQuestions.length === 0, href: "#questions" },
                      { label: "Manufacturer source reviewed", complete: reviewed, description: "Confirm the source review below after saving the draft." },
                    ]} />
                    {publishedSchedule && <ScheduleChanges published={publishedSchedule} entries={entries} items={items} />}
                    <Text>
                      Save a draft if you need to stop or ask someone about an
                      unclear requirement. Keep the schedule as a draft until
                      every instruction has been checked.
                    </Text>
                    <FormField
                      label="Where should you pick up next time? (private note)"
                      hint="This note appears on Home with the saved draft and is never shown to drivers."
                    >
                      <Textarea
                        disabled={locked}
                        maxLength={4000}
                        value={adminNote}
                        onChange={(event) => {
                          setAdminNote(event.target.value);
                          setDirty(true);
                        }}
                        placeholder="For example: Confirm the brake-fluid symbol on page 42 before approving."
                      />
                    </FormField>
                    <Text fontSize="sm" color="muted">
                      Saving also remembers the manual and page you are viewing.
                    </Text>
                    <Flex gap={3} wrap="wrap">
                      <Button
                        disabled={
                          locked ||
                          assistanceDirty ||
                          (!dirty && Boolean(schedule))
                        }
                        loading={busy}
                        onClick={saveDraft}
                      >
                        Save draft
                      </Button>
                      <Button
                        variant="plain"
                        disabled={
                          !schedule || dirty || assistanceDirty || locked
                        }
                        onClick={() => checkOrPublish(false)}
                      >
                        Check for missing details (optional)
                      </Button>
                    </Flex>
                    <Text fontSize="sm" color="muted">
                      The optional check looks for missing or invalid details. Publishing runs validation again; you still need to check the source manual.
                    </Text>
                    {assistanceDirty && (
                      <Text color="muted">
                        Save the task or table edits in “Help me find service
                        tasks” first. Then save the schedule draft.
                      </Text>
                    )}
                    {dirty && (
                      <Text color="muted">
                        You have unsaved changes. Save the draft before the
                        final check.
                      </Text>
                    )}
                    {progress.incomplete > 0 && (
                      <Box color="orange.800">
                        <Text>Complete these details before publishing, then save the draft:</Text>
                        {entries.map((entry, index) => {
                          const issues = scheduleEntryIssues(entry, documents);
                          if (!issues.length) return null;
                          const title = items.find((item) => item.id === entry.itemId)?.title || "New service task";
                          return (
                            <Text key={index} mt={2}>
                              <a href={`#schedule-task-${index + 1}`} onClick={() => setPreview(false)}>
                                Task {index + 1} ({title}): {issues.join(" ")}
                              </a>
                            </Text>
                          );
                        })}
                      </Box>
                    )}
                    {!entries.length && <Text>Add at least one service task before publishing.</Text>}
                    {error && <Text role="alert">{error}</Text>}
                    <Checkbox
                      checked={reviewed}
                      disabled={
                        !schedule ||
                        dirty ||
                        assistanceDirty ||
                        locked ||
                        !entries.length ||
                        progress.incomplete > 0 ||
                        openQuestions.length > 0
                      }
                      onCheckedChange={(event) =>
                        setReviewed(event.checked === true)
                      }
                    >
                      I checked every service task, interval and condition
                      against the original manufacturer reference.
                    </Checkbox>
                    <Button
                      alignSelf="start"
                      disabled={
                        !schedule ||
                        dirty ||
                        assistanceDirty ||
                        locked ||
                        !reviewed ||
                        !entries.length ||
                        progress.incomplete > 0 ||
                        openQuestions.length > 0
                      }
                      onClick={() => {
                        if (
                          window.confirm(
                            "Make this checked schedule available to drivers? It will replace the current schedule for this vehicle.",
                          )
                        )
                          checkOrPublish(true);
                      }}
                    >
                      Publish schedule
                    </Button>
                  </Stack>
                ) : (
                  <Text>
                    This saved version is read-only. Choose “Update this
                    schedule” above to make changes in a new draft.
                  </Text>
                )}
                {schedule && schedule.status !== "superseded" && (
                  <Box as="details" mt={5}>
                    <Box as="summary">
                      {schedule.status === "draft"
                        ? "Discard This Draft"
                        : "Unpublish This Schedule"}
                    </Box>
                    <Button
                      mt={3}
                      variant="outline"
                      colorPalette="red"
                      disabled={dirty || assistanceDirty || locked}
                      onClick={retire}
                    >
                      {schedule.status === "draft"
                        ? "Delete draft"
                        : "Unpublish schedule"}
                    </Button>
                  </Box>
                )}
              </Box>
              <ReviewQuestions
                vehicleId={vehicleId}
                onSource={(question) => {
                  if (
                    assistanceDirty &&
                    !window.confirm(
                      "Discard unsaved table edits to check this source?",
                    )
                  )
                    return;
                  viewSource(question.document_id, question.source_page || 1);
                  setPreview(false);
                  requestAnimationFrame(() =>
                    document
                      .getElementById("schedule-source")
                      ?.scrollIntoView({ block: "start" }),
                  );
                }}
              />
            </>
          )
        )}
      </Stack>
      {questionContext && (
        <QuestionDialog
          context={questionContext}
          onClose={() => setQuestionContext(null)}
          onSaved={() => {
            setReviewed(false);
            setNotice(
              "Question saved. It will be waiting here and on Home when you return.",
            );
          }}
        />
      )}
      {creatingItem && (
        <MaintenanceItemEditor
          categories={[
            ...new Set(items.map((item) => item.category).filter(Boolean)),
          ]}
          onClose={() => setCreatingItem(false)}
          onSaved={(item) => {
            setItems((previous) => [...previous, item]);
            setCreatingItem(false);
            const entry = newEntry();
            entry.itemId = item.id;
            entry.action = item.action;
            if (selectedSource) {
              entry.rule.sourceDocumentId = selectedSource.id;
              entry.rule.sourceRevision = selectedSource.source_revision;
              entry.rule.sourcePage =
                selectedSource.source_type === "pdf" ? page : null;
            }
            setEntries((previous) => [...previous, entry]);
            setDirty(true);
            setReviewed(false);
          }}
        />
      )}
    </AdminLayout>
  );
}
