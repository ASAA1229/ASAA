// One command for local development: `npm run dev`.
//
//   1. Creates the API's Python environment on first run (apps/ap-api/.venv, pinned by constraints.txt).
//   2. Applies database migrations (alembic upgrade head) so every API route has its tables.
//   3. When the local identity server (Keycloak realm "asaa" on 127.0.0.1:8280) answers, wires the API's token
//      verification, the Swagger UI sign-in (client asaa-api-docs) and the portal sign-in (client asaa-portal) to it.
//      Values you set yourself (process environment, apps/ap-api/.env, .env) always win; nothing is written to disk.
//   4. Starts the API (http://127.0.0.1:8001, docs at /docs) and the web portal (http://127.0.0.1:5173), waits until the
//      API is ready, and stops both together.
//
// Loopback only: the identity server is used only when it is on 127.0.0.1/localhost. No secret is read or printed.
// Opt-outs: ASAA_DEV_SKIP_SETUP=1, ASAA_DEV_SKIP_MIGRATE=1, ASAA_DEV_NO_IDENTITY=1.

import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const root = process.cwd();
const apiDir = join(root, "apps", "ap-api");
const venvPython = isWindows ? join(apiDir, ".venv", "Scripts", "python.exe") : join(apiDir, ".venv", "bin", "python");
const apiPort = process.env.API_PORT?.trim() || "8001";
const webPort = process.env.WEB_PORT?.trim() || "5173";
const apiBase = `http://127.0.0.1:${apiPort}`;
const identityBase = (process.env.ASAA_DEV_IDENTITY_URL?.trim() || "http://127.0.0.1:8280").replace(/\/+$/, "");
const children = [];
let stopping = false;

function log(message) { console.log(`[dev] ${message}`); }

function runOnce(label, command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, stdio: "inherit", env: process.env });
    child.on("error", (error) => reject(new Error(`${label}: ${error.message}`)));
    child.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(`${label} exited with code ${code}`))));
  });
}

// Keys set in a dotenv-style file (uncommented, non-empty). Only names are read for the decision; values are not used.
function keysSetIn(file) {
  const keys = new Set();
  if (!existsSync(file)) return keys;
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    if (m && m[2].trim() !== "") keys.add(m[1]);
  }
  return keys;
}

function isLoopback(url) {
  try { return ["127.0.0.1", "localhost", "[::1]", "::1"].includes(new URL(url).hostname); } catch { return false; }
}

async function identityServerReady() {
  if (process.env.ASAA_DEV_NO_IDENTITY === "1" || !isLoopback(identityBase)) return false;
  try {
    const response = await fetch(`${identityBase}/realms/asaa/.well-known/openid-configuration`, { signal: AbortSignal.timeout(2000), redirect: "error" });
    return response.ok;
  } catch { return false; }
}

async function waitForApi(timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && !stopping) {
    try {
      const response = await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(2000) });
      if (response.ok) return true;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

function start(label, command, args, options = {}) {
  const child = spawn(command, args, { cwd: root, stdio: "inherit", env: process.env, shell: isWindows && command === npmCommand, ...options });
  children.push({ label, child });
  child.on("error", (error) => { console.error(`[${label}] Failed to start: ${error.message}`); stop(1); });
  child.on("exit", (code, signal) => {
    if (!stopping && (code !== 0 || signal)) {
      console.error(`[${label}] exited (code: ${code ?? "-"}, signal: ${signal ?? "-"}).`);
      if (label === "API") console.error("[dev] The API stopped. Check the error above; run `npm run setup:api` if Python packages are missing.");
      stop(code || 1);
    }
  });
  return child;
}

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const { child } of children) {
    if (!child.pid || child.exitCode !== null) continue;
    if (isWindows) spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    else child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(exitCode), 300);
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

