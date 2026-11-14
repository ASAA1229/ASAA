import { existsSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

const root = process.cwd();
const apiDir = join(root, "apps", "ap-api");
const windowsPython = join(apiDir, ".venv", "Scripts", "python.exe");
const unixPython = join(apiDir, ".venv", "bin", "python");
const venvPython = process.platform === "win32" ? windowsPython : unixPython;
const python = existsSync(venvPython) ? venvPython : (process.platform === "win32" ? "python" : "python3");

console.log(`[API] Using ${existsSync(venvPython) ? "project virtual environment" : "system Python"}.`);
const child = spawn(python, [
  "-m", "uvicorn", "asaa_ap.main:app",
  "--reload", "--host", "127.0.0.1", "--port", "8000"
], { cwd: apiDir, stdio: "inherit", env: process.env });

child.on("error", error => {
  console.error(`[API] Could not start Python: ${error.message}`);
  console.error("[API] Run npm run setup:api from the repository root, then retry.");
  process.exit(1);
});
child.on("exit", code => process.exit(code ?? 1));
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
