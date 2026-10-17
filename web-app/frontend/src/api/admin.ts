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
export type MaintenanceItem = {
  id: string;
  title: string;
  category: string;
  description: string;
  action: "inspect" | "replace" | "service";
  active: boolean;
};
export type Rule = {
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
};
export type SourceDocument = {
  id: string;
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
export const saveManufacturer = (id: string, body: Omit<Manufacturer, "id">) =>
  request(id ? `/admin/manufacturers/${id}` : "/admin/manufacturers", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveModel = (id: string, body: Omit<VehicleModel, "id">) =>
  request(id ? `/admin/models/${id}` : "/admin/models", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveVehicle = (
  id: string,
  body: Omit<
    Vehicle,
    "id" | "manual_available" | "manufacturer_schedule_available"
  >,
) =>
  request(id ? `/knowledge/vehicles/${id}` : "/knowledge/vehicles", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveItem = (id: string, body: Omit<MaintenanceItem, "id">) =>
  request(id ? `/admin/maintenance-items/${id}` : "/admin/maintenance-items", {
    method: id ? "PATCH" : "POST",
    body,
  });
export const saveSchedule = (
  id: string,
  vehicle_id: string,
  entries: ScheduleEntry[],
): Promise<Schedule> =>
  request(id ? `/admin/schedules/${id}` : "/admin/schedules", {
    method: id ? "PATCH" : "POST",
    body: { vehicle_id, entries },
  });
export const validateSchedule = (
  id: string,
): Promise<{ valid: boolean; message: string }> =>
  request(`/admin/schedules/${id}/validate`, { method: "POST" });
export const publishSchedule = (id: string): Promise<Schedule> =>
  request(`/admin/schedules/${id}/publish`, {
    method: "POST",
    body: { confirm_review: true },
  });
export const withdrawSchedule = (id: string): Promise<Schedule> =>
  request(`/admin/schedules/${id}/withdraw`, { method: "POST" });
export const deleteDraftSchedule = (id: string): Promise<void> =>
  request(`/admin/schedules/${id}`, { method: "DELETE" });
