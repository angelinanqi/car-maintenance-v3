import { request, listAll } from "./client.mjs";

export type Manufacturer = { id: string; name: string; active: boolean };
export type VehicleModel = Manufacturer & { manufacturer_id: string };
export type Vehicle = {
  id: string;
  code: string;
  name: string;
  model_id: string | null;
  year: string;
  engine: string;
  variant: string;
  powertrain: "petrol" | "diesel";
  active: boolean;
  published: boolean;
  manual_available: boolean;
  manufacturer_schedule_available: boolean;
};
export type Catalogue = {
  manufacturers: Manufacturer[];
  models: VehicleModel[];
  vehicles: Vehicle[];
};
export type CatalogueKind = "manufacturers" | "models" | "vehicles";
export type CatalogueDeletionImpact = {
  kind: CatalogueKind;
  entry: Manufacturer;
  references: Record<string, number>;
  deletable: boolean;
  fingerprint: string;
  blockers: { key: string; label: string; count: number; href: string | null;
    items: { name: string; href: string }[] }[];
};
export const catalogueDeletionPreview = (kind: CatalogueKind, id: string, signal?: AbortSignal): Promise<CatalogueDeletionImpact> =>
  request(`/admin/catalogue/${kind}/${id}/deletion-preview`, { signal });
export const deleteCatalogueEntry = (kind: CatalogueKind, id: string, fingerprint: string): Promise<void> =>
  request(`${kind === "vehicles" ? "/knowledge" : "/admin"}/${kind}/${id}`, {
    method: "DELETE", body: { fingerprint },
  });
export const deactivateCatalogueEntry = (kind: CatalogueKind, id: string): Promise<Manufacturer> =>
  request(`/admin/catalogue/${kind}/${id}/deactivate`, { method: "POST" });
export type MaintenanceItem = {
  id: string;
  title: string;
  category: string;
  description: string;
  action: "inspect" | "replace" | "service";
  active: boolean;
};
type Rule = {
  type: "recurring" | "milestone" | "informational";
  distanceKm: number | null;
  months: number | null;
  distanceMilestones: number[];
  monthMilestones: number[];
  vehicleStartDate: string | null;
  conditions: string;
  notes: string;
  sourceDocumentId: string | null;
  sourcePage: number | null;
  sourceRevision?: string | null;
  sourceTableId?: string | null;
  sourceSuggestionId?: string | null;
};
export type ScheduleEntry = {
  itemId: string | null;
  action: MaintenanceItem["action"];
  rule: Rule;
};
export type Schedule = {
  id: string;
  vehicle_id: string;
  revision: number;
  status: "draft" | "published" | "superseded";
  entries: ScheduleEntry[];
  verified_at: string | null;
  admin_note?: string;
  work_context?: {
    document_id?: string | null;
    source_revision?: string | null;
    page?: number;
  };
  updated_at?: string;
};
export type SourceDocument = {
  id: string;
  source_revision: string;
  superseded_by_id?: string | null;
  replacement_for_id?: string | null;
  name: string;
  source_type: string;
  document_type: string;
  status: string;
  published: boolean;
};

export const loadCatalogue = (): Promise<Catalogue> =>
  request("/admin/catalogue");
export const loadItems = (): Promise<MaintenanceItem[]> =>
  listAll("/admin/maintenance-items");
export const loadSchedules = (vehicleId: string): Promise<Schedule[]> =>
  listAll("/admin/schedules", { vehicle_id: vehicleId });
export const saveManufacturer = (id: string, body: Omit<Manufacturer, "id"> & { id?: string }) =>
  request(id ? `/admin/manufacturers/${id}` : "/admin/manufacturers", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveModel = (id: string, body: Omit<VehicleModel, "id"> & { id?: string }) =>
  request(id ? `/admin/models/${id}` : "/admin/models", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveVehicle = (
  id: string,
  body: Omit<
    Vehicle,
    "id" | "manual_available" | "manufacturer_schedule_available"
  > & { id?: string },
) =>
  request(id ? `/knowledge/vehicles/${id}` : "/knowledge/vehicles", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveItem = (id: string, body: Omit<MaintenanceItem, "id"> & { id?: string }) =>
  request(id ? `/admin/maintenance-items/${id}` : "/admin/maintenance-items", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveSchedule = (
  id: string,
  vehicle_id: string,
  entries: ScheduleEntry[],
  admin_note = "",
  work_context: Schedule["work_context"] = {},
  createId?: string,
  expectedUpdatedAt?: string,
): Promise<Schedule> =>
  request(id ? `/admin/schedules/${id}` : "/admin/schedules", {
    method: id ? "PATCH" : "POST",
    body: { vehicle_id, entries, admin_note, work_context,
      ...(id ? { expected_updated_at: expectedUpdatedAt } : { id: createId }) },
  });
export const validateSchedule = (
  id: string,
): Promise<{ valid: boolean; message: string }> =>
  request(`/admin/schedules/${id}/validate`, { method: "POST" });
export const publishSchedule = (id: string, expectedUpdatedAt?: string): Promise<Schedule> =>
  request(`/admin/schedules/${id}/publish`, {
    method: "POST",
    body: { confirm_review: true, expected_updated_at: expectedUpdatedAt },
  });
export const withdrawSchedule = (id: string, expectedUpdatedAt?: string): Promise<Schedule> =>
  request(`/admin/schedules/${id}/withdraw`, { method: "POST", body: { expected_updated_at: expectedUpdatedAt } });
export const deleteDraftSchedule = (id: string, expectedUpdatedAt?: string): Promise<void> =>
  request(`/admin/schedules/${id}?${new URLSearchParams({ expected_updated_at: expectedUpdatedAt || '' })}`, { method: "DELETE" });
