function validDraft(kind, value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  if (kind === "playbook") {
    return typeof value.title === "string" && Array.isArray(value.steps) && value.steps.length <= 100 &&
      value.steps.every(step => step && ["id", "title", "description", "imageUrl"].every(key => typeof step[key] === "string")) &&
      ["category", "description", "source", "safety_warnings", "client_id", "id", "updated_at"].every(key => value[key] === undefined || value[key] === null || typeof value[key] === "string");
  }
  return typeof value.name === "string" && typeof value.phone === "string" &&
    (value.description === undefined || typeof value.description === "string") &&
    (value.display_order === undefined || (typeof value.display_order === "number" && Number.isFinite(value.display_order))) &&
    (value.id === undefined || typeof value.id === "string") &&
    (value.base_updated_at === undefined || value.base_updated_at === null || typeof value.base_updated_at === "string");
}

const keyFor = (owner, kind, id) => `emergency-draft:${owner}:${kind}:${id}`;
const memoryCopies = new Map();

export const emergencyDraftIsPersistent = (owner, kind, id = "") => memoryCopies.get(keyFor(owner, kind, id))?.persistent !== false;

export function readEmergencyDraft(storage, owner, kind, id = "") {
  const key = keyFor(owner, kind, id);
  if (memoryCopies.has(key)) return memoryCopies.get(key).value;
  const raw = storage.getItem(key);
  if (!raw) return null;
  const value = JSON.parse(raw);
  if (!validDraft(kind, value)) throw new Error("Invalid Emergency recovery copy");
  return value;
}

export function writeEmergencyDraft(storage, owner, kind, id, value) {
  if (value !== null && !validDraft(kind, value)) throw new Error("Invalid Emergency recovery copy");
  const key = keyFor(owner, kind, id);
  // Keep a tab-lifetime copy even if session storage is blocked or full.
  memoryCopies.set(key, { value, persistent: false });
  if (value === null) storage.removeItem(key);
  else storage.setItem(key, JSON.stringify(value));
  if (value === null) memoryCopies.delete(key);
  else memoryCopies.set(key, { value, persistent: true });
}
