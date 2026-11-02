import { readFileSync } from "node:fs";

export function loadConfiguration() {
  const root = new URL("../../", import.meta.url);
  // The web app needs only non-secret JSON settings; root .env is for server credentials.
  let values;
  try {
    values = JSON.parse(readFileSync(new URL("app.config.json", root), "utf8"));
  } catch {
    throw new Error("Cannot read app.config.json; expected a JSON object of string settings");
  }
  if (!values || Array.isArray(values) || typeof values !== "object" ||
      Object.values(values).some((value) => typeof value !== "string")) {
    throw new Error("app.config.json must contain a JSON object of string settings");
  }
  for (const [name, value] of Object.entries(values)) {
    if (process.env[name] === undefined) process.env[name] = value;
  }
}
