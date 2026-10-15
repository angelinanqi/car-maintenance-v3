"use client";

import { useCallback, useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import FormField from "@/components/admin/FormField";
import {
  loadCatalogue,
  saveManufacturer,
  saveModel,
  saveVehicle,
  type Catalogue,
  type Vehicle,
} from "@/api/admin";

const emptyVehicle = {
  code: "",
  name: "",
  model_id: "",
  year: "",
  engine: "",
  variant: "",
  powertrain: "petrol" as Vehicle["powertrain"],
  active: true,
  published: false,
};

export default function VehiclesPage() {
  const [data, setData] = useState<Catalogue | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [manufacturerId, setManufacturerId] = useState("");
  const [manufacturer, setManufacturer] = useState({ name: "", active: true });
  const [modelId, setModelId] = useState("");
  const [model, setModel] = useState({
    name: "",
    manufacturer_id: "",
    active: true,
  });
  const [vehicleId, setVehicleId] = useState("");
  const [vehicle, setVehicle] = useState(emptyVehicle);
  const [manufacturerFilter, setManufacturerFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");
  const reload = useCallback(async () => {
    setData(await loadCatalogue());
  }, []);
  useEffect(() => {
    let active = true;
    loadCatalogue()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((failure: Error) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, []);

  async function save(action: () => Promise<unknown>, reset: () => void) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      reset();
      await reload();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const models = data?.models || [];
  const manufacturers = data?.manufacturers || [];
  const vehicles = (data?.vehicles || []).filter((row) => {
    const model = models.find((m) => m.id === row.model_id);
    const maker = manufacturers.find((m) => m.id === model?.manufacturer_id);
    return (
      (!manufacturerFilter || maker?.id === manufacturerFilter) &&
      (activeFilter === "all" || row.active === (activeFilter === "active")) &&
      `${row.name} ${maker?.name || ""} ${model?.name || ""} ${row.year} ${row.variant} ${row.code}`
        .toLowerCase()
        .includes(query.toLowerCase())
    );
  });

  return (
    <AdminLayout
      title="Vehicle Catalogue"
      description="Manage central ICE vehicle identities used by mobile registration and document scopes."
    >
      <Stack gap={5}>
        {error && (
          <Text role="alert" color="red.700">
            {error}
          </Text>
        )}
        <Button
          alignSelf="start"
          variant="outline"
          onClick={() =>
            reload()
              .then(() => setError(""))
              .catch((e: Error) => setError(e.message))
          }
        >
          Reload catalogue
        </Button>
        {!data && !error && <Text>Loading catalogue…</Text>}
        {data && (
          <>
            <Flex gap={4} wrap="wrap">
              <Box
                flex="1"
                minW="260px"
                p={4}
                borderWidth="1px"
                borderRadius="md"
              >
                <Heading size="md" mb={3}>
                  Manufacturers
                </Heading>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void save(
                      () => saveManufacturer(manufacturerId, manufacturer),
                      () => {
                        setManufacturerId("");
                        setManufacturer({ name: "", active: true });
                      },
                    );
                  }}
                >
                  <fieldset disabled={busy}>
                    <Stack gap={3}>
                      <FormField label="Manufacturer to edit">
                        <select
                          value={manufacturerId}
                          onChange={(e) => {
                            const row = manufacturers.find(
                              (r) => r.id === e.target.value,
                            );
                            setManufacturerId(e.target.value);
                            setManufacturer(
                              row
                                ? { name: row.name, active: row.active }
                                : { name: "", active: true },
                            );
                          }}
                        >
                          <option value="">New manufacturer</option>
                          {manufacturers.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.name}
                            </option>
                          ))}
                        </select>
                      </FormField>
                      <FormField label="Name">
                        <Input
                          required
                          value={manufacturer.name}
                          onChange={(e) =>
                            setManufacturer({
                              ...manufacturer,
                              name: e.target.value,
                            })
                          }
                        />
                      </FormField>
                      <label>
                        <input
                          type="checkbox"
                          checked={manufacturer.active}
                          onChange={(e) =>
                            setManufacturer({
                              ...manufacturer,
                              active: e.target.checked,
                            })
                          }
                        />{" "}
                        Active manufacturer
                      </label>
                      <Button type="submit">Save manufacturer</Button>
                    </Stack>
                  </fieldset>
                </form>
              </Box>
              <Box
                flex="1"
                minW="260px"
                p={4}
                borderWidth="1px"
                borderRadius="md"
              >
                <Heading size="md" mb={3}>
                  Models
                </Heading>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void save(
                      () => saveModel(modelId, model),
                      () => {
                        setModelId("");
                        setModel({
                          name: "",
                          manufacturer_id: "",
                          active: true,
                        });
                      },
                    );
                  }}
                >
                  <fieldset disabled={busy}>
                    <Stack gap={3}>
                      <FormField label="Model to edit">
                        <select
                          value={modelId}
                          onChange={(e) => {
                            const row = models.find(
                              (r) => r.id === e.target.value,
                            );
                            setModelId(e.target.value);
                            setModel(
                              row
                                ? {
                                    name: row.name,
                                    manufacturer_id: row.manufacturer_id,
                                    active: row.active,
                                  }
                                : {
                                    name: "",
                                    manufacturer_id: "",
                                    active: true,
                                  },
                            );
                          }}
                        >
                          <option value="">New model</option>
                          {models.map((r) => (
                            <option key={r.id} value={r.id}>
                              {
                                manufacturers.find(
                                  (m) => m.id === r.manufacturer_id,
                                )?.name
                              }{" "}
                              {r.name}
                            </option>
                          ))}
                        </select>
                      </FormField>
                      <FormField label="Manufacturer">
                        <select
                          required
                          disabled={Boolean(modelId)}
                          value={model.manufacturer_id}
                          onChange={(e) =>
                            setModel({
                              ...model,
                              manufacturer_id: e.target.value,
                            })
                          }
                        >
                          <option value="">Select manufacturer</option>
                          {manufacturers.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.name}
                            </option>
                          ))}
                        </select>
                      </FormField>
                      <FormField label="Model name">
                        <Input
                          required
                          value={model.name}
                          onChange={(e) =>
                            setModel({ ...model, name: e.target.value })
                          }
                        />
                      </FormField>
                      <label>
                        <input
                          type="checkbox"
                          checked={model.active}
                          onChange={(e) =>
                            setModel({ ...model, active: e.target.checked })
                          }
                        />{" "}
                        Active model
                      </label>
                      <Button type="submit">Save model</Button>
                    </Stack>
                  </fieldset>
                </form>
              </Box>
            </Flex>
            <Box p={4} borderWidth="1px" borderRadius="md">
              <Heading size="md" mb={3}>
                {vehicleId ? "Edit vehicle variant" : "Add vehicle variant"}
              </Heading>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void save(
                    () =>
                      saveVehicle(vehicleId, {
                        ...vehicle,
                        model_id: vehicle.model_id || null,
                      }),
                    () => {
                      setVehicleId("");
                      setVehicle(emptyVehicle);
                    },
                  );
                }}
              >
                <fieldset disabled={busy}>
                  <Stack gap={3}>
                    <FormField label="Model">
                      <select
                        required
                        value={vehicle.model_id}
                        disabled={Boolean(
                          vehicleId &&
                          data.vehicles.find((r) => r.id === vehicleId)
                            ?.model_id,
                        )}
                        onChange={(e) =>
                          setVehicle({ ...vehicle, model_id: e.target.value })
                        }
                      >
                        <option value="">Select model</option>
                        {models.map((r) => (
                          <option key={r.id} value={r.id}>
                            {
                              manufacturers.find(
                                (m) => m.id === r.manufacturer_id,
                              )?.name
                            }{" "}
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </FormField>
                    <Flex gap={3} wrap="wrap">
                      <FormField label="Display name">
                        <Input
                          required
                          value={vehicle.name}
                          onChange={(e) =>
                            setVehicle({ ...vehicle, name: e.target.value })
                          }
                        />
                      </FormField>
                      <FormField label="Stable code">
                        <Input
                          required
                          pattern="[a-z0-9]+(-[a-z0-9]+)*"
                          value={vehicle.code}
                          onChange={(e) =>
                            setVehicle({ ...vehicle, code: e.target.value })
                          }
                        />
                      </FormField>
                      <FormField label="Model year">
                        <Input
                          required
                          type="number"
                          min={1900}
                          max={2100}
                          value={vehicle.year}
                          onChange={(e) =>
                            setVehicle({ ...vehicle, year: e.target.value })
                          }
                        />
                      </FormField>
                    </Flex>
                    <Flex gap={3} wrap="wrap">
                      <FormField label="Engine">
                        <Input
                          value={vehicle.engine}
                          onChange={(e) =>
                            setVehicle({ ...vehicle, engine: e.target.value })
                          }
                        />
                      </FormField>
                      <FormField label="Variant / transmission">
                        <Input
                          value={vehicle.variant}
                          onChange={(e) =>
                            setVehicle({ ...vehicle, variant: e.target.value })
                          }
                        />
                      </FormField>
                      <FormField label="Powertrain">
                        <select
                          value={vehicle.powertrain}
                          onChange={(e) =>
                            setVehicle({
                              ...vehicle,
                              powertrain: e.target
                                .value as Vehicle["powertrain"],
                            })
                          }
                        >
                          <option value="petrol">Petrol ICE</option>
                          <option value="diesel">Diesel ICE</option>
                        </select>
                      </FormField>
                    </Flex>
                    <label>
                      <input
                        type="checkbox"
                        checked={vehicle.active}
                        onChange={(e) =>
                          setVehicle({ ...vehicle, active: e.target.checked })
                        }
                      />{" "}
                      Available for new mobile registrations
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={vehicle.published}
                        onChange={(e) =>
                          setVehicle({
                            ...vehicle,
                            published: e.target.checked,
                          })
                        }
                      />{" "}
                      Publish vehicle knowledge scope for chat
                    </label>
                    <Flex gap={3}>
                      <Button type="submit">Save vehicle</Button>
                      {vehicleId && (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setVehicleId("");
                            setVehicle(emptyVehicle);
                          }}
                        >
                          Cancel edit
                        </Button>
                      )}
                    </Flex>
                  </Stack>
                </fieldset>
              </form>
            </Box>
            <Flex gap={3} wrap="wrap">
              <Input
                maxW="360px"
                aria-label="Search vehicles"
                placeholder="Search vehicle, year or variant"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <FormField label="Manufacturer filter">
                <select
                  value={manufacturerFilter}
                  onChange={(e) => setManufacturerFilter(e.target.value)}
                >
                  <option value="">All manufacturers</option>
                  {manufacturers.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField label="Status filter">
                <select
                  value={activeFilter}
                  onChange={(e) => setActiveFilter(e.target.value)}
                >
                  <option value="all">All statuses</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </FormField>
            </Flex>
            <Table.ScrollArea>
              <Table.Root minW="700px">
                <Table.Header>
                  <Table.Row>
                    {[
                      "Vehicle",
                      "Catalogue",
                      "Owner's manual",
                      "Manufacturer schedule",
                      "Actions",
                    ].map((label) => (
                      <Table.ColumnHeader key={label}>
                        {label}
                      </Table.ColumnHeader>
                    ))}
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {vehicles.map((row) => (
                    <Table.Row key={row.id}>
                      <Table.Cell>
                        {row.name}
                        <Text fontSize="xs">
                          {row.year} · {row.engine} · {row.variant} ·{" "}
                          {row.powertrain}
                        </Text>
                        {!row.model_id && (
                          <Text fontSize="xs" color="orange.700">
                            Link this legacy scope to a model to enable mobile
                            registration.
                          </Text>
                        )}
                      </Table.Cell>
                      <Table.Cell>
                        {row.active ? "Active" : "Inactive"}
                      </Table.Cell>
                      <Table.Cell>
                        {row.manual_available ? "Published" : "Not available"}
                      </Table.Cell>
                      <Table.Cell>
                        {row.manufacturer_schedule_available
                          ? "Published"
                          : "Not configured"}
                      </Table.Cell>
                      <Table.Cell>
                        <Flex gap={2}>
                          <Button
                            disabled={busy}
                            size="sm"
                            onClick={() => {
                              setVehicleId(row.id);
                              setVehicle({
                                code: row.code,
                                name: row.name,
                                model_id: row.model_id || "",
                                year: row.year,
                                engine: row.engine,
                                variant: row.variant,
                                powertrain: row.powertrain,
                                active: row.active,
                                published: row.published,
                              });
                            }}
                          >
                            Edit
                          </Button>
                          <Button size="sm" variant="outline" asChild>
                            <NextLink
                              href={`/user/schedules?vehicle=${row.id}`}
                            >
                              Schedules
                            </NextLink>
                          </Button>
                        </Flex>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
            {!vehicles.length && (
              <Text>
                No matching vehicles. Add manufacturers and models above to
                create a variant.
              </Text>
            )}
          </>
        )}
      </Stack>
    </AdminLayout>
  );
}
