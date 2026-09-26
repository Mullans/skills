"""Execute shipped host definitions, not a hand-written substitute invocation.

Native Unix coverage runs in CI. Git Bash on Windows is supplemental shell
coverage only; it is not labeled as Linux or macOS validation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_session_learning_v2 import REPO_ROOT, session_learning, v1_lesson


class HookLaunchContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        # Values that break textual substitution or double shell expansion.
        self.plugin = self.root / "Plugin café $cash 'quote' & (parens) %PATH% !bang!"
        shutil.copytree(REPO_ROOT / "plugins/mullans-productivity", self.plugin)
        self.project = self.root / "project café"
        self.learning = self.project / ".agents/learning"
        self.learning.mkdir(parents=True)
        self.data = self.root / "plugin data"
        self.data.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = os.environ.copy()
        for name in ("PLUGIN_ROOT", "PLUGIN_DATA", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA"):
            self.env.pop(name, None)
        self.env.update({"HOME": str(self.home), "USERPROFILE": str(self.home),
                         "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        self.configure_python()
        self.node = shutil.which("node")
        self.assertIsNotNone(self.node, "Node is a required hook/test dependency")

    def configure_python(self, executable=None):
        (self.learning / "config.json").write_text(json.dumps({
            "schema_version": 1, "python_path": executable or sys.executable,
        }), encoding="utf-8")

    def payload(self, event):
        return {"session_id": "contract", "cwd": str(self.project),
                "hook_event_name": event, "source": "startup",
                "prompt": "Update generated clients from the API schema — café 日本語",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(self.project / "src/generated/api.py")}}

    def shells(self):
        if os.name == "nt":
            yield "cmd-host"
            for shell in ("powershell.exe", "pwsh.exe"):
                self.assertIsNotNone(shutil.which(shell), f"Required Windows test shell: {shell}")
                yield shell
            # Git Bash is not used to stand in for a native Unix runner.
        else:
            for shell in ("sh", "bash", "zsh"):
                executable = shutil.which(shell)
                if executable:
                    yield executable
            self.assertTrue(shutil.which("sh"), "POSIX shell required")
            if sys.platform == "darwin":
                self.assertTrue(shutil.which("zsh"), "Test the macOS default shell")

    def invoke(self, host, event, shell=None, payload=None):
        handler = json.loads((self.plugin / f"hooks/{host}.json").read_text())["hooks"][event][0]["hooks"][0]
        env = self.env.copy()
        prefix = "PLUGIN" if host == "codex" else "CLAUDE_PLUGIN"
        env[f"{prefix}_ROOT"] = str(self.plugin)
        env[f"{prefix}_DATA"] = str(self.data)
        if host == "claude":
            # Documented exec form: substitute each argument as data, no shell.
            argv = [self.node if handler["command"] == "node" else handler["command"]]
            argv += [arg.replace("${CLAUDE_PLUGIN_ROOT}", str(self.plugin)) for arg in handler["args"]]
        else:
            command = handler["commandWindows" if os.name == "nt" else "command"]
            if shell == "cmd-host":
                # Match Codex's raw outer-quoted command, not Python shell=True
                # or list2cmdline's escaping of the inner quotes.
                argv = f'"{os.environ.get("COMSPEC", "cmd.exe")}" /C "{command}"'
            elif os.name == "nt":
                argv = [shutil.which(shell), "-NoProfile", "-NonInteractive", "-Command", command]
            else:
                # Codex's default Unix runner uses the session shell with -lc.
                argv = [shell, "-lc", command]
        return subprocess.run(argv, input=json.dumps(payload or self.payload(event), ensure_ascii=False),
                              text=True, encoding="utf-8", capture_output=True,
                              cwd=self.root, env=env, timeout=handler["timeout"], check=False)

    def probe_engine(self, source=None):
        (self.plugin / "skills/session-learning/scripts/session_learning.py").write_text(
            source or "import json,sys\nprint(json.dumps({'payload':json.load(sys.stdin),'args':sys.argv[1:]}))\n",
            encoding="utf-8")

    def assert_success(self, result):
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", result.stderr)

    def test_all_packaged_events_reach_engine_with_intact_input(self):
        self.probe_engine()
        for host in ("codex", "claude"):
            for shell in (list(self.shells()) if host == "codex" else [None]):
                for event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "SessionEnd"):
                    with self.subTest(host=host, shell=shell, event=event):
                        result = self.invoke(host, event, shell)
                        self.assert_success(result)
                        output = json.loads(result.stdout)
                        self.assertEqual(self.payload(event), output["payload"])
                        self.assertEqual(["hook", "--data-dir", str(self.data), "--host", host], output["args"])

    def test_real_lesson_context_for_both_hosts_and_retrieval_events(self):
        lessons = self.learning / "lessons"
        lessons.mkdir()
        record = v1_lesson()
        record["delivery"].update({"mode": "dynamic", "host": None, "path": None,
                                   "instruction_path": "AGENTS.md", "enforcement_target": None})
        (lessons / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")
        (self.project / "AGENTS.md").write_text(session_learning._instruction_pointer_block(), encoding="utf-8")
        (self.project / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        session_learning.rebuild_index(self.project)
        for host in ("codex", "claude"):
            for shell in (list(self.shells()) if host == "codex" else [None]):
                for event in ("UserPromptSubmit", "PreToolUse"):
                    with self.subTest(host=host, shell=shell, event=event):
                        payload = self.payload(event)
                        payload["session_id"] = f"{host}-{shell}-{event}"
                        result = self.invoke(host, event, shell, payload)
                        self.assert_success(result)
                        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                        self.assertIn(record["id"], context)

    def test_missing_python_warns_once_without_executing_cache_as_code(self):
        self.configure_python(str(self.root / "missing-python"))
        self.env["PATH"] = ""  # Claude exec form uses the absolute Node binary.
        sentinel = self.root / "should-not-exist"
        (self.data / "python-launcher.txt").write_text(f"echo stolen > {sentinel}", encoding="utf-8")
        first = self.invoke("claude", "SessionStart")
        second = self.invoke("claude", "SessionStart")
        prompt = self.invoke("claude", "UserPromptSubmit")
        for result in (first, second, prompt):
            self.assert_success(result)
        self.assertIn("Python 3.10+", json.loads(first.stdout)["systemMessage"])
        self.assertEqual("", second.stdout)
        self.assertEqual("", prompt.stdout)
        self.assertFalse(sentinel.exists())

    def test_invalid_project_python_falls_back_to_personal_config(self):
        self.configure_python(str(self.root / "missing-python"))
        config = self.home / ".agents/session-learning/config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"schema_version": 1, "python_path": sys.executable}), encoding="utf-8")
        self.env["PATH"] = ""
        self.probe_engine()
        result = self.invoke("claude", "UserPromptSubmit")
        self.assert_success(result)
        self.assertEqual(self.payload("UserPromptSubmit"), json.loads(result.stdout)["payload"])

    def test_python_discovery_without_config_and_cached_repeat(self):
        (self.learning / "config.json").unlink()
        self.env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + self.env["PATH"]
        self.probe_engine()
        for _ in range(2):
            result = self.invoke("claude", "UserPromptSubmit")
            self.assert_success(result)
            self.assertEqual(self.payload("UserPromptSubmit"), json.loads(result.stdout)["payload"])
        self.assertIn((self.data / "python-launcher.txt").read_text().strip(), {"py", "python3", "python"})

    def test_engine_crash_or_timeout_never_leaks_partial_output(self):
        for body in ("raise SystemExit(1)", "import time; time.sleep(10)"):
            with self.subTest(body=body):
                self.probe_engine("print('partial', flush=True)\n" + body + "\n")
                result = self.invoke("claude", "UserPromptSubmit")
                self.assert_success(result)
                self.assertEqual("", result.stdout)

    def test_read_only_data_location_fails_open(self):
        # Portable deterministic equivalent of an unwritable directory.
        self.data = self.root / "not-a-directory"
        self.data.write_text("occupied", encoding="utf-8")
        result = self.invoke("claude", "UserPromptSubmit")
        self.assert_success(result)
        self.assertEqual("", result.stdout)


if __name__ == "__main__":
    unittest.main()
