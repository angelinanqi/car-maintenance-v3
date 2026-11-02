import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadConfiguration } from "./configuration.mjs";

const frontendDir = fileURLToPath(new URL("../", import.meta.url));
const command = process.argv[2];
loadConfiguration();

const args = [command, ...process.argv.slice(3)];
if (command === "start") {
  if (!args.some(arg => arg === "--port" || arg === "-p" || arg.startsWith("--port="))) {
    args.push("--port", process.env.FRONTEND_PORT || "3000");
  }
  if (!args.some(arg => arg === "--hostname" || arg === "-H" || arg.startsWith("--hostname="))) {
    args.push("--hostname", process.env.FRONTEND_HOST || "127.0.0.1");
  }
}

const child = spawn(process.execPath, ["node_modules/next/dist/bin/next", ...args], {
  cwd: frontendDir,
  stdio: "inherit",
  env: process.env,
});
child.on("error", (error) => {
  console.error(error.message);
  process.exitCode = 1;
});
child.on("exit", (code) => { process.exitCode = code ?? 1; });
