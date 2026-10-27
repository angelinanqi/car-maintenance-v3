"use client";

import { Checkbox } from "@/components/ui/checkbox";

import { useState, type FormEvent } from "react";
import { Box, Button, Collapsible, Grid, Input, Text } from "@chakra-ui/react";
import RecordDialog from "./RecordDialog";
import FormField from "./FormField";
import { AdminSelect } from "./NativeControls";
import { suggestVehicleCode } from "@/lib/catalogue.mjs";
import {
  saveManufacturer,
  saveModel,
  saveVehicle,
  type Catalogue,
  type Manufacturer,
  type VehicleModel,
  type Vehicle,
} from "@/api/admin";

type CommonProps<T> = {
  row?: T;
  onClose: () => void;
  onSaved: (row: T) => void;
};

export function ManufacturerEditor({
  row,
  onClose,
  onSaved,
}: CommonProps<Manufacturer>) {
  const original = { name: row?.name || "", active: row?.active ?? true };
  const [draft, setDraft] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!draft.name.trim()) {
      setError("Enter a manufacturer name.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onSaved(
        await saveManufacturer(row?.id || "", {
          ...draft,
          name: draft.name.trim(),
        }),
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <RecordDialog
      title={row ? "Edit manufacturer" : "Add manufacturer"}
      description="A manufacturer is the vehicle make, such as Perodua. Models and vehicle variants belong beneath it."
      busy={busy}
      dirty={JSON.stringify(draft) !== JSON.stringify(original)}
      error={error}
      onClose={onClose}
      onSubmit={submit}
      saveLabel={row ? "Save manufacturer" : "Add manufacturer"}
    >
      <FormField label="Manufacturer name">
        <Input
          required
          maxLength={100}
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          placeholder="e.g. Perodua"
        />
      </FormField>
      <Checkbox
        checked={draft.active}
        onCheckedChange={(e) =>
          setDraft({ ...draft, active: e.checked === true })
        }
      >
        Available for new vehicle selections
        <Text color="muted" fontSize="sm" mt={2}>
          Turning this off hides all models and variants under this manufacturer
          from new selections in Roadie. Existing records are kept.
        </Text>
      </Checkbox>
    </RecordDialog>
  );
}

export function ModelEditor({
  row,
  data,
  onClose,
  onSaved,
  initialManufacturerId = "",
}: CommonProps<VehicleModel> & {
  data: Catalogue;
  initialManufacturerId?: string;
}) {
  const original = {
    name: row?.name || "",
    manufacturer_id: row?.manufacturer_id || initialManufacturerId,
    active: row?.active ?? true,
  };
  const [draft, setDraft] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const maker = data.manufacturers.find((m) => m.id === draft.manufacturer_id);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!draft.name.trim()) {
      setError("Enter a model name.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onSaved(
        await saveModel(row?.id || "", { ...draft, name: draft.name.trim() }),
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <RecordDialog
      title={row ? "Edit model" : "Add model"}
      description="A model is a vehicle family, such as Myvi. Add year, engine and trim details as vehicle variants."
      busy={busy}
      dirty={JSON.stringify(draft) !== JSON.stringify(original)}
      error={error}
      onClose={onClose}
      onSubmit={submit}
      saveLabel={row ? "Save model" : "Add model"}
    >
      <FormField
        label="Manufacturer"
        hint={
          row
            ? "The manufacturer cannot be changed after creation. Add a new model if it belongs to a different make."
            : "Choose the make this model belongs to."
        }
      >
        <AdminSelect
          required
          disabled={Boolean(row)}
          value={draft.manufacturer_id}
          onChange={(e) =>
            setDraft({ ...draft, manufacturer_id: e.target.value })
          }
        >
          <option value="">Choose a manufacturer</option>
          {data.manufacturers.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
              {m.active ? "" : " (inactive)"}
            </option>
          ))}
        </AdminSelect>
      </FormField>
      <FormField label="Model name">
        <Input
          required
          maxLength={100}
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          placeholder="e.g. Myvi"
        />
      </FormField>
      <Checkbox
        checked={draft.active}
        onCheckedChange={(e) =>
          setDraft({ ...draft, active: e.checked === true })
        }
      >
        Available for new vehicle selections
        <Text fontSize="sm" color="muted" mt={2}>
          Turning this off hides the model and its variants from new selections
          in Roadie. Existing records are kept.
        </Text>
      </Checkbox>
      {maker && !maker.active && (
        <Text bg="brand.50" p={3}>
          This manufacturer is inactive. Activating the model alone will not
          make it available in Roadie.
        </Text>
      )}
    </RecordDialog>
  );
}

