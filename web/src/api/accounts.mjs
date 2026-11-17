import { request } from "./client.mjs";

export const currentAccount = () => request("/accounts/me");
export const updateDisplayName = display_name => request("/accounts/me", {
  method: "PATCH", body: { display_name },
});
export const accountSessions = signal => request("/accounts/sessions", { signal });
export const revokeAccountSession = id => request(`/accounts/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
export const deleteAccount = () => request("/accounts/me", { method: "DELETE" });
