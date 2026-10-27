"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import {
  Badge,
  Box,
  Button,
  Flex,
  Grid,
  Heading,
  Input,
  Stack,
  Tabs,
  Text,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import ListFilters from "@/components/admin/ListFilters";
import FormField from "@/components/admin/FormField";
import { AdminSelect } from "@/components/admin/NativeControls";
import {
  ManufacturerEditor,
  ModelEditor,
  VehicleEditor,
} from "@/components/admin/CatalogueEditors";
import {
  loadCatalogue,
  type Catalogue,
  type Manufacturer,
  type VehicleModel,
  type Vehicle,
} from "@/api/admin";
import { vehicleAvailability } from "@/lib/catalogue.mjs";

type Section = "vehicles" | "models" | "manufacturers";
type Editor =
  | { kind: "vehicles"; row?: Vehicle }
  | { kind: "models"; row?: VehicleModel }
  | { kind: "manufacturers"; row?: Manufacturer };

export default function VehiclesPage() {
  const router = useRouter();
  const [data, setData] = useState<Catalogue | null>(null);
  const [section, setSection] = useState<Section>("vehicles");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [query, setQuery] = useState("");
  const [manufacturerId, setManufacturerId] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    loadCatalogue()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function reload() {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      setData(await loadCatalogue());
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
    }
  }
  function chooseSection(next: Section) {
    setSection(next);
    setQuery("");
    setStatus("all");
    setManufacturerId("");
  }
  function saved<T extends Manufacturer | VehicleModel | Vehicle>(
    kind: Section,
    row: T,
  ) {
    setData((current) =>
      current
        ? {
            ...current,
            [kind]: [
              ...current[kind].filter((entry) => entry.id !== row.id),
              row,
            ],
          }
        : current,
    );
    setEditor(null);
    setNotice(`${row.name} saved.`);
    setQuery("");
    setManufacturerId("");
    setStatus("all");
    if (kind === "vehicles") router.push(`/admin/vehicles/${row.id}`);
  }
  const matchesQuery = (text: string) =>
    text.toLowerCase().includes(query.trim().toLowerCase());
  const matchesStatus = (active: boolean) =>
    status === "all" || (status === "active" ? active : !active);
  const manufacturerName = (id?: string) =>
    data?.manufacturers.find((row) => row.id === id)?.name ||
    "Manufacturer unavailable";
  const vehicles = (data?.vehicles || [])
    .filter((row) => {
      const model = data?.models.find((m) => m.id === row.model_id);
      const availability = vehicleAvailability(
        row,
        data?.models || [],
        data?.manufacturers || [],
      );
      return (
        (!manufacturerId || model?.manufacturer_id === manufacturerId) &&
        matchesStatus(availability === "Available in Roadie") &&
        matchesQuery(
          `${row.name} ${manufacturerName(model?.manufacturer_id)} ${model?.name || ""} ${row.year} ${row.engine} ${row.variant} ${row.code}`,
        )
      );
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  const models = (data?.models || [])
    .filter(
      (row) =>
        (!manufacturerId || row.manufacturer_id === manufacturerId) &&
        matchesStatus(row.active) &&
        matchesQuery(`${row.name} ${manufacturerName(row.manufacturer_id)}`),
    )
    .sort((a, b) => a.name.localeCompare(b.name));
  const manufacturers = (data?.manufacturers || [])
    .filter((row) => matchesStatus(row.active) && matchesQuery(row.name))
    .sort((a, b) => a.name.localeCompare(b.name));
  const count =
    section === "vehicles"
      ? vehicles.length
      : section === "models"
        ? models.length
        : manufacturers.length;
  const total = data?.[section].length || 0;
  const singular =
    section === "vehicles"
      ? "vehicle variant"
      : section === "models"
        ? "model"
        : "manufacturer";
  function add() {
    setEditor({ kind: section });
  }

  return (
    <AdminLayout
      title="Vehicles"
      description="Choose a vehicle to update its manuals, service schedule and information available to drivers."
    >
      <Stack gap={5}>
        {notice && <Text role="status">{notice}</Text>}
        {error && (
          <Box role="alert">
            <Text>{error}</Text>
            <Button
              variant="outline"
              mt={3}
              onClick={reload}
              disabled={loading}
            >
              Retry catalogue
            </Button>
          </Box>
        )}
        <Tabs.Root
          value={section}
          onValueChange={({ value }) => chooseSection(value as Section)}
        >
          <Tabs.List overflowX="auto" mb={6}>
            <Tabs.Trigger value="vehicles">
              Vehicles {data ? `(${data.vehicles.length})` : ""}
            </Tabs.Trigger>
            <Tabs.Trigger value="models">
              Models {data ? `(${data.models.length})` : ""}
            </Tabs.Trigger>
            <Tabs.Trigger value="manufacturers">
              Manufacturers {data ? `(${data.manufacturers.length})` : ""}
            </Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value={section} p={0}>
            <Flex
              justify="space-between"
              gap={4}
              align="start"
              wrap="wrap"
              mb={5}
            >
              <Box>
                <Heading as="h2" size="xl">
                  {section === "vehicles"
                    ? "Vehicle variants"
                    : section === "models"
                      ? "Models"
                      : "Manufacturers"}
                </Heading>
                <Text color="muted" mt={2}>
                  {section === "vehicles"
                    ? "A variant is one model year and configuration."
                    : section === "models"
                      ? "Model families such as Myvi or City. Each belongs to one manufacturer."
                      : "Vehicle makes such as Perodua or Honda. Inactive makes and their vehicles are hidden from new selections."}
                </Text>
              </Box>
              <Flex gap={2} wrap="wrap">
                <Button variant="outline" loading={loading} onClick={reload}>
                  Refresh
                </Button>
                <Button
                  disabled={
                    !data ||
                    loading ||
                    (section === "vehicles" && !data.models.length) ||
                    (section === "models" && !data.manufacturers.length)
                  }
                  onClick={add}
                >
                  Add {singular}
                </Button>
              </Flex>
            </Flex>
            {data && section === "vehicles" && !data.models.length && (
              <Box bg="brand.100" p={5} borderRadius="8px" mb={5}>
                <Text fontWeight="600">
                  Set up a model before adding a vehicle
                </Text>
                <Text mt={1}>
                  Add the manufacturer first, then its model. You can then add
                  year and trim variants here.
                </Text>
                <Button
                  variant="outline"
                  mt={3}
                  onClick={() =>
                    chooseSection(
                      data.manufacturers.length ? "models" : "manufacturers",
                    )
                  }
                >
                  Go to {data.manufacturers.length ? "models" : "manufacturers"}
                </Button>
              </Box>
            )}
            {data && section === "models" && !data.manufacturers.length && (
              <Box bg="brand.100" p={5} borderRadius="8px" mb={5}>
                <Text>Add a manufacturer before creating a model.</Text>
                <Button
                  variant="outline"
                  mt={3}
                  onClick={() => chooseSection("manufacturers")}
                >
                  Go to manufacturers
                </Button>
              </Box>
            )}
            <Box mb={5}>
              <ListFilters
                columns={
                  section === "manufacturers" ? "2fr 1fr" : "2fr 1fr 1fr"
                }
                activeCount={
                  Number(Boolean(manufacturerId)) + Number(status !== "all")
                }
                search={
                  <FormField label={`Search ${section}`}>
                    <Input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder={
                        section === "vehicles"
                          ? "Name, make, model, year, engine or code"
                          : "Name or manufacturer"
                      }
                      disabled={!data}
                    />
                  </FormField>
                }
              >
                {section !== "manufacturers" && (
                  <FormField label="Manufacturer">
                    <AdminSelect
                      value={manufacturerId}
                      onChange={(e) => setManufacturerId(e.target.value)}
                      disabled={!data}
                    >
                      <option value="">All manufacturers</option>
                      {data?.manufacturers.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </AdminSelect>
                  </FormField>
                )}
                <FormField
                  label={
                    section === "vehicles" ? "Roadie selection" : "Entry status"
                  }
                >
                  <AdminSelect
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    disabled={!data}
                  >
                    <option value="all">All entries</option>
                    <option value="active">
                      {section === "vehicles"
                        ? "Available in Roadie"
                        : "Active"}
                    </option>
                    <option value="inactive">
                      {section === "vehicles"
                        ? "Unavailable in Roadie"
                        : "Inactive"}
                    </option>
                  </AdminSelect>
                </FormField>
              </ListFilters>
            </Box>
            {loading && !data && <Text role="status">Loading catalogue…</Text>}
            {data && (
              <Text fontSize="sm" color="muted" mb={3}>
                {count} of {total} {section}
                {section === "vehicles"
                  ? ". Open a vehicle to see its documents, service schedule and availability."
                  : ". Deactivate entries to preserve existing records."}
              </Text>
            )}
            <Stack as="ul" gap={3} listStyleType="none" m={0} p={0}>
              {section === "vehicles" &&
                vehicles.map((row) => {
                  const model = data?.models.find((m) => m.id === row.model_id);
                  const availability = vehicleAvailability(
                    row,
                    data?.models || [],
                    data?.manufacturers || [],
                  );
                  return (
                    <Box
                      as="li"
                      key={row.id}
                      bg="white"
                      p={5}
                      borderRadius="10px"
                    >
                      <Grid
                        templateColumns={{
                          base: "1fr",
                          xl: "minmax(0, 1.4fr) minmax(0, 1fr) auto",
                        }}
                        gap={5}
                        alignItems="start"
                      >
                        <Box>
                          <Heading as="h3" size="md">
                            <NextLink href={`/admin/vehicles/${row.id}`}>
                              {row.name}
                            </NextLink>
                          </Heading>
                          <Text color="muted" mt={1}>
                            {model
                              ? `${manufacturerName(model.manufacturer_id)} · ${model.name}`
                              : "Model not linked"}{" "}
                            · {row.year || "Year not set"}
                          </Text>
                          <Text fontSize="sm" mt={1}>
                            {[
                              row.engine,
                              row.variant,
                              row.powertrain === "diesel" ? "Diesel" : "Petrol",
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </Text>
                        </Box>
                        <Stack gap={2} align="start">
                          <Badge
                            colorPalette={
                              availability === "Available in Roadie"
                                ? "green"
                                : "orange"
                            }
                          >
                            {availability}
                          </Badge>
                          <Text fontSize="sm">
                            Chatbot:{" "}
                            {row.published
                              ? "Enabled; needs published content"
                              : "Not enabled"}
                          </Text>
                          <Text fontSize="sm" color="muted">
                            Owner’s manual:{" "}
                            {row.manual_available
                              ? "Available"
                              : "Not published"}
                            <br />
                            Service schedule:{" "}
                            {row.manufacturer_schedule_available
                              ? "Published"
                              : "Not published"}
                          </Text>
                        </Stack>
                        <Flex gap={2} wrap="wrap">
                          <Button asChild size="sm">
                            <NextLink href={`/admin/vehicles/${row.id}`}>
                              Open vehicle
                            </NextLink>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setEditor({ kind: "vehicles", row })}
                            aria-label={`Edit ${row.name}`}
                          >
                            Edit
                          </Button>
                          <Button variant="outline" size="sm" asChild>
                            <NextLink
                              href={`/admin/schedules?vehicle=${row.id}`}
                            >
                              Schedules
                            </NextLink>
                          </Button>
                        </Flex>
                      </Grid>
                    </Box>
                  );
                })}
              {section === "models" &&
                models.map((row) => (
                  <Box
                    as="li"
                    key={row.id}
                    bg="white"
                    p={5}
                    borderRadius="10px"
                  >
                    <Flex
                      gap={4}
                      justify="space-between"
                      align="start"
                      wrap="wrap"
                    >
                      <Box flex={1}>
                        <Heading as="h3" size="md">
                          {manufacturerName(row.manufacturer_id)} · {row.name}
                        </Heading>
                        <Text color="muted" mt={2}>
                          {
                            data?.vehicles.filter((v) => v.model_id === row.id)
                              .length
                          }{" "}
                          vehicle variants
                        </Text>
                        {!data?.manufacturers.find(
                          (m) => m.id === row.manufacturer_id,
                        )?.active && (
                          <Text fontSize="sm" color="orange.700" mt={1}>
                            Manufacturer inactive: variants remain unavailable
                            in Roadie.
                          </Text>
                        )}
                      </Box>
                      <Badge colorPalette={row.active ? "green" : "gray"}>
                        {row.active ? "Active model" : "Inactive model"}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        aria-label={`Edit ${row.name}`}
                        onClick={() => setEditor({ kind: "models", row })}
                      >
                        Edit
                      </Button>
                    </Flex>
                  </Box>
                ))}
              {section === "manufacturers" &&
                manufacturers.map((row) => (
                  <Box
                    as="li"
                    key={row.id}
                    bg="white"
                    p={5}
                    borderRadius="10px"
                  >
                    <Flex
                      gap={4}
                      justify="space-between"
                      align="start"
                      wrap="wrap"
                    >
                      <Box flex={1}>
                        <Heading as="h3" size="md">
                          {row.name}
                        </Heading>
                        <Text color="muted" mt={2}>
                          {
                            data?.models.filter(
                              (m) => m.manufacturer_id === row.id,
                            ).length
                          }{" "}
                          models
                        </Text>
                      </Box>
                      <Badge colorPalette={row.active ? "green" : "gray"}>
                        {row.active ? "Active" : "Inactive"}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        aria-label={`Edit ${row.name}`}
                        onClick={() =>
                          setEditor({ kind: "manufacturers", row })
                        }
                      >
                        Edit
                      </Button>
                    </Flex>
                  </Box>
                ))}
            </Stack>
            {data && !count && (
              <Box bg="white" p={8} borderRadius="10px" mt={3}>
                <Heading as="h3" size="md">
                  {total ? "No matching entries" : `No ${section} yet`}
                </Heading>
                <Text mt={2} color="muted">
                  {total
                    ? "Try another search or clear the filters."
                    : `Use Add ${singular} to create your first entry. Nothing is created until you save.`}
                </Text>
                {total > 0 && (
                  <Button
                    variant="outline"
                    mt={4}
                    onClick={() => {
                      setQuery("");
                      setManufacturerId("");
                      setStatus("all");
                    }}
                  >
                    Clear filters
                  </Button>
                )}
              </Box>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </Stack>
      {data && editor?.kind === "vehicles" && (
        <VehicleEditor
          data={data}
          row={editor.row}
          onClose={() => setEditor(null)}
          onSaved={(row) => saved("vehicles", row)}
        />
      )}
      {data && editor?.kind === "models" && (
        <ModelEditor
          data={data}
          row={editor.row}
          onClose={() => setEditor(null)}
          onSaved={(row) => saved("models", row)}
        />
      )}
      {editor?.kind === "manufacturers" && (
        <ManufacturerEditor
          row={editor.row}
          onClose={() => setEditor(null)}
          onSaved={(row) => saved("manufacturers", row)}
        />
      )}
    </AdminLayout>
  );
}
