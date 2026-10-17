export function vehicleAvailability(vehicle, models, manufacturers) {
  if (!vehicle.model_id) return "Link a model";
  const model = models.find((row) => row.id === vehicle.model_id);
  const manufacturer = manufacturers.find(
    (row) => row.id === model?.manufacturer_id,
  );
  if (!model || !manufacturer) return "Catalogue link missing";
  if (!vehicle.active) return "Vehicle inactive";
  if (!model.active) return "Model inactive";
  if (!manufacturer.active) return "Manufacturer inactive";
  if (
    !/^\d+$/.test(vehicle.year) ||
    Number(vehicle.year) < 1900 ||
    Number(vehicle.year) > 2100
  )
    return "Set a model year";
  return "Available in Roadie";
}

export function suggestVehicleCode(manufacturer, model, year, variant) {
  return [manufacturer, model, year, variant]
    .filter(Boolean)
    .join("-")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
