import { API_URL, API_PAGE_SIZE } from "../lib/config.mjs";

let csrfToken = "";
export function setCsrfToken(value) { csrfToken = value || ""; }

export async function request(path, { method = "GET", body, signal } = {}) {
  method = method.toUpperCase();
  const hasBody = body !== undefined;
  const multipart = body instanceof FormData;
  const requestCsrf = csrfToken;
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method, signal, credentials: "include", cache: "no-store",
      headers: {
        ...(hasBody && !multipart ? { "Content-Type": "application/json" } : {}),
        ...(method !== "GET" && csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body: hasBody ? (multipart ? body : JSON.stringify(body)) : undefined,
    });
  } catch (cause) {
    if (signal?.aborted) throw cause;
    throw new Error("Could not connect to Roadie. Check your connection and try again. Your changes have not been confirmed.");
  }
  if (response.status === 204) return null;
  let result;
  try {
    result = await response.json();
  } catch {
    if (response.ok) throw new Error("The backend returned an unexpected response. Your changes have not been confirmed.");
  }
  if (!response.ok) {
    const detail = result?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => {
        const field = Array.isArray(item?.loc) ? item.loc.slice(1).join(".") : "";
        return `${field ? `${field}: ` : ""}${typeof item?.msg === "string" ? item.msg : "Invalid input"}`;
      }).join("; ")
      : detail;
    const error = new Error(typeof message === "string" ? message : `Request failed (${response.status}). Please retry.`);
    error.status = response.status;
    if (response.status === 401 && !path.startsWith("/accounts/") && requestCsrf === csrfToken && typeof window !== "undefined") window.dispatchEvent(new Event("session-expired"));
    throw error;
  }
  if (result === null || typeof result !== "object") {
    throw new Error("The backend returned an unexpected response. Your changes have not been confirmed.");
  }
  return result;
}

export async function listAll(path, filters = {}) {
  const rows = [];
  while (true) {
    const query = new URLSearchParams({ ...filters, offset: String(rows.length), limit: String(API_PAGE_SIZE) });
    const page = await request(`${path}?${query}`);
    if (!Array.isArray(page)) throw new Error("The backend returned an unexpected list response.");
    rows.push(...page);
    if (page.length < API_PAGE_SIZE) return rows;
  }
}
