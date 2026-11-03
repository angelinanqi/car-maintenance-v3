import { request, listAll } from "./client.mjs";
export const listGuides = () => listAll("/guides", { include_drafts: "true" });
export const saveGuide = (id, body) => request(id ? `/guides/${id}` : "/guides", { method: id ? "PATCH" : "POST", body });
export const deleteGuide = (id) => request(`/guides/${id}`, { method: "DELETE" });
export const publishGuide = (id) => request(`/guides/${id}/publish`, { method: "POST" });
export const guideIndexStatus = (id) => request(`/guides/${id}/index-status`);
export const retryGuideIndexing = (id) => request(`/guides/${id}/retry-indexing`, { method: "POST" });
export function uploadGuideImage(id, file) {
  const body = new FormData();
  body.append("file", file);
  return request(`/guides/${id}/images`, { method: "POST", body });
}
