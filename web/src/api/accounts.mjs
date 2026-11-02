import { request } from "./client.mjs";

export const currentAccount = () => request("/accounts/me");
