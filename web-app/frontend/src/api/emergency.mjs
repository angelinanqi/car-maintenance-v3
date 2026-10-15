import { request, listAll } from "./client.mjs";
export const listPlaybooks = () => listAll("/emergency/playbooks", { include_drafts: "true" });
export const publishPlaybook = (id) => request(`/emergency/playbooks/${id}/publish`, { method: "POST", body: { confirm_review: true } });
export const savePlaybook = (id, body) => request(id ? `/emergency/playbooks/${id}` : "/emergency/playbooks", { method: id ? "PATCH" : "POST", body });
export const deletePlaybook = (id) => request(`/emergency/playbooks/${id}`, { method: "DELETE" });
export const listContacts = () => listAll("/emergency/contacts");
export const saveContact = (id, body) => request(id ? `/emergency/contacts/${id}` : "/emergency/contacts", { method: id ? "PATCH" : "POST", body });
export const deleteContact = (id) => request(`/emergency/contacts/${id}`, { method: "DELETE" });
