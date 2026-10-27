import { request, listAll } from "./client.mjs";
export const listCategories = () => listAll("/categories", { include_drafts: "true" });
export const saveCategory = (id, body) => request(id ? `/categories/${id}` : "/categories", { method: id ? "PATCH" : "POST", body });
export const deleteCategory = (id) => request(`/categories/${id}`, { method: "DELETE" });
