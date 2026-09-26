#!/usr/bin/env node
"use strict";

// One bootstrap for both hosts and all operating systems. Never spawn a shell.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { performance } = require("node:perf_hooks");
const { spawnSync } = require("node:child_process");

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return null; }
}

function projectConfig(cwd) {
  if (typeof cwd !== "string" || !path.isAbsolute(cwd)) return null;
  let current = cwd;
  while (true) {
    const candidate = path.join(current, ".agents", "learning", "config.json");
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

function configuredPython(file) {
  const config = file && readJson(file);
  const executable = config && config.schema_version === 1 && config.python_path;
  if (typeof executable !== "string" || !path.isAbsolute(executable)) return null;
  try {
    if (fs.statSync(executable).isFile()) return { command: executable, prefix: [] };
  } catch { /* Try the next configured or discovered interpreter. */ }
  return null;
}

function run(args) {
  const hostIndex = args.indexOf("--host");
  const host = args[hostIndex + 1];
  if (hostIndex < 0 || !["codex", "claude"].includes(host)) return;
  const dataDir = host === "codex" ? process.env.PLUGIN_DATA : process.env.CLAUDE_PLUGIN_DATA;
  if (!dataDir) return;
  fs.mkdirSync(dataDir, { recursive: true });
  const payload = fs.readFileSync(0);
  let input;
  try { input = JSON.parse(payload.toString("utf8")); } catch { input = {}; }

  // Leave headroom inside the hosts' two-second timeout. Bound both discovery
  // and engine execution, rather than letting the host kill advisory retrieval.
  const deadline = performance.now() + 1400;
  const remaining = () => Math.max(0, Math.floor(deadline - performance.now()));
  const childEnv = { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8",
    PYTHONDONTWRITEBYTECODE: "1" };
  const candidates = new Map(process.platform === "win32" ? [
    ["py", { command: "py", prefix: ["-3"] }],
    ["python3", { command: "python3", prefix: [] }],
    ["python", { command: "python", prefix: [] }],
  ] : [
    ["python3", { command: "python3", prefix: [] }],
    ["python", { command: "python", prefix: [] }],
  ]);
  const attempted = new Set();
  function works(candidate) {
    if (!candidate || !remaining()) return false;
    const key = JSON.stringify(candidate);
    if (attempted.has(key)) return false;
    attempted.add(key);
    const result = spawnSync(candidate.command, [...candidate.prefix, "-c",
      "import sys; raise SystemExit(sys.version_info < (3, 10))"], {
      stdio: "ignore", windowsHide: true, shell: false, env: childEnv,
      timeout: Math.min(250, remaining()),
    });
    return !result.error && result.status === 0;
  }

  let selected = [
    configuredPython(projectConfig(input && input.cwd)),
    configuredPython(path.join(os.homedir(), ".agents/session-learning/config.json")),
  ].find(works);
  let selectedIdentifier;
  const cachePath = path.join(dataDir, "python-launcher.txt");
  if (!selected) {
    let cached;
    try { cached = fs.readFileSync(cachePath, "utf8").trim(); } catch { /* First run. */ }
    if (works(candidates.get(cached))) {
      selected = candidates.get(cached);
      selectedIdentifier = cached;
    }
  }
  if (!selected) {
    for (const [identifier, candidate] of candidates) {
      if (works(candidate)) {
        selected = candidate;
        selectedIdentifier = identifier;
        break;
      }
    }
  }
  if (!selected) {
    if (args.includes("--warn-missing-python")) {
      try {
        fs.closeSync(fs.openSync(path.join(dataDir, "python-launcher-warning"), "wx"));
        process.stdout.write(JSON.stringify({ systemMessage:
          "Session Learning automatic retrieval is unavailable because Python 3.10+ was not found within the startup budget." }) + "\n");
      } catch { /* Warn once; don't block work on a read-only data directory. */ }
    }
    return;
  }
  if (selectedIdentifier) {
    const temporary = `${cachePath}.${process.pid}.tmp`;
    try {
      fs.writeFileSync(temporary, `${selectedIdentifier}\n`, "utf8");
      fs.renameSync(temporary, cachePath);
    } catch { /* Cache failures do not prevent retrieval. */ }
    finally { try { fs.unlinkSync(temporary); } catch { /* Already renamed. */ } }
  }
  if (!remaining()) return;
  const engine = path.join(__dirname, "../skills/session-learning/scripts/session_learning.py");
  const result = spawnSync(selected.command, [...selected.prefix, engine, "hook",
    "--data-dir", dataDir, "--host", host], {
    input: payload, encoding: "utf8", env: childEnv, shell: false,
    windowsHide: true, timeout: remaining(), maxBuffer: 1024 * 1024,
  });
  // Keep partial/crashed engine output out of the host's JSON protocol.
  if (!result.error && result.status === 0 && result.stdout) process.stdout.write(result.stdout);
}

function main(args = process.argv.slice(2)) {
  try { run(args); } catch { /* Advisory retrieval never blocks a host action. */ }
}

module.exports = { main };
if (require.main === module) main();
