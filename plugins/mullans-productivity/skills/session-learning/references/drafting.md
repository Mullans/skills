# Lightweight Drafting

Load only through `draft-context` after a meaningful learning moment in an enabled project. Continue the primary task after one compact capture; perform full reconciliation in the explicit retrospective.

Capture a specific user correction, verified non-obvious recovery, useful discovery, or successful workflow whose omission could meaningfully affect a comparable future task. Ordinary success, exploratory failures, retries, praise, and transient task state are not learning moments. Preserve both strengths and weaknesses without fabricating a failed baseline or successful verification.

Run `save-draft - --root <project> --home-dir <home>` with JSON on standard input (omit the home override in normal use):

Send the payload from an in-memory literal. Do not create draft input files in the repository. If a new scratch input file is necessary, use the host's temporary directory and remove it after the attempt.

```json
{
  "target_authority": "project",
  "source": {"host": "codex", "session_id": "visible-session-id", "event_ids": ["visible-event-id"]},
  "signal": "explicit_user_correction",
  "observation": {
    "situation": "A generated response needed to change.",
    "attempted_behavior": "Edited generated output directly.",
    "feedback": "The schema is the source of truth.",
    "corrected_behavior": "Updated the schema and regenerated output.",
    "outcome": "Targeted contract checks passed."
  },
  "proposed_guidance": {
    "statement": "Update the source schema before regenerating this client.",
    "scope": {"type": "paths", "paths": ["schemas/**", "src/generated/**"]},
    "triggers": ["generated response"],
    "safe_path": ["update source schema", "regenerate client", "verify contract"],
    "exceptions": []
  },
  "verification_gaps": []
}
```

Use the visible host/session/event identities. If stable event IDs are absent, use a short source anchor identifying the visible correction or result, without reconstructing history. Allowed signals are `explicit_user_correction`, `test_failure`, `runtime_failure`, `ci_failure`, `review_finding`, `durable_user_convention`, `validated_workflow`, and `successful_non_obvious_discovery`. Historical `recovery_pair` is unavailable here. Mark an unresolved outcome as unverified and describe the verification gap explicitly.

Keep each contrast field within 500 characters. Retain sanitized descriptions rather than commands, outputs, prompts, logs, secrets, or absolute paths. Use `<project>` and `<home>` placeholders. Store proposed authority, narrow scope, triggers, safe action, and exceptions; drafts are observations, not instructions.

Exact equivalent content is deduplicated even across sessions. Revising a source draft requires `--draft-id` and `--expected-sha256` from its pending view. New evidence or changed interpretation can reopen a terminal record through that guarded revision. Capture cannot activate lessons or alter project files. A failed/disabled save ends this capture attempt; do not redirect to repository memory or retry repeatedly.

Leave review and acceptance to the explicit retrospective. This capture attempt grants no canonical authoring authority.
