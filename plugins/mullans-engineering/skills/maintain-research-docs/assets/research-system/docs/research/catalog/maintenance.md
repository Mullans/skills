# Research reference maintenance

Use these local commands and configuration for organizational audits and approved
reference-maintenance batches. Direct corrections and routine promotion do not
require this batch process.

## Commands

Run from the project root with its Python execution prefix. The script is
`scripts/workspace/research_docs.py`.

| Task | Arguments after the script |
| --- | --- |
| Audit reference organization | `audit` |
| Obtain structured audit results | `audit --format json` |
| Create a proposal for flagged pages | `propose --output experiments/YYYYMMDD-reference-review/proposal.json` |
| Select particular registered or discovered pages | Add `--paths PATH PATH` to `propose`, including pages below size thresholds |
| Finalize after the approved document commit | `finalize --proposal experiments/YYYYMMDD-reference-review/proposal.json` |
| Preview without writing | Add `--dry-run` to `finalize`; this is optional |

For example:

```sh
python scripts/workspace/research_docs.py audit
```

Proposal creation records pending items and refuses overwrite. Finalization records
accepted baselines; it does not apply patches or commit documents. Commit finalized
registry metadata separately when authorized.

## Local owners

| Item | Location or interface |
| --- | --- |
| Page classifications, thresholds, overrides and accepted baselines | [maintenance.json](maintenance.json) |
| Proposals, review decisions, drafts and unresolved work | The owning `experiments/<id>/` record; proposed copies belong in its `drafts/` directory |
| Source validation immediately before applying approved patches | `validate_sources(root, bundle)` in the [installed tool](../../../scripts/workspace/research_docs.py) |
| Selective commit of approved outputs | `commit_batch(root, proposal_path, message)` in the installed tool; scoped staging is also supported |
| Schema, measurements and transaction mechanics | The installed tool and its [Markdown helper](../../../scripts/workspace/research_markdown.py) |

The source validator and selective commit helper are Python APIs, not CLI
subcommands. Installed implementations may differ from newer packaged versions.

## Outcomes and recovery

| Result | Meaning or action |
| --- | --- |
| Audit exit `0` | Complete audit with no reviews required |
| Audit exit `1` | Complete audit with reviews identified, not an execution failure |
| Audit exit `2` | Incomplete coverage or measurement; inspect reported errors |
| Propose/finalize exit `0` | Operation succeeded; inspect returned items or updates |
| Propose/finalize exit `2` | Resolve the failure before continuing the affected operation |
| Size or accumulated-change flag | Assess organization; a flag does not mandate splitting |
| Unclassified or not-yet-onboarded page | Assess ownership/onboarding even below size thresholds |
| Changed approved input or result | Reconcile the affected proposal and approval |
| Failed finalization after document commit | Preserve the commit; resolve the mismatch before retrying |
| Existing lock | Investigate the owner before manual recovery |

Ordinary edits and pending/rejected items do not update accepted baselines.
Organizational acceptance does not certify technical claims.
