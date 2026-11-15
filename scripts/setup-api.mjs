import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const apiDir = join(process.cwd(), "apps", "ap-api");
const venvDir = join(apiDir, ".venv");
const windowsPython = join(venvDir, "Scripts", "python.exe");
const unixPython = join(venvDir, "bin", "python");
const pythonInVenv = process.platform === "win32" ? windowsPython : unixPython;
const configuredPython = process.env.PYTHON?.trim();

function run(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, stdio: "inherit", shell: process.platform === "win32" && command === "py" });
    child.on("error", reject);
    child.on("exit", code => code === 0 ? resolve() : reject(new Error(`${command} exited with code ${code}`)));
  });
}

try {
  if (!existsSync(pythonInVenv)) {
    console.log("[API setup] Creating apps/ap-api/.venv");
    if (configuredPython) {
      await run(configuredPython, ["-m", "venv", ".venv"], apiDir);
    } else if (process.platform === "win32") {
      await run("py", ["-3", "-m", "venv", ".venv"], apiDir);
    } else {
      await run("python3", ["-m", "venv", ".venv"], apiDir);
    }
  }
  console.log("[API setup] Installing API and test dependencies");
  const constraints = join(apiDir, "constraints.txt");
  const pipArgs = ["-m", "pip", "install", "-e", ".[test]"];
  if (existsSync(constraints)) {
    console.log("[API setup] Using pinned versions from apps/ap-api/constraints.txt");
    pipArgs.push("-c", constraints);
  }
  await run(pythonInVenv, pipArgs, apiDir);
  console.log("[API setup] Complete. Start both services with: npm run dev");
} catch (error) {
  console.error(`[API setup] ${error.message}`);
  process.exit(1);
}
