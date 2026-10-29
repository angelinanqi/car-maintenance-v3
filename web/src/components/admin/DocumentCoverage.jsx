"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Box,
  Button,
  Fieldset,
  Flex,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import { useContent } from "@/components/ContentProvider";
import { request } from "@/api/client.mjs";
import { documentCoverage } from "@/lib/adminJourney.mjs";
import FormField from "./FormField";
import useUnsavedChanges from "./useUnsavedChanges";

export default function DocumentCoverage({
  document,
  preferredVehicle = "",
  onDirty,
  onSaved,
  disabled = false,
  prepare = false,
}) {
  const { knowledge, refresh } = useContent();
  const coverage = documentCoverage(document.id, knowledge);
  const initial = {
    ...coverage,
    vehicle_ids:
      coverage.vehicle_ids.length ||
      coverage.category_ids.length ||
      !preferredVehicle
        ? coverage.vehicle_ids
        : [preferredVehicle],
    year: document.year || "",
    engine: document.engine || "",
    variant: document.variant || "",
    vehicle_independent: document.vehicle_independent || false,
  };
  const [baseline, setBaseline] = useState({
    ...initial,
    vehicle_ids: coverage.vehicle_ids,
  });
  const [draft, setDraft] = useState(initial);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  useUnsavedChanges(dirty);
  useEffect(() => {
    onDirty?.(dirty);
    return () => onDirty?.(false);
  }, [dirty, onDirty]);

  function toggle(field, id) {
    setDraft((previous) => ({
      ...previous,
      [field]: previous[field].includes(id)
        ? previous[field].filter((value) => value !== id)
        : [...previous[field], id],
    }));
    setNotice("");
  }

  async function save(event) {
    event.preventDefault();
    if (busy) return;
    const shouldPrepare = prepare && event.nativeEvent.submitter?.value !== "save";
    let coverageSaved = false;
    if (!draft.vehicle_ids.length && !draft.category_ids.length) {
      setError(
        "Choose at least one vehicle or topic so we know where this document belongs.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { vehicle_ids, category_ids, ...metadata } = draft;
      await request(`/documents/${document.id}`, {
        method: "PATCH",
        body: metadata,
      });
      await request(`/knowledge/documents/${document.id}/associations`, {
        method: "PUT",
        body: { vehicle_ids, category_ids },
      });
      setBaseline(draft);
      coverageSaved = true;
      if (shouldPrepare) {
        const force = document.status === "processed" ? "?force=true" : "";
        await request(`/documents/${document.id}/process${force}`, { method: "POST" });
        setNotice("Coverage saved and preparation requested. You can return later.");
      } else {
        setNotice("Coverage saved. You can continue with the next step below.");
      }
      await refresh({ documentsOnly: true });
      onSaved?.();
    } catch (cause) {
      setError(`${coverageSaved && shouldPrepare ? "Coverage was saved, but preparation was not confirmed. " : ""}${cause.message}`);
      await refresh({ documentsOnly: true });
    } finally {
      setBusy(false);
    }
  }

  const matches = (text) =>
    text.toLowerCase().includes(query.trim().toLowerCase());
  return (
    <form onSubmit={save}>
      <Fieldset.Root disabled={busy || disabled}>
        <Stack gap={4}>
          <Text color="muted">
            Choose only the vehicles and topics covered by the original. If a
            year or engine is unclear, save your work and confirm it before
            making the document available.
          </Text>
          {error && <Text role="alert">{error}</Text>}
          {notice && <Text role="status">{notice}</Text>}
          <FormField label="Find a vehicle or topic">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by model, year, engine or topic"
            />
          </FormField>
          <Box>
            <Text fontWeight="600" mb={2}>
              Vehicles covered
            </Text>
            <Stack gap={3} maxH="280px" overflowY="auto" p={1}>
              {knowledge.vehicles
                .filter((vehicle) =>
                  matches(
                    [
                      vehicle.name,
                      vehicle.year,
                      vehicle.engine,
                      vehicle.variant,
                    ].join(" "),
                  ),
                )
                .map((vehicle) => (
                  <Checkbox
                    key={vehicle.id}
                    checked={draft.vehicle_ids.includes(vehicle.id)}
                    onCheckedChange={() => toggle("vehicle_ids", vehicle.id)}
                  >
                    {[
                      vehicle.name,
                      vehicle.year,
                      vehicle.engine,
                      vehicle.variant,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </Checkbox>
                ))}
              {!knowledge.vehicles.length && (
                <Text>
                  No vehicles yet.{" "}
                  <NextLink
                    href="/admin/vehicles"
                    style={{ textDecoration: "underline" }}
                  >
                    Add a vehicle
                  </NextLink>{" "}
                  before assigning a vehicle-specific manual.
                </Text>
              )}
            </Stack>
          </Box>
          <Box>
            <Text fontWeight="600" mb={2}>
              Related learning topics
            </Text>
            <Stack gap={3} maxH="200px" overflowY="auto" p={1}>
              {knowledge.categories
                .filter((category) => matches(category.name))
                .map((category) => (
                  <Checkbox
                    key={category.id}
                    checked={draft.category_ids.includes(category.id)}
                    onCheckedChange={() => toggle("category_ids", category.id)}
                  >
                    {category.name}
                  </Checkbox>
                ))}
              {!knowledge.categories.length && (
                <Text>
                  No topics yet.{" "}
                  <NextLink
                    href="/admin/learn-cards/manage-cat"
                    style={{ textDecoration: "underline" }}
                  >
                    Add a learning topic
                  </NextLink>{" "}
                  for general reference material.
                </Text>
              )}
            </Stack>
          </Box>
          <Text fontSize="sm">
            Selected: {draft.vehicle_ids.length} vehicles and{" "}
            {draft.category_ids.length} topics. Searching does not remove your
            selections.
          </Text>
          <Checkbox
            checked={draft.vehicle_independent}
            onCheckedChange={(event) =>
              setDraft({
                ...draft,
                vehicle_independent: event.checked === true,
              })
            }
          >
            This is general guidance that is not specific to a car model.
          </Checkbox>
          <Box as="details">
            <Box as="summary">
              Year, engine or version stated in the document (optional)
            </Box>
            <Stack mt={3} gap={3}>
              <Text fontSize="sm" color="muted">
                Copy these details from the manual if provided. These describe
                the document; the selections above determine where it is used.
              </Text>
              {[
                ["year", "Model year or year range"],
                ["engine", "Engine"],
                ["variant", "Version / trim"],
              ].map(([key, label]) => (
                <FormField key={key} label={label}>
                  <Input
                    value={draft[key]}
                    onChange={(event) =>
                      setDraft({ ...draft, [key]: event.target.value })
                    }
                  />
                </FormField>
              ))}
            </Stack>
          </Box>
          <Flex gap={3} wrap="wrap">
            <Button
              type="submit"
              value={prepare ? "prepare" : "save"}
              loading={busy}
              disabled={!prepare && !dirty}
            >
              {prepare ? "Save coverage and prepare" : "Save coverage"}
            </Button>
            {prepare && (
              <Button type="submit" value="save" variant="outline" disabled={busy || !dirty}>
                Save coverage only
              </Button>
            )}
          </Flex>
        </Stack>
      </Fieldset.Root>
    </form>
  );
}
