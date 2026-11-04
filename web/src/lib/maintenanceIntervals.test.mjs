import test from "node:test";
import assert from "node:assert/strict";
import { currentSchedules, taskIntervals } from "./maintenanceIntervals.mjs";

const schedule = (id, vehicle_id, revision, status, itemId = "oil") => ({
  id, vehicle_id, revision, status,
  entries: [{ itemId: "other", rule: {} }, { itemId, rule: { distanceKm: 10000 } }],
});

test("keeps the driver schedule and newest draft without displaying previous revisions", () => {
  const rows = [schedule("old", "car", 1, "superseded"),
    schedule("draft2", "car", 2, "draft"), schedule("live", "car", 3, "published"),
    schedule("draft4", "car", 4, "draft")];
  assert.deepEqual(currentSchedules(rows).map((row) => row.id), ["draft4", "live"]);
});

test("vehicle and item selection keep intervals scoped and link to the actual task position", () => {
  const rows = [schedule("car-oil", "car", 1, "published"),
    schedule("van-oil", "van", 1, "published"), schedule("car-tyres", "car", 2, "draft", "tyres")];
  const matches = taskIntervals(rows, "oil", "car");
  assert.equal(matches.length, 1);
  assert.equal(matches[0].schedule.id, "car-oil");
  assert.equal(matches[0].index, 1);
  assert.equal(taskIntervals(rows, "oil").length, 2);
  assert.deepEqual(taskIntervals(rows, "oil", "missing"), []);
});
