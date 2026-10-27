import { request } from "./client.mjs";

export const registerAccount = (details) => request("/accounts/register", { method: "POST", body: details });
export const loginAccount = (details) => request("/accounts/login", { method: "POST", body: details });
export const currentAccount = () => request("/accounts/me");
export const logoutAccount = () => request("/accounts/logout", { method: "POST" });