export function VehicleEditor({
  row,
  data: initialCatalogue,
  onClose,
  onSaved,
}: CommonProps<Vehicle> & { data: Catalogue }) {
  const [data, setData] = useState(initialCatalogue);
  const [adding, setAdding] = useState<"manufacturer" | "model" | null>(null);
  const original = {
    name: row?.name || "",
    model_id: row?.model_id || "",
    year: row?.year || "",
    engine: row?.engine || "",
    variant: row?.variant || "",
    powertrain: row?.powertrain || "petrol",
    active: row?.active ?? true,
    published: row?.published ?? false,
    code: row?.code || "",
  };
  const [draft, setDraft] = useState(original);
  const [manufacturerId, setManufacturerId] = useState(
    data.models.find((m) => m.id === row?.model_id)?.manufacturer_id || "",
  );
  const [customCode, setCustomCode] = useState(Boolean(row));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const manufacturer = data.manufacturers.find((m) => m.id === manufacturerId);
  const model = data.models.find((m) => m.id === draft.model_id);
  const generatedCode = suggestVehicleCode(
    manufacturer?.name,
    model?.name,
    draft.year,
    [draft.engine, draft.variant].filter(Boolean).join(" "),
  );
  const code = customCode ? draft.code : generatedCode;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const problems: Record<string, string> = {};
    if (!draft.name.trim())
      problems.name = "Enter the name drivers should see.";
    if (!draft.model_id)
      problems.model_id =
        "Choose a model, or add the missing model using the button below.";
    if (
      !/^\d{4}$/.test(draft.year) ||
      Number(draft.year) < 1900 ||
      Number(draft.year) > 2100
    )
      problems.year = "Use a single year between 1900 and 2100.";
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(code))
      problems.code =
        "Use lowercase letters and numbers, separated by hyphens.";
    if (data.vehicles.some((v) => v.id !== row?.id && v.code === code))
      problems.code =
        "This internal code is already in use. Add a trim or change the code below.";
    setErrors(problems);
    if (Object.keys(problems).length) {
      setError("Check the highlighted fields before saving.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const saved = await saveVehicle(row?.id || "", {
        ...draft,
        name: draft.name.trim(),
        code,
        model_id: draft.model_id,
      });
      onSaved({
        ...row,
        manual_available: row?.manual_available ?? false,
        manufacturer_schedule_available:
          row?.manufacturer_schedule_available ?? false,
        ...saved,
      });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <RecordDialog
        title={row ? "Edit vehicle details" : "Add a vehicle"}
        description="Identify the exact car drivers will select. After saving, you can add its manuals and service schedule from the vehicle overview."
        busy={busy}
        dirty={
          JSON.stringify(draft) !== JSON.stringify(original) ||
          (!row && Boolean(manufacturerId))
        }
        error={error}
        onClose={onClose}
        onSubmit={submit}
        saveLabel={row ? "Save vehicle" : "Add vehicle"}
      >
        <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={4}>
          <FormField label="Manufacturer">
            <AdminSelect
              required
              disabled={Boolean(row?.model_id)}
              value={manufacturerId}
              onChange={(e) => {
                setManufacturerId(e.target.value);
                setDraft({ ...draft, model_id: "" });
              }}
            >
              <option value="">Choose manufacturer</option>
              {data.manufacturers.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                  {m.active ? "" : " (inactive)"}
                </option>
              ))}
            </AdminSelect>
          </FormField>
          <FormField
            label="Model"
            error={errors.model_id}
            hint={
              row?.model_id
                ? "The model is fixed for an existing variant."
                : manufacturerId
                  ? "Only models from the selected manufacturer are shown."
                  : "Choose a manufacturer first."
            }
          >
            <AdminSelect
              required
              disabled={!manufacturerId || Boolean(row?.model_id)}
              value={draft.model_id}
              onChange={(e) => setDraft({ ...draft, model_id: e.target.value })}
            >
              <option value="">Choose model</option>
              {data.models
                .filter((m) => m.manufacturer_id === manufacturerId)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.active ? "" : " (inactive)"}
                  </option>
                ))}
            </AdminSelect>
          </FormField>
          {!row && (
            <Box>
              <Button
                type="button"
                variant="plain"
                size="sm"
                onClick={() => setAdding("manufacturer")}
              >
                Manufacturer missing? Add it here
              </Button>
            </Box>
          )}
          {!row && manufacturerId && (
            <Box>
              <Button
                type="button"
                variant="plain"
                size="sm"
                onClick={() => setAdding("model")}
              >
                Add missing model
              </Button>
            </Box>
          )}
        </Grid>
        {manufacturerId &&
          !data.models.some((m) => m.manufacturer_id === manufacturerId) && (
            <Text bg="brand.50" p={3}>
              No models have been added for this manufacturer. Use “Add missing
              model” above to continue here.
            </Text>
          )}
        <FormField
          label="Name shown to drivers"
          hint="Include enough detail to distinguish this variant, for example Myvi 1.5 AV (2022)."
          error={errors.name}
        >
          <Input
            required
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
        </FormField>
        <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={4}>
          <FormField label="Model year" error={errors.year}>
            <Input
              required
              inputMode="numeric"
              maxLength={4}
              value={draft.year}
              onChange={(e) => setDraft({ ...draft, year: e.target.value })}
              placeholder="e.g. 2022"
            />
          </FormField>
          <FormField label="Fuel type">
            <AdminSelect
              value={draft.powertrain}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  powertrain: e.target.value as Vehicle["powertrain"],
                })
              }
            >
              <option value="petrol">Petrol</option>
              <option value="diesel">Diesel</option>
            </AdminSelect>
          </FormField>
          <FormField
            label="Engine (optional)"
            hint="Copy this from the manual, for example 1.5 L. Leave blank if you need to confirm it."
          >
            <Input
              value={draft.engine}
              onChange={(e) => setDraft({ ...draft, engine: e.target.value })}
            />
          </FormField>
          <FormField
            label="Trim / transmission (optional)"
            hint="For example AV / D-CVT."
          >
            <Input
              value={draft.variant}
              onChange={(e) => setDraft({ ...draft, variant: e.target.value })}
            />
          </FormField>
        </Grid>
        <Box bg="canvas" p={4} borderRadius="8px">
          <Checkbox
            checked={draft.active}
            onCheckedChange={(e) =>
              setDraft({ ...draft, active: e.checked === true })
            }
          >
            Available for new selections in Roadie
          </Checkbox>
          <Text fontSize="sm" color="muted" mt={2}>
            The manufacturer and model must also be active. Turning this off
            keeps existing vehicles, records and source links.
          </Text>
        </Box>
        {draft.active &&
          ((manufacturer && !manufacturer.active) ||
            (model && !model.active)) && (
            <Text bg="brand.50" p={3}>
              The parent manufacturer or model is inactive. This vehicle will
              remain unavailable to new selections until both are active.
            </Text>
          )}
        <Box bg="canvas" p={4} borderRadius="8px">
          <Checkbox
            checked={draft.published}
            onCheckedChange={(e) =>
              setDraft({ ...draft, published: e.checked === true })
            }
          >
            Offer this vehicle in the chatbot
          </Checkbox>
          <Text fontSize="sm" color="muted" mt={2}>
            Drivers can ask questions about this vehicle once its reference
            documents or other supported content are published. You can check
            availability in the vehicle overview.
          </Text>
        </Box>
        <Collapsible.Root
          key={errors.code || "code"}
          defaultOpen={Boolean(errors.code)}
        >
          <Collapsible.Trigger asChild>
            <Button variant="outline" type="button">
              Internal code
            </Button>
          </Collapsible.Trigger>
          <Collapsible.Content pt={3}>
            <FormField
              label="Unique code"
              error={errors.code}
              hint={
                row
                  ? "The code is permanent because the mobile manual catalogue uses it. Create another variant for a different identity."
                  : "Suggested from the manufacturer, model, year and trim. Change it if another configuration uses the same code."
              }
            >
              <Input
                value={code}
                readOnly={Boolean(row)}
                onChange={(e) => {
                  setCustomCode(true);
                  setDraft({ ...draft, code: e.target.value });
                }}
              />
            </FormField>
          </Collapsible.Content>
        </Collapsible.Root>
      </RecordDialog>
      {adding === "manufacturer" && (
        <ManufacturerEditor
          onClose={() => setAdding(null)}
          onSaved={(manufacturer) => {
            setData((previous) => ({
              ...previous,
              manufacturers: [...previous.manufacturers, manufacturer],
            }));
            setManufacturerId(manufacturer.id);
            setDraft((previous) => ({ ...previous, model_id: "" }));
            setAdding(null);
          }}
        />
      )}
      {adding === "model" && (
        <ModelEditor
          data={data}
          initialManufacturerId={manufacturerId}
          onClose={() => setAdding(null)}
          onSaved={(model) => {
            setData((previous) => ({
              ...previous,
              models: [...previous.models, model],
            }));
            setDraft((previous) => ({ ...previous, model_id: model.id }));
            setManufacturerId(model.manufacturer_id);
            setAdding(null);
          }}
        />
      )}
    </>
  );
}
