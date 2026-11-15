import { spawn } from "node:child_process";

const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const apiPort = process.env.API_PORT?.trim() || "8001";
const children = [];

function start(label, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: process.cwd(),
    stdio: "inherit",
    env: process.env,
    shell: isWindows && command === npmCommand,
    ...options
  });
  children.push({ label, child });
  child.on("error", error => {
    console.error(`[${label}] Failed to start: ${error.message}`);
    stop(1);
  });
  child.on("exit", (code, signal) => {
    if (!stopping && (code !== 0 || signal)) {
      console.error(`[${label}] exited (code: ${code ?? "—"}, signal: ${signal ?? "—"}).`);
      stop(code || 1);
    }
  });
  return child;
}

let stopping = false;
function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const { child } of children) {
    if (!child.pid || child.exitCode !== null) continue;
    if (isWindows) {
      spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    } else {
      child.kill("SIGTERM");
    }
  }
  setTimeout(() => process.exit(exitCode), 300);
}

console.log("Starting ASAA web and API services. Press Ctrl+C to stop both.");
console.log("Web: http://localhost:5173");
console.log(`API: http://127.0.0.1:${apiPort}  |  Docs: http://127.0.0.1:${apiPort}/docs`);
start("WEB", npmCommand, ["run", "dev:web"]);
start("API", process.execPath, ["scripts/dev-api.mjs"]);
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
