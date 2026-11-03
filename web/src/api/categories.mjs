import { request, listAll } from "./client.mjs";
export const listCategories = () => listAll("/categories", { include_drafts: "true" });
export const saveCategory = (id, body) => request(id ? `/categories/${id}` : "/categories", { method: id ? "PATCH" : "POST", body });
export const categoryRemovalImpact = (id, signal) => request(`/categories/${id}/removal-impact`, { signal });
export const deleteCategory = (id, body) => request(`/categories/${id}`, { method: "DELETE", body });
export const archiveCategory = (id) => request(`/categories/${id}/archive`, { method: "POST" });
export const restoreCategory = (id) => request(`/categories/${id}/restore`, { method: "POST" });
