"use client";

import { Checkbox } from "@/components/ui/checkbox";

import { AdminSelect } from "@/components/admin/NativeControls";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Fieldset,
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import FormField from "@/components/admin/FormField";
import useUnsavedChanges from "@/components/admin/useUnsavedChanges";
import { request, listAll } from "@/api/client.mjs";
import { originalDocumentUrl } from "@/api/documents.mjs";
import {
  loadCatalogue,
  loadItems,
  loadSchedules,
  saveSchedule,
  validateSchedule,
  publishSchedule,
  withdrawSchedule,
  deleteDraftSchedule,
  type Vehicle,
  type MaintenanceItem,
  type Schedule,
  type ScheduleEntry,
  type SourceDocument,
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

export default function SchedulesPage() {
  return (
    <Suspense fallback={<Text p={8}>Loading schedules…</Text>}>
      <ScheduleEditor />
    </Suspense>
  );
}

function ScheduleEditor() {
  const search = useSearchParams();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [items, setItems] = useState<MaintenanceItem[]>([]);
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [links, setLinks] = useState<
    { vehicle_id: string; document_id: string }[]
  >([]);
  const [vehicleId, setVehicleId] = useState(search.get("vehicle") || "");
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [dirty, setDirty] = useState(false);
  useUnsavedChanges(dirty);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pdfId, setPdfId] = useState("");
  const [page, setPage] = useState(1);
  const [reviewed, setReviewed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      loadCatalogue(),
      loadItems(),
      listAll("/documents"),
      request("/knowledge/manage"),
    ])
      .then(([catalogue, items, docs, knowledge]) => {
        if (active) {
          setVehicles(catalogue.vehicles);
          setItems(items);
          setDocuments(docs);
          setLinks(knowledge.document_vehicles);
          setLoading(false);
        }
      })
      .catch((e: Error) => {
        if (active) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);
  useEffect(() => {
    if (!vehicleId) return;
    let active = true;
    loadSchedules(vehicleId)
      .then((rows) => {
        if (active) setSchedules(rows);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [vehicleId, reloadKey]);
  const sources = documents.filter(
    (d) =>
      d.source_type === "pdf" &&
      links.some(
        (link) => link.vehicle_id === vehicleId && link.document_id === d.id,
      ),
  );
  const canEdit = !schedule || schedule.status === "draft";
  const changeEntry = (index: number, next: ScheduleEntry) => {
    setEntries(entries.map((entry, i) => (i === index ? next : entry)));
    setDirty(true);
    setReviewed(false);
    setNotice("");
  };
  function chooseSchedule(id: string) {
    if (dirty && !window.confirm("Discard unsaved schedule changes?")) return;
    const row = schedules.find((s) => s.id === id) || null;
    setSchedule(row);
    setEntries(row?.entries || []);
    setDirty(false);
    setReviewed(false);
    setNotice("");
  }
  async function saveDraft() {
    if (busy || !vehicleId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await saveSchedule(schedule?.id || "", vehicleId, entries);
      setSchedule(saved);
      setEntries(saved.entries);
      setDirty(false);
      setReviewed(false);
      setSchedules((previous) => [
        ...previous.filter((row) => row.id !== saved.id),
        saved,
      ]);
      setNotice(
        "Draft saved. Validate the saved configuration, then verify the source before publishing.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function validateOrPublish(publishing: boolean) {
    if (!schedule || dirty || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (publishing) {
        if (!reviewed)
          throw new Error(
            "Confirm that you checked every rule against its source PDF.",
          );
        const saved = await publishSchedule(schedule.id);
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
          "Verified schedule published. The previous published revision is preserved as superseded.",
        );
      } else {
        setNotice((await validateSchedule(schedule.id)).message);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function retireSchedule() {
    if (!schedule || dirty || busy) return;
    const removing = schedule.status === "draft";
    if (
      !window.confirm(
        removing
          ? "Delete this draft revision?"
          : "Withdraw this schedule? Manufacturer reminders from this revision will stop on the next mobile refresh. Service records and personal tasks are kept.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      if (removing) {
        await deleteDraftSchedule(schedule.id);
        setSchedules((previous) =>
          previous.filter((row) => row.id !== schedule.id),
        );
        setSchedule(null);
        setEntries([]);
      } else {
        const saved = await withdrawSchedule(schedule.id);
        setSchedule(saved);
        setSchedules((previous) =>
          previous.map((row) => (row.id === saved.id ? saved : row)),
        );
      }
      setReviewed(false);
      setNotice(
        removing
          ? "Draft deleted."
          : "Schedule withdrawn. Personal tasks and service history are kept.",
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <AdminLayout
      title="Service schedules"
      description="Choose a vehicle, enter rules from its source PDF, then save, validate and review before publishing."
    >
      <Stack gap={5}>
        {error && (
          <Text role="alert" color="red.700">
            {error}
          </Text>
        )}
        {notice && (
          <Text role="status" color="green.700">
            {notice}
          </Text>
        )}
        <Button
          variant="outline"
          alignSelf="start"
          disabled={busy}
          onClick={() => setReloadKey((v) => v + 1)}
        >
          Reload sources and schedules
        </Button>
        {loading && <Text>Loading vehicle and source catalogues…</Text>}
        <FormField label="Vehicle variant">
          <AdminSelect
            disabled={busy || loading}
            value={vehicleId}
            onChange={(e) => {
              if (dirty && !window.confirm("Discard unsaved schedule changes?"))
                return;
              setVehicleId(e.target.value);
              setSchedules([]);
              setSchedule(null);
              setEntries([]);
              setDirty(false);
              setReviewed(false);
              setPdfId("");
              setPage(1);
              setNotice("");
              setError("");
            }}
          >
            <option value="">Select a vehicle</option>
            {vehicles.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} · {row.year} · {row.variant}
              </option>
            ))}
          </AdminSelect>
        </FormField>
        {vehicleId && (
          <>
            <FormField label="Schedule revision">
              <AdminSelect
                disabled={busy}
                value={schedule?.id || ""}
                onChange={(e) => chooseSchedule(e.target.value)}
              >
                <option value="">New draft revision</option>
                {schedules.map((row) => (
                  <option key={row.id} value={row.id}>
                    Revision {row.revision} · {row.status}
                  </option>
                ))}
              </AdminSelect>
            </FormField>
            {schedule && (
              <Text>
                Revision {schedule.revision} · {schedule.status}
                {schedule.verified_at
                  ? ` · Verified ${new Date(schedule.verified_at).toLocaleString("en-GB")}`
                  : ""}
              </Text>
            )}
            {!canEdit && (
              <Button
                alignSelf="start"
                disabled={busy}
                onClick={() => {
                  setSchedule(null);
                  setEntries(structuredClone(entries));
                  setDirty(true);
                  setReviewed(false);
                  setNotice(
                    "Editing a new draft revision. The current published schedule remains active until this revision is published.",
                  );
                }}
              >
                Create draft revision from this schedule
              </Button>
            )}
            <Flex
              gap={5}
              align="start"
              direction={{ base: "column", xl: "row" }}
            >
              <Box
                flex="1"
                w="100%"
                minW={0}
                borderWidth="1px"
                p={4}
                borderRadius="md"
              >
                <Heading size="md" mb={3}>
                  Original source
                </Heading>
                <Stack gap={3}>
                  <FormField label="Associated PDF">
                    <AdminSelect
                      value={pdfId}
                      onChange={(e) => {
                        setPdfId(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">Select original PDF</option>
                      {sources.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} · {d.document_type.replaceAll("_", " ")}
                        </option>
                      ))}
                    </AdminSelect>
                  </FormField>
                  {!sources.length && (
                    <Text>
                      No associated PDF. Upload and associate a maintenance
                      source in Documents.
                    </Text>
                  )}
                  <FormField label="PDF page">
                    <Input
                      type="number"
                      min={1}
                      value={page}
                      onChange={(e) =>
                        setPage(Math.max(1, Number(e.target.value) || 1))
                      }
                    />
                  </FormField>
                  {pdfId && (
                    <>
                      <Button asChild variant="outline">
                        <a
                          href={`${originalDocumentUrl(pdfId)}#page=${page}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Open original PDF at page {page}
                        </a>
                      </Button>
                      <Box asChild w="100%" h="640px">
                        <iframe
                          key={`${pdfId}:${page}`}
                          title="Original maintenance PDF"
                          src={`${originalDocumentUrl(pdfId)}#page=${page}`}
                        />
                      </Box>
                    </>
                  )}
                </Stack>
              </Box>
              <Box flex="1" w="100%" minW={0}>
                <Fieldset.Root disabled={busy}>
                  <Stack gap={4}>
                    {entries.map((entry, index) => (
                      <Box
                        key={`${vehicleId}:${schedule?.id || "new"}:${index}:${entry.itemId || "blank"}`}
                        borderWidth="1px"
                        borderRadius="md"
                        p={4}
                      >
                        <Fieldset.Root disabled={!canEdit}>
                          <Stack gap={3}>
                            <Heading size="sm">Rule {index + 1}</Heading>
                            <FormField label="Standard maintenance item">
                              <AdminSelect
                                value={entry.itemId || ""}
                                onChange={(e) => {
                                  const item = items.find(
                                    (r) => r.id === e.target.value,
                                  );
                                  changeEntry(index, {
                                    ...entry,
                                    itemId: item?.id || null,
                                    action: item?.action || "replace",
                                  });
                                }}
                              >
                                <option value="">Select standard item</option>
                                {items
                                  .filter(
                                    (r) => r.active || r.id === entry.itemId,
                                  )
                                  .map((r) => (
                                    <option key={r.id} value={r.id}>
                                      {r.title} ({r.action})
                                    </option>
                                  ))}
                              </AdminSelect>
                            </FormField>
                            <Text fontSize="sm">Action: {entry.action}</Text>
                            <FormField label="Rule structure">
                              <AdminSelect
                                value={entry.rule.type}
                                onChange={(e) =>
                                  changeEntry(index, {
                                    ...entry,
                                    rule: {
                                      ...newEntry().rule,
                                      type: e.target
                                        .value as ScheduleEntry["rule"]["type"],
                                      conditions: entry.rule.conditions,
                                      notes: entry.rule.notes,
                                      sourceDocumentId:
                                        entry.rule.sourceDocumentId,
                                      sourcePage: entry.rule.sourcePage,
                                    },
                                  })
                                }
                              >
                                <option value="recurring">
                                  Recurring interval
                                </option>
                                <option value="milestone">
                                  Specific service milestones
                                </option>
                                <option value="informational">
                                  Conditional / informational guidance
                                </option>
                              </AdminSelect>
                            </FormField>
                            {entry.rule.type === "recurring" && (
                              <>
                                {(["distanceKm", "months"] as const).map(
                                  (key) => (
                                    <FormField
                                      key={key}
                                      label={
                                        key === "distanceKm"
                                          ? "Distance interval (km)"
                                          : "Time interval (months)"
                                      }
                                    >
                                      <Input
                                        type="number"
                                        min={1}
                                        value={entry.rule[key] ?? ""}
                                        onChange={(e) =>
                                          changeEntry(index, {
                                            ...entry,
                                            rule: {
                                              ...entry.rule,
                                              [key]: e.target.value
                                                ? Number(e.target.value)
                                                : null,
                                            },
                                          })
                                        }
                                      />
                                    </FormField>
                                  ),
                                )}
                                <Text fontSize="sm">
                                  When both are set, whichever threshold is
                                  reached first applies.
                                </Text>
                              </>
                            )}
                            {entry.rule.type === "milestone" &&
                              (
                                [
                                  "distanceMilestones",
                                  "monthMilestones",
                                ] as const
                              ).map((key) => (
                                <MilestoneField
                                  key={key}
                                  label={
                                    key === "distanceMilestones"
                                      ? "Distance milestones (km, comma-separated)"
                                      : "Time milestones (months, comma-separated)"
                                  }
                                  values={entry.rule[key]}
                                  onChange={(values) =>
                                    changeEntry(index, {
                                      ...entry,
                                      rule: { ...entry.rule, [key]: values },
                                    })
                                  }
                                />
                              ))}
                            <FormField label="Applicability conditions">
                              <Textarea
                                value={entry.rule.conditions}
                                onChange={(e) =>
                                  changeEntry(index, {
                                    ...entry,
                                    rule: {
                                      ...entry.rule,
                                      conditions: e.target.value,
                                    },
                                  })
                                }
                              />
                            </FormField>
                            <FormField label="Explanatory notes">
                              <Textarea
                                value={entry.rule.notes}
                                onChange={(e) =>
                                  changeEntry(index, {
                                    ...entry,
                                    rule: {
                                      ...entry.rule,
                                      notes: e.target.value,
                                    },
                                  })
                                }
                              />
                            </FormField>
                            <FormField label="Source document">
                              <AdminSelect
                                value={entry.rule.sourceDocumentId || ""}
                                onChange={(e) =>
                                  changeEntry(index, {
                                    ...entry,
                                    rule: {
                                      ...entry.rule,
                                      sourceDocumentId: e.target.value || null,
                                    },
                                  })
                                }
                              >
                                <option value="">Select associated PDF</option>
                                {sources.map((d) => (
                                  <option key={d.id} value={d.id}>
                                    {d.name}
                                  </option>
                                ))}
                              </AdminSelect>
                            </FormField>
                            <FormField label="Source page">
                              <Input
                                type="number"
                                min={1}
                                value={entry.rule.sourcePage ?? ""}
                                onChange={(e) =>
                                  changeEntry(index, {
                                    ...entry,
                                    rule: {
                                      ...entry.rule,
                                      sourcePage: e.target.value
                                        ? Number(e.target.value)
                                        : null,
                                    },
                                  })
                                }
                              />
                            </FormField>
                          </Stack>
                        </Fieldset.Root>
                        <Flex gap={2} wrap="wrap" mt={3}>
                          <Button
                            variant="outline"
                            disabled={!entry.rule.sourceDocumentId}
                            onClick={() => {
                              setPdfId(entry.rule.sourceDocumentId || "");
                              setPage(entry.rule.sourcePage || 1);
                            }}
                          >
                            Inspect source page
                          </Button>
                          <Button
                            colorPalette="red"
                            variant="outline"
                            disabled={!canEdit}
                            onClick={() => {
                              setEntries(entries.filter((_, i) => i !== index));
                              setDirty(true);
                              setReviewed(false);
                            }}
                          >
                            Remove rule
                          </Button>
                        </Flex>
                      </Box>
                    ))}
                    {!entries.length && (
                      <Text>
                        No rules yet. Select standard items and enter
                        requirements from the original PDF.
                      </Text>
                    )}
                    <Button
                      variant="outline"
                      disabled={!canEdit}
                      onClick={() => {
                        setEntries([...entries, newEntry()]);
                        setDirty(true);
                        setReviewed(false);
                      }}
                    >
                      Add maintenance rule
                    </Button>
                    <Button disabled={!canEdit} onClick={saveDraft}>
                      Save draft
                    </Button>
                  </Stack>
                </Fieldset.Root>
              </Box>
            </Flex>
            <Flex gap={3} wrap="wrap" align="center">
              {schedule && schedule.status !== "superseded" && (
                <Button
                  variant="outline"
                  colorPalette="red"
                  disabled={dirty || busy}
                  onClick={retireSchedule}
                >
                  {schedule.status === "draft"
                    ? "Delete draft revision"
                    : "Withdraw schedule"}
                </Button>
              )}
              <Button
                variant="outline"
                disabled={!schedule || dirty || busy}
                onClick={() => validateOrPublish(false)}
              >
                Validate saved configuration
              </Button>
              <Checkbox
                checked={reviewed}
                disabled={!canEdit || dirty || !schedule || busy}
                onCheckedChange={(e) => setReviewed(e.checked === true)}
              >
                I verified every rule, action, condition and source page against
                the original PDF.
              </Checkbox>
              <Button
                colorPalette="brand"
                disabled={!schedule || !canEdit || dirty || busy || !reviewed}
                onClick={() => validateOrPublish(true)}
              >
                Publish verified schedule
              </Button>
            </Flex>
            {dirty && (
              <Text fontSize="sm">
                Save the draft before validation or publication.
              </Text>
            )}
          </>
        )}
      </Stack>
    </AdminLayout>
  );
}

function MilestoneField({
  label,
  values,
  onChange,
}: {
  label: string;
  values: number[];
  onChange: (values: number[]) => void;
}) {
  const [text, setText] = useState(values.join(", "));
  const [error, setError] = useState("");
  return (
    <FormField label={label}>
      <Input
        value={text}
        onChange={(e) => {
          const value = e.target.value;
          setText(value);
          const numbers = value.trim()
            ? value.split(",").map((part) => Number(part.trim()))
            : [];
          if (
            numbers.some((n) => !Number.isInteger(n) || n <= 0) ||
            numbers.some((n, i) => i > 0 && n <= numbers[i - 1])
          ) {
            setError("Use unique positive numbers in ascending order.");
            e.target.setCustomValidity("Invalid milestones");
            // Invalid input must also fail backend draft validation rather than saving stale values.
            onChange([-1]);
          } else {
            setError("");
            e.target.setCustomValidity("");
            onChange(numbers);
          }
        }}
      />
      {error && (
        <Text role="alert" color="red.700">
          {error}
        </Text>
      )}
    </FormField>
  );
}
