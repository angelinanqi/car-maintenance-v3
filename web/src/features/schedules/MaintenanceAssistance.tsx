"use client";

import TableEvidence from "./TableEvidence";
import TaskCheck from "./TaskCheck";
import { useEffect, useRef, useState } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { AdminSelect } from "@/components/admin/NativeControls";
import FormField from "@/components/admin/FormField";
import { useContent } from "@/components/ContentProvider";
import { QuestionDialog, type QuestionContext } from "@/components/admin/ReviewQuestions";
import { columnExamples, suggestedNameColumns } from "@/lib/adminJourney.mjs";
import type { MaintenanceItem, SourceDocument } from "@/api/admin";
import {
  loadReview,
  updateReview,
  type Review,
  type Selection,
  type Suggestion,
  type DetectedTable,
} from "@/api/maintenanceAssistance";

export default function MaintenanceAssistance({
  document,
  vehicleId,
  scheduleId,
  existingItemIds = [],
  currentPage = 1,
  items,
  onItem,
  onNavigate,
  onImport,
  disabled,
  onDirty,
}: {
  document: SourceDocument;
  vehicleId: string;
  scheduleId?: string;
  existingItemIds?: (string | null)[];
  currentPage?: number;
  items: MaintenanceItem[];
  onItem: (item: MaintenanceItem) => void;
  onNavigate: (page: number) => void;
  onImport: (review: Review, suggestions: Suggestion[]) => void;
  disabled: boolean;
  onDirty: (dirty: boolean) => void;
}) {
  const { reviewQuestions } = useContent();
  const [review, setReview] = useState<Review | null>(null);
  const [step, setStep] = useState(0);
  const [tableId, setTableId] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [selectionBaseline, setSelectionBaseline] = useState<Selection | null>(
    null,
  );
  const [search, setSearch] = useState("");
  const [showOtherTables, setShowOtherTables] = useState(false);
  const [taskFilter, setTaskFilter] = useState("suggested");
  const [taskIndex, setTaskIndex] = useState(0);
  const [taskDirty, setTaskDirty] = useState(false);
  const [manualName, setManualName] = useState("");
  const [manualLocation, setManualLocation] = useState("");
  const [asking, setAsking] = useState<QuestionContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [attempt, setAttempt] = useState(0);
  const alive = useRef(false);
  const activeRequest = useRef(false);
  const selectionDirty =
    JSON.stringify(selection) !== JSON.stringify(selectionBaseline);
  const dirty = selectionDirty || taskDirty || !!manualName || !!manualLocation;
  const locked = disabled || busy || loading;
  const activeTable = review?.catalogue.tables.find(
    (table) => table.table_id === tableId,
  );
  const accepted =
    review?.suggestions.filter(
      (task) => task.status === "accepted" && task.mapped_item_id,
    ) || [];
  const blockedItems = reviewQuestions
    .filter(
      (question) =>
        question.document_id === document.id &&
        (!question.vehicle_id || question.vehicle_id === vehicleId),
    )
    .map((question) => question.item_id);
  const additions = accepted.filter(
    (task) =>
      !existingItemIds.includes(task.mapped_item_id) &&
      !blockedItems.includes(null) &&
      !blockedItems.includes(task.mapped_item_id),
  );
  const tasks =
    review?.suggestions.filter(
      (task) => taskFilter === "all" || task.status === taskFilter,
    ) || [];
  const activeTask = tasks[Math.min(taskIndex, Math.max(0, tasks.length - 1))];

  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    loadReview(document.id, document.source_revision, controller.signal)
      .then((next) => {
        if (!alive.current) return;
        setReview(next);
        const table =
          next.catalogue.tables.find(
            (table) => table.table_id === next.selections[0]?.table_id,
          ) || next.catalogue.tables[0];
        setTableId(table?.table_id || "");
        const initial = table
          ? next.selections.find(
              (choice) => choice.table_id === table.table_id,
            ) || {
              table_id: table.table_id,
              confirmed: true as const,
              columns: suggestedNameColumns(table),
              excluded_rows: [],
            }
          : null;
        setSelection(initial);
        setSelectionBaseline(initial);
        setStep(
          next.suggestions.length
            ? next.suggestions.some((task) => task.status === "suggested")
              ? 1
              : 2
            : 0,
        );
        setTaskDirty(false);
        setManualName("");
        setManualLocation("");
        setTaskIndex(0);
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(cause.message);
      })
      .finally(() => {
        if (alive.current) setLoading(false);
      });
    return () => {
      alive.current = false;
      controller.abort();
      onDirty(false);
    };
  }, [document.id, document.source_revision, onDirty, attempt]);

  async function run(
    action: (state: Review) => Promise<Review>,
    success: string,
    nextStep?: number,
  ) {
    if (!review || activeRequest.current || disabled) return false;
    activeRequest.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await action(review);
      if (!alive.current) return false;
      setReview(next);
      setTaskDirty(false);
      const saved = next.selections.find(
        (choice) => choice.table_id === tableId,
      );
      if (saved) {
        setSelection(saved);
        setSelectionBaseline(saved);
      }
      setNotice(success);
      if (nextStep !== undefined) setStep(nextStep);
      return true;
    } catch (cause) {
      if (alive.current) {
        setError((cause as Error).message);
        // A first request may have saved before a later request failed. Refresh
        // the version without throwing away the admin's unsaved field values.
        try {
          setReview(await loadReview(document.id, document.source_revision));
        } catch {}
      }
      return false;
    } finally {
      activeRequest.current = false;
      if (alive.current) setBusy(false);
    }
  }
  function chooseTable(table: DetectedTable) {
    if (
      dirty &&
      !window.confirm(
        "Discard unsaved table or task edits? Saved checks will be kept.",
      )
    )
      return;
    setTableId(table.table_id);
    const initial = review?.selections.find(
      (choice) => choice.table_id === table.table_id,
    ) || {
      table_id: table.table_id,
      confirmed: true as const,
      columns: suggestedNameColumns(table),
      excluded_rows: [],
    };
    setSelection(initial);
    setSelectionBaseline(initial);
    setTaskDirty(false);
    setManualName("");
    setManualLocation("");
    setNotice("");
  }
  function moveStep(next: number) {
    if (
      dirty &&
      !window.confirm(
        "Discard unsaved table or task edits? Saved checks will be kept.",
      )
    )
      return;
    setSelection(selectionBaseline);
    setTaskDirty(false);
    setManualName("");
    setManualLocation("");
    setStep(next);
  }
  const likelyTables =
    review?.catalogue.tables.filter(
      (table) => table.ranking.classification !== "other",
    ) || [];
  const visibleTables = (
    showOtherTables || !likelyTables.length
      ? review?.catalogue.tables || []
      : likelyTables
  ).filter((table) =>
    [table.title, ...table.source.cells.map((cell) => cell.text)]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase()),
  );

  return (
    <Box borderWidth="1px" borderRadius="10px" p={4}>
      <Stack gap={4}>
        <Heading size="md">Find service tasks in this manual</Heading>
        <Text fontSize="sm" color="muted">
          Work through the table and check the task names. The service intervals
          still need to be entered and checked against the manual.
        </Text>
        <Flex as="ol" gap={2} listStyleType="none" p={0} m={0} wrap="wrap">
          {["Choose the table", "Check the tasks", "Add to schedule"].map(
            (label, index) => (
              <Box as="li" key={label}>
                <Button
                  size="sm"
                  variant={step === index ? "solid" : "outline"}
                  aria-current={step === index ? "step" : undefined}
                  disabled={
                    locked || (index > 0 && !review?.suggestions.length)
                  }
                  onClick={() => moveStep(index)}
                >
                  {index + 1}. {label}
                </Button>
              </Box>
            ),
          )}
        </Flex>
        {loading && <Text role="status">Opening saved table checks…</Text>}
        {error && <Text role="alert">{error}</Text>}
        {notice && <Text role="status">{notice}</Text>}
        {!loading && error && (
          <Button
            variant="outline"
            onClick={() => {
              if (!dirty || window.confirm("Reload and discard unsaved edits?"))
                setAttempt((value) => value + 1);
            }}
          >
            Reload saved checks
          </Button>
        )}
        {review && step === 0 && (
          <>
            <Heading size="sm">Which table lists the service tasks?</Heading>
            <Text fontSize="sm">
              Check the table against the original. Tables most likely to
              contain a service schedule are shown first.
            </Text>
            <Input
              aria-label="Find a service table"
              placeholder="Search by a heading or task name"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Stack gap={2} maxH="240px" overflowY="auto">
              {visibleTables.map((table, index) => (
                <Button
                  key={table.table_id}
                  variant={tableId === table.table_id ? "solid" : "outline"}
                  disabled={locked}
                  justifyContent="start"
                  aria-pressed={tableId === table.table_id}
                  onClick={() => chooseTable(table)}
                >
                  {table.title ||
                    (table.pages.length
                      ? `Service table on page ${table.pages.join(", ")}`
                      : `Table ${index + 1}`)}
                  {table.title && table.pages.length
                    ? ` · page ${table.pages.join(", ")}`
                    : ""}
                </Button>
              ))}
            </Stack>
            {!visibleTables.length && (
              <Text>
                No matching tables. Try another search or enter a task from a
                known page below.
              </Text>
            )}
            {review.catalogue.tables.length > likelyTables.length && (
              <Button
                variant="plain"
                size="sm"
                alignSelf="start"
                onClick={() => setShowOtherTables((value) => !value)}
              >
                {showOtherTables
                  ? "Show likely service tables"
                  : "Look through all tables"}
              </Button>
            )}
            {activeTable && selection && (
              <>
                <Flex gap={2} wrap="wrap">
                  {activeTable.pages.map((page) => (
                    <Button
                      key={page}
                      variant="outline"
                      size="sm"
                      onClick={() => onNavigate(page)}
                    >
                      Check original page {page}
                    </Button>
                  ))}
                </Flex>
                <Heading size="sm">Where are the task names?</Heading>
                <Text fontSize="sm">
                  Choose the column containing names such as engine oil or brake
                  fluid. The examples below come from this table.
                </Text>
                <Stack gap={3}>
                  {[
                    ...new Set(
                      activeTable.source.cells.map((cell) => cell.column),
                    ),
                  ]
                    .sort((a, b) => a - b)
                    .map((column) => {
                      const header = activeTable.source.cells.find(
                        (cell) => cell.column === column && cell.header,
                      )?.text;
                      const examples = columnExamples(activeTable, column);
                      return (
                        <Box
                          key={column}
                          bg={
                            selection.columns.includes(column)
                              ? "brand.50"
                              : "canvas"
                          }
                          borderRadius="8px"
                          p={3}
                        >
                          <Checkbox
                            disabled={locked}
                            checked={selection.columns.includes(column)}
                            onCheckedChange={(event) =>
                              setSelection({
                                ...selection,
                                columns:
                                  event.checked === true
                                    ? [...selection.columns, column].sort(
                                        (a, b) => a - b,
                                      )
                                    : selection.columns.filter(
                                        (value) => value !== column,
                                      ),
                              })
                            }
                          >
                            <Text fontWeight="600">
                              {header || `Names in this column (${column + 1})`}
                            </Text>
                            <Text fontSize="sm" color="muted">
                              {examples.join(" · ") ||
                                "No readable examples. Check the original before choosing."}
                            </Text>
                          </Checkbox>
                        </Box>
                      );
                    })}
                </Stack>
                <Box as="details">
                  <Box as="summary">
                    Check the full table or skip heading and note rows
                  </Box>
                  <TableEvidence
                    table={activeTable}
                    selection={selection}
                    disabled={locked}
                    onExclude={(row) =>
                      setSelection({
                        ...selection,
                        excluded_rows: selection.excluded_rows.includes(row)
                          ? selection.excluded_rows.filter(
                              (value) => value !== row,
                            )
                          : [...selection.excluded_rows, row].sort(
                              (a, b) => a - b,
                            ),
                      })
                    }
                  />
                </Box>
                {activeTable.uncertainty.length > 0 && (
                  <Text fontSize="sm" color="orange.800">
                    Some table details need checking. Confirm the task names,
                    merged cells, notes and page against the original.
                  </Text>
                )}
                {[
                  ...(activeTable.source.context || []),
                  ...(activeTable.source.notes || []),
                ].map((note, index) => (
                  <Text key={index} fontSize="sm" whiteSpace="pre-wrap">
                    {note}
                  </Text>
                ))}
                <Button
                  disabled={locked || !selection.columns.length}
                  onClick={() =>
                    run(
                      async (state) => {
                        const choices = [
                          ...state.selections.filter(
                            (choice) => choice.table_id !== selection.table_id,
                          ),
                          selection,
                        ].sort((a, b) => a.table_id.localeCompare(b.table_id));
                        const saved = await updateReview(
                          state,
                          "/confirmation",
                          "PUT",
                          { tables: choices },
                        );
                        const next = await updateReview(
                          saved,
                          "/suggestions",
                          "POST",
                        );
                        setTaskFilter("suggested");
                        setTaskIndex(0);
                        return next;
                      },
                      "Table choices saved. Check each suggested task below.",
                      1,
                    )
                  }
                >
                  Find tasks from these names
                </Button>
              </>
            )}
            <Box as="details" borderTopWidth="1px" pt={3}>
              <Box as="summary">
                Can’t find the table? Enter a task from the manual
              </Box>
              <Stack gap={3} mt={3}>
                <Text fontSize="sm">
                  Copy a task name and record its page or section. You will
                  check the matching task next.
                </Text>
                <FormField label="Task name as written in the manual">
                  <Input
                    disabled={locked}
                    maxLength={500}
                    value={manualName}
                    onChange={(event) => setManualName(event.target.value)}
                  />
                </FormField>
                <FormField
                  label={
                    document.source_type === "pdf"
                      ? "Page in the manual"
                      : "Section heading"
                  }
                >
                  <Input
                    disabled={locked}
                    type={document.source_type === "pdf" ? "number" : "text"}
                    min={1}
                    value={manualLocation}
                    placeholder={
                      document.source_type === "pdf"
                        ? String(currentPage)
                        : "e.g. Periodic maintenance"
                    }
                    onChange={(event) => setManualLocation(event.target.value)}
                  />
                </FormField>
                <Button
                  variant="outline"
                  disabled={
                    locked || !manualName.trim() || !manualLocation.trim()
                  }
                  onClick={() =>
                    run(
                      async (state) => {
                        const saved = await updateReview(
                          state,
                          "/bookmarks",
                          "POST",
                          {
                            title: manualName.trim(),
                            ...(document.source_type === "pdf"
                              ? { page: Number(manualLocation) }
                              : { section: manualLocation.trim() }),
                          },
                        );
                        const bookmark =
                          saved.bookmarks[saved.bookmarks.length - 1];
                        const next = await updateReview(
                          saved,
                          "/manual-items",
                          "POST",
                          {
                            table_id: bookmark.table_id,
                            name: manualName.trim(),
                          },
                        );
                        setManualName("");
                        setManualLocation("");
                        setTaskFilter("suggested");
                        setTaskIndex(0);
                        return next;
                      },
                      "Task and reference saved. Check the matching task next.",
                      1,
                    )
                  }
                >
                  Save task and check it
                </Button>
              </Stack>
            </Box>
          </>
        )}
        {review && step === 1 && (
          <>
            <Text>
              {
                review.suggestions.filter((task) => task.status === "suggested")
                  .length
              }{" "}
              awaiting a check · {accepted.length} accepted
            </Text>
            <FormField label="Show tasks">
              <AdminSelect
                disabled={taskDirty || locked}
                value={taskFilter}
                onChange={(event) => {
                  setTaskFilter(event.target.value);
                  setTaskIndex(0);
                }}
              >
                <option value="suggested">Still to check</option>
                <option value="accepted">Accepted tasks</option>
                <option value="rejected">Skipped tasks</option>
                <option value="all">All tasks</option>
              </AdminSelect>
            </FormField>
            {activeTask ? (
              <>
                <TaskCheck
                  key={activeTask.suggestion_id}
                  suggestion={activeTask}
                  items={items}
                  blockedItems={blockedItems}
                  disabled={locked}
                  onDirty={setTaskDirty}
                  onItem={onItem}
                  onNavigate={onNavigate}
                  onSave={async (body) => {
                    const saved = await run(
                      (state) =>
                        updateReview(
                          state,
                          `/suggestions/${encodeURIComponent(activeTask.suggestion_id)}`,
                          "PATCH",
                          body,
                        ),
                      body.status === "accepted"
                        ? "Task accepted. Its interval still needs checking in the schedule."
                        : "Task check saved.",
                    );
                    if (saved && taskFilter === "all")
                      setTaskIndex((value) =>
                        Math.min(value + 1, tasks.length - 1),
                      );
                  }}
                  onAsk={(task) =>
                    setAsking({
                      document_id: document.id,
                      source_revision: document.source_revision,
                      source_type: document.source_type,
                      vehicle_id: vehicleId,
                      schedule_id: scheduleId || null,
                      item_id: task.mapped_item_id,
                      title: (task.edited_name || task.suggested_name).slice(
                        0,
                        300,
                      ),
                      excerpt: (task.original_text || "").slice(0, 2000),
                      source_page:
                        task.pages?.[0] ||
                        review.catalogue.tables.find(
                          (table) => table.table_id === task.table_id,
                        )?.pages[0] ||
                        null,
                    })
                  }
                />
                <Flex justify="space-between" gap={3}>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={locked || taskDirty || taskIndex === 0}
                    onClick={() =>
                      setTaskIndex((value) => Math.max(0, value - 1))
                    }
                  >
                    Previous task
                  </Button>
                  <Text fontSize="sm">
                    {Math.min(taskIndex + 1, tasks.length)} of {tasks.length}
                  </Text>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={
                      locked || taskDirty || taskIndex >= tasks.length - 1
                    }
                    onClick={() => setTaskIndex((value) => value + 1)}
                  >
                    Next task
                  </Button>
                </Flex>
              </>
            ) : (
              <Text>
                {taskFilter === "suggested"
                  ? "No more tasks are waiting in this view. Review the accepted tasks before adding them."
                  : "No tasks in this view."}
              </Text>
            )}
            <Button
              disabled={locked || taskDirty || !accepted.length}
              onClick={() => moveStep(2)}
            >
              Review accepted tasks
            </Button>
          </>
        )}
        {review && step === 2 && (
          <>
            <Heading size="sm">Ready to add to your draft</Heading>
            <Text>
              These task names have been checked. You will still enter the
              interval and any driving conditions from the manual.
            </Text>
            <Stack gap={2}>
              {accepted.map((task) => (
                <Flex key={task.suggestion_id} gap={3} justify="space-between">
                  <Text>
                    {items.find((item) => item.id === task.mapped_item_id)
                      ?.title ||
                      task.edited_name ||
                      task.suggested_name}
                  </Text>
                  <Badge>
                    {blockedItems.includes(null) ||
                    blockedItems.includes(task.mapped_item_id)
                      ? "Needs clarification"
                      : existingItemIds.includes(task.mapped_item_id)
                        ? "Already in draft"
                        : "Ready to add"}
                  </Badge>
                </Flex>
              ))}
            </Stack>
            {!accepted.length && (
              <Text>No accepted tasks yet. Return to “Check the tasks”.</Text>
            )}
            <Button
              disabled={locked || dirty || !additions.length}
              onClick={() => {
                onImport(review, additions);
                setNotice(
                  "Tasks added to the draft below. Enter their intervals, then save the schedule.",
                );
              }}
            >
              Add {additions.length} {additions.length === 1 ? "task" : "tasks"}{" "}
              to draft
            </Button>
            <Button
              variant="outline"
              disabled={locked || dirty}
              onClick={() => moveStep(0)}
            >
              Find tasks in another table
            </Button>
          </>
        )}
      </Stack>
      {asking && (
        <QuestionDialog
          context={asking}
          onClose={() => setAsking(null)}
          onSaved={() => {
            setNotice(
              "Question saved. This task still needs checking before it can be accepted.",
            );
            setTaskIndex((value) => Math.min(value + 1, tasks.length - 1));
          }}
        />
      )}
    </Box>
  );
}
