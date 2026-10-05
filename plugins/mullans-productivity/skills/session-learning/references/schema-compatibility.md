# Schema Compatibility

## Patch release 0.8.1

Retrospective diagnosis and recommendation guidance change without altering lesson schema 4 or evidence schema 2. Skill release changes alone do not require record migration. Migration eligibility depends on a supported older record schema, not the age of its writing skill version.

## Additions in 0.8.0

Lesson schema 4 and evidence schema 2 remain unchanged. Manifest schema 3 adds authority revision guards and idempotent acceptance receipts; legacy manifest schema 2 remains readable without those fields. Draft schema 1, configuration schema 1, and activity/receipt schema 1 occupy separate stores. These additions alone require no record migration. Existing supported lessons continue to normalize in memory; ordinary migration policy remains unchanged.

## Project storage in 0.7.0

Project state is read and written only at `<project>/.session-learning`. Move older stores as described in [SKILL.md](../SKILL.md#retrospective) before using 0.7.0; there is no old-location fallback or automatic relocation. The folder contents and record schemas are unchanged by this path change. Personal project-scoped local authority retains its separate hashed home store.

## Record schema migration

Record schemas remain readable within one major version: the installed release reads supported records written by earlier releases, once they are in the current storage location. Older installations may reject newer schemas. Storage-path compatibility is separate from record-schema compatibility; 0.7.0 requires the manual folder move.

Every current lesson carries both `schema_version`, which identifies its structure, and `version`, which identifies the skill release that last wrote it. New lessons use the installed values. Schema migration advances supported older lessons to the installed schema and stamps the writing skill version when the registered upgrade writes that field. A current-schema lesson retains its writing version, including older same-major releases or prereleases; a release bump alone never rewrites it. Supported schema 1–3 lessons without `version` are legacy. A missing or invalid writing version in schema 4, or one outside the installed major version, is a validation error requiring repair rather than a migration offer.

The installed skill's `LESSON_SCHEMA_VERSION` is the migration target. Explicit invocation records supported outdated lessons as migration candidates, writes the requested new lesson first, reports that primary write as complete, and then offers migration:

```text
python <skill-root>/scripts/session_learning_migrate.py --root <project-root> --authority both --host <active-host>
```

Current or absent stores require no migration command. Declining or ignoring the offer leaves the new lesson committed and the compatible legacy lessons unchanged. When accepted, the script applies registered migrations one schema version at a time, migrates supporting evidence when required for store validity, rebuilds derived catalogs, validates the final store, and commits only migration changes transactionally. Re-running it remains a no-op, but routine no-op invocation is unnecessary.

Validation, search, and index generation normalize supported older lessons in memory, so a mixed-schema store remains usable while migration is pending. Schema 1–3 records receive their missing fields through registered upgrade steps; a valid schema 4 lesson written by 0.6.2 requires no migration and remains unchanged. Hooks normally read the derived retrieval catalog. If it is missing or unreadable, they build a bounded read-only view from valid canonical lessons; `rebuild-index` restores the fast path without changing those lessons. `audit` reports supported older lesson schemas as `migration_candidates`, not validation errors.

An absent, invalid, unsupported, or newer `schema_version` is a hard stop. Preserve the affected records unchanged and report the incompatible file; never guess its shape or downgrade it. Hooks do not run migrations because retrieval hooks remain advisory and may not mutate canonical lessons.
