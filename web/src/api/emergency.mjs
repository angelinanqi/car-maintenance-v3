import { request, listAll } from "./client.mjs";

export function validImageUrl(value) {
  if (!value) return true;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && Boolean(url.hostname) && !url.username && !url.password && !/\s/.test(value);
  } catch { return false; }
}

function validIdentity(row) {
  return row && typeof row.id === "string" && typeof row.updated_at === "string" && Number.isFinite(Date.parse(row.updated_at));
}

function playbook(row) {
  if (!validIdentity(row) || typeof row.title !== "string" || !row.title.trim() || !["draft", "published"].includes(row.status) ||
      !Number.isInteger(row.display_order) || row.display_order < 0 ||
      !["source", "category", "description", "safety_warnings"].every(key => typeof row[key] === "string") ||
      !Array.isArray(row.steps) || row.steps.length > 100 || row.steps.some(step => !step || typeof step.id !== "string" || typeof step.title !== "string" || typeof step.description !== "string" || typeof step.imageUrl !== "string" || !validImageUrl(step.imageUrl))) {
    throw new Error("Emergency guide data could not be read. Your edits are kept. Refresh the guides and retry.");
  }
  return row;
}

function contact(row) {
  if (!validIdentity(row) || typeof row.name !== "string" || !row.name.trim() || typeof row.phone !== "string" ||
      !/^[+\d\s().-]+$/.test(row.phone) || row.phone.replace(/\D/g, "").length < 3 ||
      typeof row.description !== "string" || !Number.isInteger(row.display_order) || row.display_order < 0) {
    throw new Error("Emergency contact data could not be read. Your edits are kept. Refresh the contacts and retry.");
  }
  return row;
}

export const listPlaybooks = async () => (await listAll("/emergency/playbooks", { include_drafts: "true" })).map(playbook);
export const publishPlaybook = async (id, updatedAt) => playbook(await request(`/emergency/playbooks/${id}/publish`, { method: "POST", body: { confirm_review: true, expected_updated_at: updatedAt } }));
export const savePlaybook = async (id, body) => playbook(await request(id ? `/emergency/playbooks/${id}` : "/emergency/playbooks", { method: id ? "PATCH" : "POST", body }));
export const listContacts = async () => (await listAll("/emergency/contacts")).map(contact);
export const saveContact = async (id, body) => contact(await request(id ? `/emergency/contacts/${id}` : "/emergency/contacts", { method: id ? "PATCH" : "POST", body }));

async function remove(path, updatedAt) {
  if (!updatedAt) throw new Error("Reload this record before deleting it.");
  try {
    return await request(`${path}?${new URLSearchParams({ expected_updated_at: updatedAt })}`, { method: "DELETE" });
  } catch (error) {
    if (error.status !== 404) throw error;
    return null;
  }
}
export const deletePlaybook = (id, updatedAt) => remove(`/emergency/playbooks/${id}`, updatedAt);
export const deleteContact = (id, updatedAt) => remove(`/emergency/contacts/${id}`, updatedAt);
