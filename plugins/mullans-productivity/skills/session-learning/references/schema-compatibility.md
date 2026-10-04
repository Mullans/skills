# Schema Compatibility

## Additions in 0.8.0

Lesson schema 4 and evidence schema 2 remain unchanged. Manifest schema 3 adds authority revision guards and idempotent acceptance receipts; legacy manifest schema 2 remains readable without those fields. Draft schema 1, configuration schema 1, and activity/receipt schema 1 occupy separate stores. These additions alone require no record migration. Existing supported lessons continue to normalize in memory; ordinary migration policy remains unchanged.

## Project storage in 0.7.0

Project state is read and written only at `<project>/.session-learning`. Move older stores as described in [SKILL.md](../SKILL.md#retrospective) before using 0.7.0; there is no old-location fallback or automatic relocation. The folder contents and record schemas are unchanged by this path change. Personal project-scoped local authority retains its separate hashed home store.

## Record schema migration

Record schemas remain readable within one major version: the installed release reads supported records written by earlier releases, once they are in the current storage location. Older installations may reject newer schemas. Storage-path compatibility is separate from record-schema compatibility; 0.7.0 requires the manual folder move.

Every current lesson carries both `schema_version`, which identifies its structure, and `version`, which identifies the skill release that last wrote it. New lessons use the installed values. Migration advances supported outdated lessons to the installed schema and replaces their `version` with the installed skill version; no separate migration-version field is retained. A readable lesson without `version` is legacy. An unreadable version is unknown.

The installed skill's `LESSON_SCHEMA_VERSION` is the migration target. Explicit invocation records supported outdated lessons as migration candidates, writes the requested new lesson first, reports that primary write as complete, and then offers migration:

```text
python <skill-root>/scripts/session_learning_migrate.py --root <project-root> --authority both --host <active-host>
```

Current or absent stores require no migration command. Declining or ignoring the offer leaves the new lesson committed and the compatible legacy lessons unchanged. When accepted, the script applies registered migrations one schema version at a time, migrates supporting evidence when required for store validity, rebuilds derived catalogs, validates the final store, and commits only migration changes transactionally. Re-running it remains a no-op, but routine no-op invocation is unnecessary.

Validation, search, and index generation normalize supported older lessons in memory, so a mixed-version store remains usable while migration is pending. Schema 1–3 records receive their missing fields through registered upgrade steps; a schema 4 lesson written by 0.6.2 remains a migration candidate until its `version` is advanced. Hooks normally read the derived retrieval catalog. If it is missing or unreadable, they build a bounded read-only view from valid canonical lessons; `rebuild-index` restores the fast path without changing those lessons. `audit` reports supported older records as `migration_candidates`, not validation errors.

An absent, invalid, unsupported, or newer `schema_version` is a hard stop. Preserve the affected records unchanged and report the incompatible file; never guess its shape or downgrade it. Hooks do not run migrations because retrieval hooks remain advisory and may not mutate canonical lessons.
