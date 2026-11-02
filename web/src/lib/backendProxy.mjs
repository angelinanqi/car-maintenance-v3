const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);

export function checkProxyOrigin(request) {
  if (safeMethods.has(request.method)) return true;
  const origin = request.headers.get("origin");
  const allowedOrigins = new Set([
    new URL(request.url).origin,
    ...(process.env.CORS_ORIGINS || "").split(",").map(value => value.trim()).filter(Boolean),
  ]);
  // Use explicit configured origins behind HTTPS proxies; forwarded headers
  // alone must never grant permission to make a state-changing request.
  return origin !== null && origin !== "null" && allowedOrigins.has(origin);
}

export function proxyPath(segments, search) {
  if (!segments.length || segments.some(segment => !segment || segment === "." || segment === ".." || /[\\/?#]/.test(segment))) {
    throw new Error("Invalid backend path");
  }
  return "/" + segments.map(encodeURIComponent).join("/") + search;
}

export async function forwardBackend(request, { path, backendURL, accessToken, fetcher = fetch }) {
  const headers = new Headers();
  for (const name of ["content-type", "accept", "range", "if-range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const origin = new URL(request.url).origin;
  headers.set("origin", origin);
  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }
  return fetcher(backendURL + path, {
    method: request.method, headers, cache: "no-store", redirect: "manual", signal: request.signal,
    ...(!safeMethods.has(request.method) ? { body: request.body, duplex: "half" } : {}),
  });
}
