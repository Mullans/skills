# Agent efficiency

Apply these mechanisms under the repository's existing engineering and verification requirements. During setup, retain only applicable sections and replace generic locations with verified local commands and paths.

## Inspection

Inventory the owning repository before expanding a search. Locate headings, symbols, or filenames, then read the relevant section. Start diff review with changed paths and expand to required hunks. After truncated output, narrow the query. Search exclusions reduce scope; verify absence using tracked paths and a scoped ignore-bypassing search when needed.

## Execution

For noisy commands, use the configured bounded-output mechanism and retain full logs. Read selected failure evidence from the saved log. Check actual exit status, not summary wording. Run focused checks during iteration where useful and all repository-required checks at their existing gates.

## Continuity

For interrupted or long work, save task-specific state with repository/branch/HEAD, owned changes, evidence, remaining requirements, and the next concrete action. Link durable decisions. Recheck mutable state when resuming. When delegation is authorized, share the relevant scope and evidence rather than asking every agent to rediscover the repository.
