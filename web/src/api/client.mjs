import { API_URL, API_PAGE_SIZE } from "../lib/config.mjs";

let requestIdentity = "";
export function setRequestIdentity(value) { requestIdentity = value || ""; }

function maintenancePath(path) {
  return /^\/admin\/(catalogue|manufacturers|models|maintenance-items|schedules|schedule-drafts|maintenance-assistance)([/?]|$)/.test(path) ||
    /^\/knowledge\/(vehicles|manage)([/?]|$)/.test(path);
}

function defaultTimeout(path) {
  if (path === '/chat') return 270000;
  if (path === '/chat/mechanic-questions') return 55000;
  if (path.startsWith('/chat/sessions/')) return 60000;
  if (path.startsWith('/mobile/') || /^\/admin\/(chat-starters|companion-settings)([/?]|$)/.test(path)) return 30000;
  if (path.startsWith('/emergency/') || path.startsWith('/accounts/') || maintenancePath(path)) return 30000;
  return undefined;
}

export async function request(path, { method = "GET", body, signal, timeoutMs = defaultTimeout(path) } = {}) {
  if (timeoutMs === undefined) return performRequest(path, { method, body, signal });
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  let timer;
  try {
    const deadline = new Promise((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        const error = new Error("The request timed out. Your changes have not been confirmed. Retry using the same saved form.");
        error.code = "TIMEOUT";
        reject(error);
      }, timeoutMs);
    });
    return await Promise.race([performRequest(path, { method, body, signal: controller.signal }), deadline]);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

async function performRequest(path, { method, body, signal }) {
  method = method.toUpperCase();
  const hasBody = body !== undefined;
  const multipart = body instanceof FormData;
  const identity = requestIdentity;
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method, signal, credentials: "include", cache: "no-store",
      headers: {
        ...(hasBody && !multipart ? { "Content-Type": "application/json" } : {}),
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
    error.requestId = response.headers.get("X-Request-ID") || undefined;
    const retryAfter = Number(response.headers.get("Retry-After"));
    if (Number.isFinite(retryAfter) && retryAfter > 0) error.retryAfter = retryAfter;
    if (!signal?.aborted && response.status === 401 && !path.startsWith("/accounts/") && identity === requestIdentity && typeof window !== "undefined") window.dispatchEvent(new Event("session-expired"));
    throw error;
  }
  if (result === null || typeof result !== "object") {
    throw new Error("The backend returned an unexpected response. Your changes have not been confirmed.");
  }
  return result;
}

export async function listAll(path, filters = {}, { timeoutMs } = {}) {
  const rows = [];
  const emergency = path.startsWith("/emergency/");
  const bounded = emergency || maintenancePath(path) || timeoutMs !== undefined;
  const deadline = Date.now() + (timeoutMs ?? 30000);
  const seen = new Set();
  while (true) {
    const query = new URLSearchParams({ ...filters, offset: String(rows.length), limit: String(API_PAGE_SIZE) });
    const page = await request(`${path}?${query}`, bounded ? { timeoutMs: Math.max(1, deadline - Date.now()) } : {});
    if (!Array.isArray(page)) throw new Error("The backend returned an unexpected list response.");
    if (emergency || /^\/admin\/(maintenance-items|schedules|schedule-drafts)([/?]|$)/.test(path)) {
      for (const row of page) {
        if (!row || typeof row.id !== "string" || !row.id || seen.has(row.id)) throw new Error(emergency ? "The Emergency directory returned invalid or repeated records. Refresh and retry." : "The maintenance catalogue returned invalid or repeated records. Refresh and retry.");
        seen.add(row.id);
      }
      if (emergency && rows.length + page.length > 10000) throw new Error("The Emergency directory is too large to load. Contact your administrator.");
    }
    rows.push(...page);
    if (page.length < API_PAGE_SIZE) return rows;
  }
}