try {
  // 1. Python environment
  if (!existsSync(venvPython)) {
    if (process.env.ASAA_DEV_SKIP_SETUP === "1") throw new Error("apps/ap-api/.venv is missing and ASAA_DEV_SKIP_SETUP=1; run `npm run setup:api`.");
    log("First run: creating the API Python environment (apps/ap-api/.venv). This takes a few minutes once.");
    await runOnce("API setup", process.execPath, [join(root, "scripts", "setup-api.mjs")], root);
  }

  // 2. Migrations
  if (process.env.ASAA_DEV_SKIP_MIGRATE !== "1") {
    log("Applying database migrations (alembic upgrade head).");
    await runOnce("Migrations", venvPython, ["-m", "alembic", "upgrade", "head"], apiDir);
  }

  // 3. Identity wiring (only values you have not set yourself)
  const apiKeys = new Set([...keysSetIn(join(apiDir, ".env"))]);
  const webKeys = new Set([...keysSetIn(join(root, ".env")), ...keysSetIn(join(root, ".env.local"))]);
  const unset = (key, fileKeys) => !(process.env[key]?.trim()) && !fileKeys.has(key);
  if (await identityServerReady()) {
    const realm = `${identityBase}/realms/asaa`;
    const defaults = [
      ["ASAA_AP_JWT_JWKS_URL", `${realm}/protocol/openid-connect/certs`, apiKeys],
      ["ASAA_AP_JWT_ISSUER", realm, apiKeys],
      ["ASAA_AP_JWT_AUDIENCE", "asaa-api", apiKeys],
      ["ASAA_AP_DOCS_OIDC_AUTHORIZATION_URL", `${realm}/protocol/openid-connect/auth`, apiKeys],
      ["ASAA_AP_DOCS_OIDC_TOKEN_URL", `${realm}/protocol/openid-connect/token`, apiKeys],
      ["ASAA_AP_DOCS_OIDC_CLIENT_ID", "asaa-api-docs", apiKeys],
      ["VITE_OIDC_AUTHORITY", realm, webKeys],
      ["VITE_OIDC_CLIENT_ID", "asaa-portal", webKeys],
      ["VITE_OIDC_REDIRECT_URI", `http://127.0.0.1:${webPort}`, webKeys],
      ["VITE_API_BASE_URL", apiBase, webKeys],
    ];
    const applied = [];
    for (const [key, value, fileKeys] of defaults) if (unset(key, fileKeys)) { process.env[key] = value; applied.push(key); }
    log(`Identity server found at ${identityBase} (realm asaa). ${applied.length ? `Wired for this session: ${applied.join(", ")}.` : "Using your configured identity settings."}`);
  } else if (process.env.ASAA_DEV_NO_IDENTITY !== "1") {
    log(`Identity server not reachable at ${identityBase}. The API and docs still start, but protected endpoints answer 503/401 until`);
    log("tokens can be verified. Start it from the Configuration repository: identity/scripts/start.ps1 (needs Docker Desktop),");
    log("then apply-realm.ps1 and create-demo-user.ps1, and run `npm run dev` again.");
  }

  // 4. Services
  log(`Starting the API on ${apiBase} and the web portal on http://127.0.0.1:${webPort}. Press Ctrl+C to stop both.`);
  start("API", process.execPath, [join(root, "scripts", "dev-api.mjs")]);
  if (await waitForApi()) {
    log(`API ready. Swagger UI: ${apiBase}/docs${process.env.ASAA_AP_DOCS_OIDC_CLIENT_ID || apiKeys.has("ASAA_AP_DOCS_OIDC_CLIENT_ID") ? " (use Authorize to sign in)" : ""}`);
  } else if (!stopping) {
    log(`The API did not answer ${apiBase}/health within 90 s; the web portal starts anyway.`);
  }
  if (!stopping) start("WEB", npmCommand, ["run", "dev:web"]);
} catch (error) {
  console.error(`[dev] ${error.message}`);
  stop(1);
}
