import { API_URL, API_PAGE_SIZE } from "../lib/config.mjs";

let csrfToken = "";
export function setCsrfToken(value) { csrfToken = value || ""; }

export async function request(path, { method = "GET", body, signal } = {}) {
  const multipart = body instanceof FormData;
  const requestCsrf = csrfToken;
  const response = await fetch(`${API_URL}${path}`, {
    method, signal, credentials: "include", cache: "no-store",
    headers: {
      ...(body && !multipart ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" && csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    },
    body: body ? (multipart ? body : JSON.stringify(body)) : undefined,
  });
  if (response.status === 204) return null;
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = result?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc.slice(1).join(".")}: ${item.msg}`).join("; ")
      : detail;
    const error = new Error(typeof message === "string" ? message : `Request failed (${response.status}). Please retry.`);
    error.status = response.status;
    if (response.status === 401 && !path.startsWith("/accounts/") && requestCsrf === csrfToken && typeof window !== "undefined") window.dispatchEvent(new Event("session-expired"));
    throw error;
  }
  return result;
}

export async function listAll(path, filters = {}) {
  const rows = [];
  while (true) {
    const query = new URLSearchParams({ ...filters, offset: String(rows.length), limit: String(API_PAGE_SIZE) });
    const page = await request(`${path}?${query}`);
    rows.push(...page);
    if (page.length < API_PAGE_SIZE) return rows;
  }
}
