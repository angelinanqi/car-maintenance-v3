// Show the current driver schedule and the newest working draft for each car.
export function currentSchedules(schedules) {
  const current = new Map();
  for (const schedule of schedules) {
    if (!["draft", "published"].includes(schedule.status)) continue;
    const key = `${schedule.vehicle_id}:${schedule.status}`;
    if (!current.has(key) || current.get(key).revision < schedule.revision)
      current.set(key, schedule);
  }
  return [...current.values()];
}

export function taskIntervals(schedules, itemId, vehicleId = "") {
  return currentSchedules(schedules)
    .filter((schedule) => !vehicleId || schedule.vehicle_id === vehicleId)
    .flatMap((schedule) => schedule.entries.flatMap((entry, index) =>
      entry.itemId === itemId ? [{ schedule, entry, index }] : []));
}
