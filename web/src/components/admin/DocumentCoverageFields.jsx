"use client";

import { useState } from "react";
import NextLink from "next/link";
import { Box, Input, Stack, Text } from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import FormField from "./FormField";

export default function DocumentCoverageFields({ knowledge, draft, onChange }) {
  const [query, setQuery] = useState("");
  const matches = (text) => text.toLowerCase().includes(query.trim().toLowerCase());
  const toggle = (field, id) => onChange({
    ...draft,
    [field]: draft[field].includes(id)
      ? draft[field].filter((value) => value !== id)
      : [...draft[field], id],
  });
  const vehicles = knowledge.vehicles.filter((vehicle) => matches(
    [vehicle.name, vehicle.year, vehicle.engine, vehicle.variant].join(" "),
  ));
  const categories = knowledge.categories
    .filter((category) => !category.archived || draft.category_ids.includes(category.id))
    .filter((category) => matches(category.name));

  return (
    <Stack gap={4}>
      <FormField label="Find a vehicle or topic">
        <Input value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by model, year, engine or topic" />
      </FormField>
      <Box>
        <Text fontWeight="600" mb={2}>Vehicles covered</Text>
        <Stack gap={3} maxH="240px" overflowY="auto" p={1}>
          {vehicles.map((vehicle) => (
            <Checkbox key={vehicle.id} checked={draft.vehicle_ids.includes(vehicle.id)}
              onCheckedChange={() => toggle("vehicle_ids", vehicle.id)}>
              {[vehicle.name, vehicle.year, vehicle.engine, vehicle.variant].filter(Boolean).join(" · ")}
            </Checkbox>
          ))}
          {!knowledge.vehicles.length && (
            <Text>No vehicles yet. <NextLink href="/admin/vehicles" style={{ textDecoration: "underline" }}>Add a vehicle</NextLink> before assigning a vehicle-specific manual.</Text>
          )}
          {knowledge.vehicles.length > 0 && !vehicles.length && <Text color="muted">No vehicles match this search.</Text>}
        </Stack>
      </Box>
      <Box>
        <Text fontWeight="600" mb={2}>Related learning topics</Text>
        <Stack gap={3} maxH="180px" overflowY="auto" p={1}>
          {categories.map((category) => (
            <Checkbox key={category.id} checked={draft.category_ids.includes(category.id)}
              onCheckedChange={() => toggle("category_ids", category.id)}>
              {category.name}{category.archived ? " (Archived)" : ""}
            </Checkbox>
          ))}
          {!knowledge.categories.length && (
            <Text>No topics yet. <NextLink href="/admin/learn-cards/manage-cat" style={{ textDecoration: "underline" }}>Add a learning topic</NextLink> for general reference material.</Text>
          )}
          {knowledge.categories.length > 0 && !categories.length && <Text color="muted">No available topics match this search.</Text>}
        </Stack>
      </Box>
      <Text fontSize="sm">
        Selected: {draft.vehicle_ids.length} vehicles and {draft.category_ids.length} topics.
        Searching keeps your selections.
      </Text>
      <Checkbox checked={draft.vehicle_independent}
        onCheckedChange={(event) => onChange({ ...draft, vehicle_independent: event.checked === true })}>
        This is general guidance that is not specific to a car model.
      </Checkbox>
      {draft.vehicle_independent && <Text fontSize="sm" color="muted">Choose the learning topics this general guidance covers.</Text>}
      <Box as="details">
        <Box as="summary">Year, Engine or Version Stated in the Document (Optional)</Box>
        <Stack mt={3} gap={3}>
          <Text fontSize="sm" color="muted">
            Copy these details from the manual if provided. These describe the document;
            the selections above determine where it is used.
          </Text>
          {[["year", "Model year or year range"], ["engine", "Engine"], ["variant", "Version / trim"]].map(([key, label]) => (
            <FormField key={key} label={label}>
              <Input value={draft[key]} onChange={(event) => onChange({ ...draft, [key]: event.target.value })} />
            </FormField>
          ))}
        </Stack>
      </Box>
    </Stack>
  );
}
