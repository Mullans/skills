# Session Learning Decision Policy

Use this policy on every invocation. The canonical store is `.agents/learning` under the resolved project root.

## 1. Inspect and measure before learning

Read applicable project instructions, existing learning records, relevant repository skills, and enforcement. Search related lessons with:

```text
python <skill-root>/scripts/session_learning.py search --root <project-root> <terms>
```

Measure only lessons that were active before the session began and whose paths, operations, or triggers clearly occurred. The session that creates a lesson supplies provenance, not a usage opportunity; initialize new lessons with zeroed usage fields.

For each eligible pre-existing lesson:

- increment `eligible_sessions` and set `last_eligible_at`;
- increment `violations` and set `last_violated_at` when any attempted behavior opposed it;
- also increment `repeat_corrections` when the user, tests, runtime, CI, or review repeated the underlying correction;
- otherwise, increment `confirmations` and set `last_confirmed_at` only when the session followed it and the outcome succeeded.

Violation and confirmation are mutually exclusive for one lesson in one session: later correction does not convert that session into a confirmation. Do not update an irrelevant lesson. Do not infer that a lesson was retrieved merely because behavior matched it.

## 2. Extract evidence events

Evidence signals are:

- `explicit_user_correction`
- `test_failure`, `runtime_failure`, or `ci_failure`
- `review_finding`
- `durable_user_convention`
- `validated_workflow`
- `successful_non_obvious_discovery`

An evidence record must preserve a compact contrast: situation, attempted behavior, feedback, corrected behavior, and outcome. Do not store raw conversation text, tool logs, secrets, or unrelated session narrative.

## 3. Apply the hard gates

A candidate survives only if all answers are yes:

1. Is it traceable to evidence from this session?
2. Would it change a future decision or behavior?
3. Is it non-default and project-specific?
4. Could it recur, or would forgetting it be materially costly?
5. Are its trigger, narrowest stable scope, and safe action clear?
6. Is it generalized one conceptual level beyond the incident—neither file-specific nor vague?
7. Has it been reconciled with existing lessons, instructions, skills, and enforcement?
8. Is prose or procedural memory appropriate, rather than existing mechanical enforcement?

Reject generic advice, praise, ordinary success, conversational style preferences without durable intent, temporary work state, and details with no transferable decision.

## 4. Decide status and relation

Auto-promote to `active` only when every hard gate passes and all are true:

- corrected behavior succeeded or authoritative repository evidence confirms it;
- scope and destination are unambiguous;
- no unresolved conflict remains;
- the change is limited to learning records, native project guidance, or a fully established local workflow.

One explicit correction is enough when the correction, validation, scope, and consequence are clear. Otherwise retain an evidence-bearing item as `candidate`. Use `conflicted` when credible evidence contradicts active guidance but does not safely resolve the required behavior. A plausibly transient failure with no rule-specific signal is not a conflict and produces no lesson.

Classify the semantic relation:

| Relation | Action |
|---|---|
| `new` | Add a distinct candidate or active lesson. |
| `duplicate` | Add provenance and measurement to the existing lesson; create no new rule. |
| `refines` | Modify the existing lesson with a narrower statement or meaningful exception. |
| `extends` | Broaden scope only when evidence supports the broader applicability. |
| `conflicts` | Preserve active guidance and store a `conflicted` candidate unless decisive evidence resolves it. |
| `supersedes` | Mark old guidance `superseded` and replace its projection only after explicit, validated correction. |
| `obsoletes` | Retire guidance only when the underlying behavior is demonstrably gone or mechanically enforced. |

## 5. Classify and route

| Kind | Destination |
|---|---|
| `guardrail` | Concise ID-tagged rule in the narrowest native instruction file. |
| `project_knowledge` | Active record plus generated index; add the managed index pointer to native instructions. |
| `workflow` | Native repository-local skill only if exact steps, commands, recurrence, and successful verification are established. |
| `preference` | Native project instructions only when explicitly durable and project-scoped. |
| `invariant` | Existing enforcement when present; otherwise candidate with `automation` destination. |

### Host and scope detection

1. Use the active runtime identity when it is known.
2. Inspect applicable existing `AGENTS.md` and `CLAUDE.md` hierarchies.
3. If both exist, project only to the active host. Never mirror automatically.
4. If neither exists, Codex uses `AGENTS.md` and `.agents/skills`; Claude uses `CLAUDE.md` and `.claude/skills`.
5. Use the deepest instruction file whose subtree covers every applicable path. Do not place a subsystem lesson at repository root for convenience.

