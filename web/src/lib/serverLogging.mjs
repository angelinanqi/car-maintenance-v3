import { appendFileSync, mkdirSync, statSync, renameSync, existsSync, unlinkSync } from "node:fs";
import { resolve, sep } from "node:path";
import { safePath, requestId, operationMessage, formatHTTP, errorCategory } from "./liveLogging.mjs";

// Both the npm scripts and the app launcher start Next.js from web/.
const directory = resolve(process.cwd(), "../output/logs") + sep;
const path = directory + "web-live.jsonl";

export function logProxyRequest(request, { status, started, id, error, upstreamStatus }) {
  if (process.env.DEV_LOGGING !== "true") return;
  try {
    const failed = status >= 400;
    const frames = error?.stack?.split("\n").slice(1, 9).map(line =>
      line.match(/([A-Za-z0-9_.-]+\.(?:m?js|tsx?|jsx)):\d+:\d+/)?.[0]).filter(Boolean);
    const event = { timestamp: new Date().toISOString(), time: Date.now() / 1000,
      service: "web", pid: process.pid, stage: "http_response", state: failed ? "failed" : "returned",
      level: status >= 500 ? "ERROR" : failed ? "WARNING" : "INFO", client_source: "WEB",
      method: request.method, route: safePath(new URL(request.url).pathname.replace(/^\/api\/backend/, "")),
      status_code: status, outcome: failed ? "ERROR" : "SUCCESS", duration_ms: Math.round(performance.now() - started),
      request_id: requestId(id), frames, error_type: error ? errorCategory(error) : undefined,
      upstream_status_code: upstreamStatus,
      backend_response: error && upstreamStatus === undefined ? "NOT_OBSERVED" : undefined,
      message: operationMessage(new URL(request.url).pathname, request.method, !failed) };
    // The normal launcher pipes child output. Use the file/viewer in that case:
    // writing to an abandoned pipe after a terminal closes can stall Next.js.
    const stream = failed ? process.stderr : process.stdout;
    if (stream.isTTY && !stream.destroyed && stream.writable) {
      try { (status >= 500 ? console.error : failed ? console.warn : console.info)(formatHTTP(event)); } catch {}
    }
    mkdirSync(directory, { recursive: true });
    if (existsSync(path) && statSync(path).size >= 5 * 1024 * 1024) {
      if (existsSync(path + ".3")) unlinkSync(path + ".3");
      for (let n = 2; n >= 0; n--) {
        const from = n ? path + "." + n : path;
        if (existsSync(from)) renameSync(from, path + "." + (n + 1));
      }
    }
    appendFileSync(path, JSON.stringify(event) + "\n", { mode: 0o600 });
  } catch { /* Logging failures must not change a proxy response. */ }
}
