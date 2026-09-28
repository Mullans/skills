# Schema Compatibility

Session Learning follows backward compatibility within one major version: the installed release reads lessons written by earlier releases in that major version. Older installations may reject newer schemas. A major-version change may require an explicit upgrade boundary.

Every current lesson carries both `schema_version`, which identifies its structure, and `version`, which identifies the skill release that last wrote it. New lessons use the installed values. Migration advances supported outdated lessons to the installed schema and replaces their `version` with the installed skill version; no separate migration-version field is retained. A readable lesson without `version` is legacy. An unreadable version is unknown.

The installed skill's `LESSON_SCHEMA_VERSION` is the migration target. Explicit invocation records supported outdated lessons as migration candidates, writes the requested new lesson first, reports that primary write as complete, and then offers migration:

```text
python <skill-root>/scripts/session_learning_migrate.py --root <project-root> --authority both --host <active-host>
```

Current or absent stores require no migration command. Declining or ignoring the offer leaves the new lesson committed and the compatible legacy lessons unchanged. When accepted, the script applies registered migrations one schema version at a time, migrates supporting evidence when required for store validity, rebuilds derived catalogs, validates the final store, and commits only migration changes transactionally. Re-running it remains a no-op, but routine no-op invocation is unnecessary.

Validation, search, index generation, and hook retrieval use the current in-memory shape for supported older lessons, so a mixed-version store remains usable while migration is pending. Schema 1–3 records receive their missing fields through registered upgrade steps; a schema 4 lesson written by 0.6.2 remains a migration candidate until its `version` is advanced. Rebuilding derived indexes can refresh hook catalogs without changing canonical lesson files. `audit` reports these records as `migration_candidates`, not validation errors.

An absent, invalid, unsupported, or newer `schema_version` is a hard stop. Preserve the affected records unchanged and report the incompatible file; never guess its shape or downgrade it. Hooks do not run migrations because retrieval hooks remain advisory and may not mutate canonical lessons.
