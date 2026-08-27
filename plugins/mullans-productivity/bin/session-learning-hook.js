#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const argumentsForEngine = process.argv.slice(2);
let warnMissingPython = false;
if (argumentsForEngine[0] === "--warn-missing-python") {
  warnMissingPython = true;
  argumentsForEngine.shift();
}

const dataDir = process.env.PLUGIN_DATA || process.env.CLAUDE_PLUGIN_DATA;
if (!dataDir) process.exit(0);
try {
  fs.mkdirSync(dataDir, { recursive: true });
} catch {
  process.exit(0);
}

const fixedCandidates = {
  py: { command: "py", prefix: ["-3"] },
  python3: { command: "python3", prefix: [] },
  python: { command: "python", prefix: [] },
};
const cachePath = path.join(dataDir, "python-launcher.txt");
const payload = fs.readFileSync(0);

function works(candidate) {
  if (!candidate) return false;
  const result = spawnSync(
    candidate.command,
    [
      ...candidate.prefix,
      "-c",
      "import sys; raise SystemExit(sys.version_info[0] != 3)",
    ],
    { stdio: "ignore", windowsHide: true }
  );
  return result.status === 0;
}

function readConfiguredPython(configPath) {
  try {
    const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
    const configured = config.schema_version === 1 ? config.python_path : null;
    if (typeof configured !== "string" || !path.isAbsolute(configured)) return null;
    if (!fs.statSync(configured).isFile()) return null;
    return { command: configured, prefix: [] };
  } catch {
    return null;
  }
}

function findProjectConfig(cwd) {
  if (typeof cwd !== "string" || !cwd) return null;
  let current = path.resolve(cwd);
  while (true) {
    const configPath = path.join(current, ".agents", "learning", "config.json");
    if (fs.existsSync(configPath)) return configPath;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

let hookInput = {};
try {
  hookInput = JSON.parse(payload.toString("utf8"));
} catch {
  hookInput = {};
}
const projectConfig = findProjectConfig(hookInput.cwd);
const personalConfig = path.join(
  os.homedir(),
  ".agents",
  "session-learning",
  "config.json"
);
const configuredCandidates = [projectConfig, personalConfig]
  .filter(Boolean)
  .map(readConfiguredPython)
  .filter(Boolean);

let selected = configuredCandidates.find(works) || null;
let selectedIdentifier = "";
let cachedIdentifier = "";
try {
  cachedIdentifier = fs.readFileSync(cachePath, "utf8").trim();
} catch {
  cachedIdentifier = "";
}
if (!selected && works(fixedCandidates[cachedIdentifier])) {
  selected = fixedCandidates[cachedIdentifier];
  selectedIdentifier = cachedIdentifier;
}
if (!selected) {
  selectedIdentifier =
    Object.keys(fixedCandidates).find((identifier) => works(fixedCandidates[identifier])) || "";
  selected = fixedCandidates[selectedIdentifier] || null;
}

if (!selected) {
  if (warnMissingPython) {
    const warningPath = path.join(dataDir, "python-launcher-warning");
    try {
      const descriptor = fs.openSync(warningPath, "wx");
      fs.closeSync(descriptor);
      process.stdout.write(
        '{"systemMessage":"Session Learning automatic retrieval is unavailable because Python 3 was not found."}\n'
      );
    } catch {
      // A previous session already emitted the warning.
    }
  }
  process.exit(0);
}

if (selectedIdentifier) {
  try {
    const temporary = path.join(
      dataDir,
      `python-launcher.${process.pid}.${Date.now()}.tmp`
    );
    fs.writeFileSync(temporary, `${selectedIdentifier}\n`, "utf8");
    fs.renameSync(temporary, cachePath);
  } catch {
    // Caching is an optimization; retrieval can still proceed.
  }
}

const pluginRoot = path.resolve(__dirname, "..");
const engine = path.join(
  pluginRoot,
  "skills",
  "session-learning",
  "scripts",
  "session_learning.py"
);
const result = spawnSync(
  selected.command,
  [
    ...selected.prefix,
    engine,
    "hook",
    "--data-dir",
    dataDir,
    ...argumentsForEngine,
  ],
  {
    input: payload,
    stdio: ["pipe", "inherit", "ignore"],
    windowsHide: true,
  }
);
process.exit(0);
