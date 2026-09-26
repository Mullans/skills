#!/usr/bin/env python3
"""Local hook diagnostics. A longer diagnostic wait is NEVER an acceptance pass.

Instrument only the disposable installed copy; execute its literal packaged
command. No network requests, host sessions, or workflow dispatches are made.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/session-learning"))
from test_hook_launch_contract import HookLaunchContractTests
from test_session_learning_v2 import session_learning, v1_lesson

TRACE_PREAMBLE = r"""
const traceFs = require('node:fs');
const traceFile = process.env.SESSION_LEARNING_TEST_TRACE;
function trace(phase, extra = {}) {
  traceFs.appendFileSync(traceFile, JSON.stringify({phase, at_ms: Date.now(), ...extra})+'\n');
}
trace('node_enter');
const realRead = traceFs.readFileSync;
traceFs.readFileSync = function(file, ...args) {
  if (file === 0) trace('stdin_read_start');
  const result = realRead.call(this, file, ...args);
  if (file === 0) trace('stdin_read_end', {bytes: result.length});
  return result;
};
const cp = require('node:child_process');
const realSpawn = cp.spawnSync;
cp.spawnSync = function(command, args, options) {
  const phase = args.includes('-c') ? 'python_probe' : 'engine';
  trace(phase+'_start', {timeout_ms: options.timeout});
  const result = realSpawn.call(this, command, args, options);
  trace(phase+'_end', {status: result.status, error: result.error?.code || null});
  return result;
};
"""

def trial(shell, event, mode, diagnostic_timeout):
    fixture = HookLaunchContractTests()
    fixture.setUp()
    try:
        if mode == "probe":
            fixture.probe_engine()
        else:
            lessons = fixture.learning / "lessons"
            lessons.mkdir()
            record = v1_lesson()
            record["delivery"].update({"mode": "dynamic", "host": None, "path": None,
                                      "instruction_path": "AGENTS.md", "enforcement_target": None})
            (lessons / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")
            (fixture.project / "AGENTS.md").write_text(session_learning._instruction_pointer_block(), encoding="utf-8")
            session_learning.rebuild_index(fixture.project)
        trace_file = fixture.root / "phases.jsonl"
        fixture.env["SESSION_LEARNING_TEST_TRACE"] = str(trace_file)
        launcher = fixture.plugin / "bin/session-learning-hook.js"
        original = launcher.read_text(encoding="utf-8")
        # Retain the shebang and strict-mode declaration ahead of instrumentation.
        anchor = '"use strict";'
        assert original.count(anchor) == 1
        launcher.write_text(original.replace(anchor, anchor + "\n" + TRACE_PREAMBLE, 1), encoding="utf-8")
        actual_popen = subprocess.Popen
        measurements = {}

        def measured_run(argv, **kwargs):
            kwargs.pop("timeout")  # Read-only diagnostic override; config is unchanged.
            kwargs.pop("check")
            kwargs.pop("capture_output")
            payload = kwargs.pop("input")
            started_ms = time.time_ns() // 1000000
            started = time.perf_counter()
            with actual_popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, **kwargs) as child:
                try:
                    stdout, stderr = child.communicate(payload, timeout=diagnostic_timeout)
                    outcome = "completed" if child.returncode == 0 else "nonzero_exit"
                except subprocess.TimeoutExpired:
                    # Terminate only the process tree created by this diagnostic.
                    if os.name == "nt":
                        killer = Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"
                        subprocess.run([str(killer), "/PID", str(child.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=5, check=False)
                    child.kill()
                    stdout, stderr = child.communicate(timeout=5)
                    outcome = "diagnostic_timeout"
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                measurements.update(outcome=outcome, total_ms=elapsed_ms,
                                    packaged_deadline_exceeded=elapsed_ms > 2000,
                                    exit_code=child.returncode)
            phases = [json.loads(line) for line in trace_file.read_text().splitlines()] if trace_file.exists() else []
            measurements["phases"] = [{**item, "elapsed_ms": item["at_ms"] - started_ms} for item in phases]
            for item in measurements["phases"]:
                del item["at_ms"]
            measurements["stderr"] = stderr[:1000]
            try:
                output = json.loads(stdout)
                measurements["output_verified"] = (
                    output.get("payload") == fixture.payload(event) if mode == "probe" else
                    "lesson.generated-files.001" in output.get("hookSpecificOutput", {}).get("additionalContext", "")
                )
            except ValueError:
                measurements["output_verified"] = False
            # SessionStart/End may legitimately produce no lesson context.
            return subprocess.CompletedProcess(argv, measurements["exit_code"], stdout, stderr)

        # The timeout handler must use the real subprocess.run for cleanup.
        actual_run = subprocess.run
        def dispatch(argv, **kwargs):
            if isinstance(argv, list) and argv and str(argv[0]).endswith("taskkill.exe"):
                return actual_run(argv, **kwargs)
            return measured_run(argv, **kwargs)
        with mock.patch("subprocess.run", side_effect=dispatch):
            fixture.invoke("codex", event, shell)
        return measurements
    finally:
        fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", default="all", choices=["all", "cmd-host", "powershell.exe", "pwsh.exe"])
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--diagnostic-timeout", type=float, default=10)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 10 or not 2 <= args.diagnostic_timeout <= 30:
        parser.error("Use 1-10 repetitions and a 2-30 second diagnostic timeout")
    if os.name != "nt":
        parser.error("This diagnostic targets native Windows; use the contract tests on Unix")
    shells = ["powershell.exe", "cmd-host", "pwsh.exe"] if args.shell == "all" else [args.shell]
    print(json.dumps({"diagnostic_only": True, "python_version": sys.version.split()[0],
                      "diagnostic_timeout_seconds": args.diagnostic_timeout}), flush=True)
    for shell in shells:
        if shell != "cmd-host" and not shutil.which(shell):
            print(json.dumps({"shell": shell, "outcome": "shell_unavailable"}), flush=True)
            continue
        for iteration in range(args.repetitions):
            for mode, event in [("probe", "SessionStart"), ("probe", "UserPromptSubmit"),
                                ("real", "UserPromptSubmit")]:
                result = trial(shell, event, mode, args.diagnostic_timeout)
                print(json.dumps({"shell": shell, "event": event, "mode": mode,
                                  "iteration": iteration + 1, **result}), flush=True)


if __name__ == "__main__":
    main()
