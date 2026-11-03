import { request, listAll } from "./client.mjs";
import { API_URL } from "../lib/config.mjs";

export const listDocuments = () => listAll("/documents");
export function uploadDocument(file, metadata) {
  const body = new FormData();
  body.append("file", file);
  body.append("name", metadata.name);
  body.append("tags", JSON.stringify(metadata.tags));
  body.append("document_type", metadata.documentType || "other_reference");
  return request("/documents", { method: "POST", body });
}
export const editDocument = (id, data) => request(`/documents/${id}`, {
  method: "PATCH", body: { name: data.name, tags: data.tags, document_type: data.documentType },
});
export async function saveDocumentCoverage(id, coverage) {
  const { vehicle_ids, category_ids, ...metadata } = coverage;
  await request(`/documents/${id}`, { method: "PATCH", body: metadata });
  return request(`/knowledge/documents/${id}/associations`, {
    method: "PUT", body: { vehicle_ids, category_ids },
  });
}
export const changeDocumentTag = (tag, replacement = null) => request("/documents/tags/change", {
  method: "POST", body: { tag, replacement },
});
export function replaceDocument(id, file) {
  const body = new FormData();
  body.append("file", file);
  return request(`/documents/${id}/replace`, { method: "POST", body });
}
export const deleteDocument = (id) => request(`/documents/${id}`, { method: "DELETE" });
export const processDocuments = (ids, force = false) => request("/documents/process-batch", { method: "POST", body: { ids, force } });
export const downloadDocumentUrl = (id) => `${API_URL}/documents/${id}/download`;
export const originalDocumentUrl = (id, revision = null) => `${API_URL}/documents/${id}/original${revision ? `?revision=${encodeURIComponent(revision)}` : ""}`;
export const publishDocument = (id) => request(`/documents/${id}/publish`, { method: "POST", body: { confirm_review: true } });
export const unpublishDocument = (id) => request(`/documents/${id}`, { method: "PATCH", body: { published: false } });
export function stageReplacement(id, file) {
  const body = new FormData();
  body.append("file", file);
  return request(`/documents/${id}/stage-replacement`, { method: "POST", body });
}
