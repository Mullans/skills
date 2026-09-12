# Validation and measured claims

Choose checks for actual installed mechanisms. Skill metadata validation alone does not demonstrate correct repository setup.

## Target-repository checks

1. Compare final changes with initial status and effective instructions. All prior coding, security, verification, review, and Git requirements must survive. Content outside managed additions remains unchanged. Inspect any formatter changes before keeping them.
2. Resolve every installed link/import from its real source location. Check actual client discovery if available; distinguish it from filesystem validation.
3. Compare the same scoped searchable inventory before and after exclusions. Validate representative authored source, tests, fixtures, hidden configuration, and any tracked paths matching a new exclusion. Remove or narrow exclusions that hide authored work. Test the scoped absence-check path too.
4. For a new wrapper, run harmless commands that succeed, fail with a known nonzero code, emit both streams, produce one long line, and fail to launch. Check status, bounded output, complete log content, and unique paths on concurrent runs. Verify supported interruption behavior. Use paths/arguments with spaces and literal shell metacharacters. A wrapper failing these checks is not ready to install.
5. Run the target's applicable checks without changing their scope or excluding new files from lint/CI to make them pass. Preserve unavailable checks as outstanding evidence.
6. Repeat setup against the resulting state. Compare file contents before and after, rather than expecting a clean Git status in an initially dirty repository. There should be no new changes from the second run. Test locally edited generated content before claiming upgrade safety.

## Forward-testing this skill

For a substantial skill revision, exercise these scenarios in isolated scratch directories with no publication or global configuration changes:

| Scenario | Observable acceptance |
| --- | --- |
| Empty directory; language undecided | Minimal reachable efficiency guidance, no invented framework/test/branch policy, no runtime dependency |
| Existing repo; custom instructions and dirty files | Original requirements and edits preserved; additions follow local conventions |
| Existing complete efficiency setup | Reuse/no-op; no duplicate wrapper, policy, or skill |
| Authored `build/`, fixtures, nested clone, hidden config | Search scope retains authored work and respects repository boundaries |
| Rerun after local customization | No duplicate blocks or silent overwrite |
| Missing ripgrep or helper runtime | Working shallow fallback and honest limitation; no automatic global install |
| Audit-only request | Findings and proposed paths, zero target writes |

Use independent behavioral evaluation when authorized and useful. Give the evaluator the request and fixture, not the expected solution. Inspect its produced files, not just its self-report.

## Evidence and rollback

Record only measured values: inventory counts, raw versus displayed bytes/lines, and commands/checks actually run. Keep scope identical across before/after measurements; an unsafe reduction in searchable source is a regression. Report token usage, truncation rate, duplicate activations, or continuation savings only when actual instrumentation captures them. Synthetic wrapper tests demonstrate output handling, not real-world model savings.

Give rollback paths and specific added blocks. Remove only unchanged files created by setup; reverse only setup hunks in shared files. Preserve newer local changes. Do not recommend reset/clean or whole-file restoration over a dirty working tree.
