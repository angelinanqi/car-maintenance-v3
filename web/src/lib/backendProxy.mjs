const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);

export function checkProxyOrigin(request) {
  if (!safeMethods.has(request.method) && request.headers.get("origin") !== new URL(request.url).origin) {
    return false;
  }
  return true;
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
