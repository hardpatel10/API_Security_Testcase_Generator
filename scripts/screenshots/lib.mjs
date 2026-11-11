// Shared helpers for the screenshot workflow. Dev-only tooling: nothing here ships with the app.
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const SHOTS = path.join(ROOT, "screenshots");
export const RAW = path.join(SHOTS, "raw");
export const TMP = path.join(SHOTS, "tmp");
export const FINAL = path.join(SHOTS, "final");
export const SAMPLES = path.join(ROOT, "frontend", "public", "samples");
export const BACKEND_PORT = 8000; // frontend/vite.config.ts proxies /api to this port
export const FRONT_PORT = 4173;
export const BASE = `http://127.0.0.1:${FRONT_PORT}`;

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const log = (...a) => console.log(...a);
export const rel = (p) => path.relative(ROOT, p).replaceAll("\\", "/");
export const ensureDir = (d) => fs.mkdirSync(d, { recursive: true });

// ------------------------------------------------------------------------------------------ servers
export function portFree(port) {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.once("error", () => resolve(false));
    s.once("listening", () => s.close(() => resolve(true)));
    s.listen(port, "127.0.0.1");
  });
}

export async function waitHttp(url, ms = 60000, check = (r) => r.ok) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      if (check(await fetch(url))) return true;
    } catch { /* not up yet */ }
    await sleep(400);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function pythonCmd() {
  const venv = process.platform === "win32" ? path.join(ROOT, ".venv", "Scripts", "python.exe") : path.join(ROOT, ".venv", "bin", "python");
  return fs.existsSync(venv) ? venv : process.platform === "win32" ? "python" : "python3";
}

export function killTree(child) {
  if (!child || child.killed || child.exitCode !== null) return;
  try {
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else process.kill(-child.pid, "SIGTERM");
  } catch { /* already gone */ }
}

/** Build the frontend, start the API and the static preview server, wait until both answer. Returns { stop }. */
export async function startServers() {
  for (const p of [BACKEND_PORT, FRONT_PORT]) {
    if (!(await portFree(p))) throw new Error(`Port ${p} is already in use. Stop whatever is using it and run again.`);
  }
  const vite = path.join(ROOT, "frontend", "node_modules", "vite", "bin", "vite.js");
  if (!fs.existsSync(vite)) throw new Error("frontend dependencies are missing. Run: npm --prefix frontend install");
  log("• building the frontend (production build: no dev overlays)…");
  const build = spawnSync(process.execPath, [vite, "build"], { cwd: path.join(ROOT, "frontend"), stdio: "ignore" });
  if (build.status !== 0) throw new Error("frontend build failed. Run: npm --prefix frontend run build");

  const detached = process.platform !== "win32";
  const api = spawn(pythonCmd(), ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    { cwd: ROOT, stdio: "ignore", detached });
  const web = spawn(process.execPath, [vite, "preview", "--host", "127.0.0.1", "--port", String(FRONT_PORT), "--strictPort"],
    { cwd: path.join(ROOT, "frontend"), stdio: "ignore", detached });
  const stop = () => { killTree(web); killTree(api); };
  process.on("exit", stop);
  process.on("SIGINT", () => { stop(); process.exit(130); });
  try {
    await waitHttp(`http://127.0.0.1:${BACKEND_PORT}/api/health`);
    await waitHttp(`${BASE}/`);
    await waitHttp(`${BASE}/api/health`, 15000); // through the preview proxy
  } catch (e) {
    stop();
    throw e;
  }
  log(`• backend :${BACKEND_PORT} and frontend :${FRONT_PORT} are healthy`);
  return { stop };
}

// ------------------------------------------------------------------------------------------ secrets
const PATTERNS = [
  ["JWT", /eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*/],
  ["Bearer token", /Bearer\s+(?!\{\{|<)[A-Za-z0-9._~+/-]{12,}/],
  ["known key prefix", /\b(sk_(live|test)_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,}|gh[pousr]_[A-Za-z0-9]{20,})/],
  ["long random string", /\b(?=[A-Za-z0-9_+/=-]*\d)(?=[A-Za-z0-9_+/=-]*[A-Za-z])[A-Za-z0-9_+/=-]{32,}\b/],
];

/** Literal secret values that exist in the sample files (they must never appear on screen). */
export function forbiddenLiterals() {
  const out = new Set();
  const env = JSON.parse(fs.readFileSync(path.join(SAMPLES, "sample-postman-environment.json"), "utf8"));
  const col = JSON.parse(fs.readFileSync(path.join(SAMPLES, "sample-postman.json"), "utf8"));
  const vars = [...(env.values ?? []), ...(col.variable ?? [])];
  for (const v of vars) {
    const val = String(v.value ?? "");
    if (val.length >= 8 && !val.startsWith("<") && /token|secret|password|key|jwt/i.test(v.key)) out.add(val);
  }
  return [...out];
}

export function scanForSecrets(text, literals) {
  const hits = [];
  for (const [name, re] of PATTERNS) {
    const m = re.exec(text);
    if (m) hits.push(`${name}: "${m[0].slice(0, 12)}…"`);
  }
  for (const lit of literals) if (text.includes(lit)) hits.push(`sample secret value "${lit.slice(0, 4)}…" is visible`);
  return hits;
}

// ------------------------------------------------------------------------------------------ files
export const pngSize = (buf) => ({ w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) });
export const kb = (n) => (n / 1024 >= 1024 ? `${(n / 1024 / 1024).toFixed(2)} MB` : `${Math.round(n / 1024)} KB`);

/** Only files whose names this workflow produces are ever deleted. */
const OWNED = [
  /^\d{2}-[a-z0-9-]+(\.attempt\d+)?\.png$/,
  /^(excel-summary|excel-plan|contact-sheet)\.png$/,
  /^(report\.xlsx|report\.pdf|carousel\.pdf|index\.html|analysis\.json)$/,
];
export const isOwned = (name) => OWNED.some((re) => re.test(name));

function inside(parent, child) {
  const r = path.relative(parent, child);
  return r && !r.startsWith("..") && !path.isAbsolute(r);
}

/** Owned files below dir (recursive); anything else is reported as "left alone". */
export function listOwned(dir) {
  const owned = [], foreign = [];
  if (!fs.existsSync(dir)) return { owned, foreign };
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else (isOwned(e.name) ? owned : foreign).push({ path: p, size: fs.statSync(p).size });
    }
  };
  walk(dir);
  return { owned, foreign };
}

/** Print a dry-run list, then delete exactly those files (never anything outside screenshots/ or foreign files). */
export function dryRunThenDelete(files, { label, dryRunOnly = false, removeEmptyDirs = [] }) {
  const safe = files.filter((f) => inside(SHOTS, f.path));
  if (!safe.length) { log(`• ${label}: nothing to delete`); return 0; }
  log(`• ${label}: dry-run list (${safe.length} file${safe.length === 1 ? "" : "s"}, ${kb(safe.reduce((s, f) => s + f.size, 0))})`);
  for (const f of safe) log(`    ${rel(f.path)}  (${kb(f.size)})`);
  if (dryRunOnly) { log("  --dry-run: nothing was deleted"); return 0; }
  for (const f of safe) fs.rmSync(f.path, { force: true });
  for (const d of removeEmptyDirs) {
    if (inside(SHOTS, d) && fs.existsSync(d) && !listAll(d).length) fs.rmSync(d, { recursive: true, force: true });
  }
  log(`  deleted ${safe.length}`);
  return safe.length;
}

function listAll(dir) {
  const out = [];
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : out.push(path.join(d, e.name))));
  walk(dir);
  return out;
}