Every active instruction or skill projection must contain `session-learning:<lesson-id>`. The managed contextual pointer must contain `session-learning:index` and say, in substance:

> Project-specific learned context is indexed at `.agents/learning/index.md`. When a task matches a listed path, scope, or trigger, load only the matching active lesson records. Candidates are not instructions.

## 6. Record schemas

Store records one per file under the canonical project store:

- `.agents/learning/lessons/<lesson-id>.json`
- `.agents/learning/evidence/<evidence-id>.json`
- `.agents/learning/cases/<case-id>.json`
- `.agents/learning/index.md`, generated from lesson records

Use lowercase stable IDs such as `lesson.generated-files.001`, `evidence.20260827.generated-files.001`, and `case.generated-files.001`. The filename must be `<id>.json`.

### Lesson

```json
{
  "schema_version": 1,
  "record_type": "lesson",
  "id": "lesson.generated-files.001",
  "title": "Generated API clients",
  "statement": "When changing generated clients, update the schema and regenerate; do not edit generated output directly.",
  "kind": "guardrail",
  "status": "active",
  "scope": {"type": "paths", "paths": ["schemas/**", "src/generated/**"]},
  "triggers": ["generated clients", "API schema"],
  "anti_pattern": ["direct edits to generated output"],
  "safe_path": ["update schema", "regenerate", "verify generated diff and tests"],
  "exceptions": [],
  "destination": {"type": "instruction", "host": "codex", "path": "AGENTS.md"},
  "provenance": [{"evidence_id": "evidence.20260827.generated-files.001", "signal": "explicit_user_correction"}],
  "relationships": {"supersedes": [], "related": []},
  "usage": {
    "eligible_sessions": 0,
    "confirmations": 0,
    "violations": 0,
    "repeat_corrections": 0,
    "last_eligible_at": null,
    "last_confirmed_at": null,
    "last_violated_at": null
  },
  "timestamps": {"created_at": "<ISO-8601>", "updated_at": "<ISO-8601>"}
}
```

Allowed statuses: `candidate`, `active`, `conflicted`, `superseded`, `retired`.

Destination types are `instruction`, `index`, `skill`, `automation`, `evidence_only`, or `none`. An index destination also supplies `instruction_path`; `none` and `evidence_only` use null host/path values.

### Evidence

```json
{
  "schema_version": 1,
  "record_type": "evidence",
  "id": "evidence.20260827.generated-files.001",
  "session_id": "<stable available session identifier or date-based local identifier>",
  "signal": "explicit_user_correction",
  "situation": "An API response changed.",
  "attempted_behavior": "Edited generated clients directly.",
  "feedback": "The schema is the source of truth.",
  "corrected_behavior": "Updated the schema and regenerated clients.",
  "outcome": "Targeted tests passed.",
  "created_at": "<ISO-8601>"
}
```

### Regression case

Create only for a high-value decision worth replaying:

```json
{
  "schema_version": 1,
  "record_type": "case",
  "id": "case.generated-files.001",
  "lesson_ids": ["lesson.generated-files.001"],
  "situation": "A generated client exposes an old response shape.",
  "trap": "Patch generated output directly.",
  "expected": "Change the schema, regenerate, and verify the diff.",
  "created_at": "<ISO-8601>"
}
```

## 7. Write safely

Do not create `.agents/learning`, its generated index, or managed instruction markers unless an evidence-bearing lesson or informative candidate will persist. A no-op retrospective must be filesystem-neutral.

Compute the complete reconciliation first and retain pre-write contents for files that will change.

1. Write evidence.
2. Create a new lesson as `candidate`; for an existing lesson, delay its mutation until its projection is ready.
3. Apply the smallest native projection, using managed markers.
4. Finalize lesson status and relationships.
5. Run `rebuild-index`.
6. Run `validate`.

If a later step fails, do not claim success. Repair immediately. If repair is impossible, restore pre-write projections and leave new lessons non-authoritative. Never leave an active lesson whose required projection is absent.

## 8. Report narrowly

For a no-op: report that no evidence-backed lesson was found and no files changed.

For changes: list lesson IDs, relations, statuses, destinations, measured prior-lesson changes, and informative conflicts or deferrals. Do not retell the session.
