import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import nextEnv from "@next/env";

const frontendDir = fileURLToPath(new URL("../", import.meta.url));
const rootDir = fileURLToPath(new URL("../../", import.meta.url));
const command = process.argv[2];
nextEnv.loadEnvConfig(rootDir, false);

const args = [command, ...process.argv.slice(3)];
if (command === "start") {
  args.push("--port", process.env.FRONTEND_PORT || "3000");
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
