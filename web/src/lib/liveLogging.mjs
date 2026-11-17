// Metadata only. Never pass bodies, headers, user identities, or Error messages.
const segments = new Set(("api backend v1 auth token logout signup recover verify user health docs config accounts me admin documents guides categories emergency playbooks contacts dashboard knowledge vehicles manufacturers models catalogue maintenance-items maintenance-intervals schedules schedule-drafts maintenance-assistance mobile tasks records incidents plans service-plans preview bookmarks notes saved-items chat sessions resume activity sources image original pages media upload process extraction review publish unpublish coverage tags removal-impact archive restore delete-impact deactivate index indexing youtube channels videos sync status questions runs tests document-test-summaries chat-starters companion-settings companion progress recap recaps nearby workshops mechanic-questions configuration scopes profiles schedule-draft assets internal handoffs pending index-ready index-failed confirm-corrections corrections content").split(" "));

export function safePath(value) {
  try {
    return new URL(value, "http://local").pathname.split("/")
      .map(part => !part || segments.has(part) ? part : ":id").join("/").slice(0, 240) || "/";
  } catch { return "/unknown"; }
}

export function requestId(value) {
  return /^[a-fA-F0-9-]{32,36}$/.test(value || "") ? value : undefined;
}

export function errorCategory(error) {
  if (Number.isInteger(error?.status)) return "HTTP_RESPONSE";
  if (error?.code === "TIMEOUT" || error?.name === "TimeoutError") return "TIMEOUT";
  if (error?.name === "AbortError") return "CANCELLED";
  if (error?.code === "INVALID_RESPONSE") return "INVALID_RESPONSE";
  if (error?.code === "NETWORK" || /^(?:ECONN|ENOTFOUND|EAI_|UND_ERR_|CERT_)/.test(error?.cause?.code || "")) return "NETWORK";
  return "UNEXPECTED";
}

export function operationMessage(path, method, success) {
  const names = { documents: "Documents", guides: "Learning guides", categories: "Learning topics",
    chat: "Chat", accounts: "Account", knowledge: "Knowledge base", emergency: "Emergency content",
    schedules: "Schedules", "schedule-drafts": "Schedule drafts", dashboard: "Dashboard", config: "Configuration" };
  const name = safePath(path).split("/").map(part => names[part]).find(Boolean) || "API";
  return `${name} ${success ? method === "GET" ? "loaded" : "request completed" : "request failed"}`;
}

export function formatHTTP(event) {
  const time = new Date(event.timestamp).toLocaleTimeString("en-GB", { hour12: false });
  return `[${time}] [WEB] [HTTP] ${event.method} ${event.route} ${event.status_code ?? "—"} | ${event.duration_ms}ms | ${event.outcome}` +
    (event.application_outcome === "ERROR" ? ` | ${event.error_type}` : "") +
    ` | ${event.message}` + (event.request_id ? ` | id=${event.request_id}` : "");
}

export function beginWebRequest(path, method) {
  const started = performance.now();
  const trace = { timestamp: new Date().toISOString(), route: safePath(path), method: method.toUpperCase() };
  try { trace.id = globalThis.crypto?.randomUUID?.(); } catch { /* Server assigns an ID if needed. */ }
  trace.finish = error => {
    try {
      if (process.env.NEXT_PUBLIC_DEV_LOGGING !== "true") return;
      const httpSuccess = trace.status_code != null && trace.status_code < 400;
      const event = { ...trace, timestamp: new Date().toISOString(), outcome: httpSuccess ? "SUCCESS" : "ERROR",
        application_outcome: error ? "ERROR" : "SUCCESS", error_type: trace.failure || (trace.status_code >= 400 ? "HTTP" : errorCategory(error)),
        duration_ms: Math.round(performance.now() - started), request_id: requestId(trace.request_id || trace.id),
        message: operationMessage(path, trace.method, !error) };
      const write = event.application_outcome === "ERROR" ? trace.status_code < 500 && trace.status_code >= 400 || event.error_type === "CANCELLED" ? console.warn : console.error : console.info;
      write(formatHTTP(event));
    } catch { /* Logging never interrupts a request. */ }
  };
  return trace;
}

export function installWebLogging() {
  if (process.env.NEXT_PUBLIC_DEV_LOGGING !== "true" || typeof window === "undefined") return () => {};
  const report = event => { try {
    const time = new Date().toLocaleTimeString("en-GB", { hour12: false });
    console.error(`[${time}] [WEB] [ERROR] Unexpected browser error` +
      (event.filename ? ` | script=${safePath(event.filename)} | line=${Number(event.lineno) || 0}` : " | unhandled promise"));
  } catch {} };
  window.addEventListener("error", report);
  window.addEventListener("unhandledrejection", report);
  return () => { window.removeEventListener("error", report); window.removeEventListener("unhandledrejection", report); };
}

export function logAccountFailure(error) {
  try {
    if (process.env.NEXT_PUBLIC_DEV_LOGGING !== "true") return;
    const status = Number(error?.status);
    const known = Number.isInteger(status) && status >= 100 && status <= 599;
    const time = new Date().toLocaleTimeString("en-GB", { hour12: false });
    (known && status < 500 ? console.warn : console.error)(`[${time}] [WEB] [${known && status < 500 ? "WARN" : "ERROR"}] Account operation failed | ${known ? `HTTP ${status}` : "no HTTP status"}`);
  } catch {}
}
