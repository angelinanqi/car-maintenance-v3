import assert from "node:assert/strict";
import { test } from "node:test";
import { checkProxyOrigin } from "./backendProxy.mjs";

test("proxy accepts configured HTTPS origins behind a local HTTP proxy", () => {
  const previous = process.env.CORS_ORIGINS;
  process.env.CORS_ORIGINS = "http://localhost:3000, https://dashboard.example:8443";
  const request = (origin, extra = {}) => new Request("http://127.0.0.1:3000/api/backend/documents", {
    method: "POST", headers: { ...(origin === undefined ? {} : { origin }), ...extra },
  });
  try {
    assert.equal(checkProxyOrigin(request("https://dashboard.example:8443")), true);
    assert.equal(checkProxyOrigin(request("http://localhost:3000")), true);
    assert.equal(checkProxyOrigin(request("http://127.0.0.1:3000")), true);
    for (const origin of [undefined, "null", "https://dashboard.example", "https://evil.example"]) {
      assert.equal(checkProxyOrigin(request(origin)), false);
    }
    assert.equal(checkProxyOrigin(request("https://evil.example", {
      "x-forwarded-host": "evil.example", "x-forwarded-proto": "https",
    })), false);
    assert.equal(checkProxyOrigin(new Request("http://127.0.0.1:3000/api/backend/documents")), true);
  } finally {
    if (previous === undefined) delete process.env.CORS_ORIGINS;
    else process.env.CORS_ORIGINS = previous;
  }
});
