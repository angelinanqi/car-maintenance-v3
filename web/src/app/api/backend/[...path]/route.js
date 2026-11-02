import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { checkProxyOrigin, proxyPath, forwardBackend } from "@/lib/backendProxy.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request, context) {
  if (!checkProxyOrigin(request)) return NextResponse.json({ detail: "Request origin is not allowed." }, { status: 403 });
  const pendingCookies = [];
  try {
    const { path: segments } = await context.params;
    const path = proxyPath(segments, new URL(request.url).search);
    let token;
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    if (url && key) {
      const store = await cookies();
      const client = createServerClient(url, key, { cookies: {
        getAll: () => store.getAll(),
        setAll: values => { for (const value of values) { store.set(value.name, value.value, value.options); pendingCookies.push(value); } },
      } });
      // This only retrieves the token. FastAPI independently verifies it and
      // enforces email confirmation, roles, MFA and object ownership.
      const { data, error } = await client.auth.getSession();
      if (error) {
        const response = NextResponse.json({ detail: "Your session could not be restored. Sign in again." }, { status: 401 });
        for (const value of pendingCookies) response.cookies.set(value.name, value.value, value.options);
        return response;
      }
      token = data.session?.access_token;
    }
    const backendURL = (process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
    const upstream = await forwardBackend(request, { path, backendURL, accessToken: token });
    const headers = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "content-disposition", "content-range", "accept-ranges", "location", "x-request-id", "retry-after"]) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    const response = new NextResponse(upstream.body, { status: upstream.status, headers });
    for (const value of pendingCookies) response.cookies.set(value.name, value.value, value.options);
    return response;
  } catch (_) {
    const response = NextResponse.json({ detail: "The account or backend service is temporarily unavailable. Retry shortly." }, { status: 503 });
    for (const value of pendingCookies) response.cookies.set(value.name, value.value, value.options);
    return response;
  }
}

export { proxy as GET, proxy as HEAD, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
