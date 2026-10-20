# Schema Compatibility

Read for an old storage location, migration candidates, or version errors.

## Storage location

Project state belongs in `<project>/.session-learning`. If `<project>/.agents/learning` exists, move its contents to the current location from the normal terminal and update the learning-index pointer in project instructions. If both directories exist, reconcile them before moving; do not overwrite either store. There is no automatic relocation or old-location fallback. Personal project-scoped storage is unchanged.

## Version checks

The runtime currently writes lesson schema 4 and evidence schema 2. Manifest schema 3 is current; schema 2 remains supported without revision/receipt fields. The installed runtime owns supported upgrades.

`schema_version` describes record structure; lesson `version` identifies the skill release that last wrote it. A skill release bump alone requires no migration. Supported schema 1–3 lessons may lack `version`; schema 4 requires a valid writing version within the installed major version. Same-major older/prerelease writing versions remain valid.

Stop on missing, invalid, unsupported, or newer schemas, or an invalid/incompatible writing version. Preserve affected records and report the error; do not guess, downgrade, or treat invalid records as migration candidates.

## Optional migration

Supported older records normalize in memory and remain usable. `audit` lists them as `migration_candidates`, not validation errors.

1. Complete the requested canonical write and report it saved.
2. Offer migration only when candidates remain. Declined, unanswered, or failed migration leaves that write intact.
3. On acceptance, run:

```text
python <skill-root>/scripts/session_learning_migrate.py --root <project-root> --authority both --host <active-host>
```

The helper upgrades supported records and any required evidence, rebuilds derived state, validates, and commits transactionally. Current or absent stores need no migration command; repeating a completed migration is a no-op. Hooks never migrate records. Use `rebuild-index` for missing derived catalogs, not schema migration.
