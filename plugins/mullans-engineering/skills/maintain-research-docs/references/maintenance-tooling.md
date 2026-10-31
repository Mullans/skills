# Maintenance tooling

Use for proposal preparation, Python API calls or interrupted maintenance.
These are contracts of the bundled documentation tools, not recovery procedures
for an experiment's external system.

The [maintenance implementation](../assets/research-system/scripts/workspace/research_docs.py)
and [Markdown helper](../assets/research-system/scripts/workspace/research_markdown.py)
own exact behavior. Read the installed project copy when it differs: older tools
may not implement all the safeguards below. Do not silently upgrade tools or
assume a newer package's behavior is present.

## Interfaces and proposal fields

The CLI exposes `audit`, `propose` and `finalize`. Source validation and selective
committing are Python APIs, not additional CLI commands. Local command prefixes
and configured thresholds belong to the project.

Use `propose` to create the initial bundle; do not reconstruct its measurements
or source identities manually. Complete the fields needed for selected changes:

| Field | Purpose |
| --- | --- |
| `registry_sha256`, schema/measurement versions, batch identity | Generated configuration and transaction identity |
| `items[].id`, `action`, `approval`, `rationale` | Item identity, retain/split/onboard decision, human disposition and reason |
| `sources` | Reviewed paths and raw-byte SHA256 values |
| `patches` | Reviewed patch paths and raw-byte SHA256 values, when used |
| `outputs` | Exact resulting paths, IDs, roles, onboarding state and raw worktree hashes |
| `outputs[].track: false` | Validate auxiliary navigation/evidence without registering a reference page |
| `unit_ownership`, `content_relocations`, `factual_changes` | Explain ownership, movement and substantive changes |
| `citation_support`, `technical_evidence`, `unresolved` | Review disposition and issues preventing finalization |
| `retire` | Registered page IDs replaced by this result |
| `deleted_paths` | Approved file deletions, distinct from retired registry IDs |

Set `citation_support` to `accepted` after assessing the relevant support. Use
`technical_evidence: unchanged` for preserved reviewed claims or `reviewed` for
substantive changes actually reviewed. Mechanical moves do not require re-proving
unchanged claims. Structural citation lint cannot establish semantic correctness.
Do not update support fingerprints merely to hide warnings.

Each approved item needs a rationale, resolved issues and declared outputs.
Pending/rejected items are not finalized. Renames/splits require explicit
destinations and appropriate retired IDs/deleted paths; one does not imply the other.

## Source validation

From the project root, immediately before applying approved patches:

```python
import json
from pathlib import Path
from scripts.workspace import research_docs

root = Path.cwd()
proposal_path = "experiments/YYYYMMDD-reference-review/proposal.json"
bundle = json.loads((root / proposal_path).read_text(encoding="utf-8"))
research_docs.validate_sources(root, bundle)
```

Apply the reviewed changes only after this succeeds. The validator checks source
and patch hashes for approved items only; an all-pending bundle does not validate
those items.

If review-time validation of pending items is useful, deep-copy the bundle,
temporarily mark only the intended items approved in that copy, and validate it.
Confirm and report the selected IDs. Never alter saved approvals for this purpose;
the check grants no application or commit authority.

## Document commit

Use ordinary scoped staging when it preserves unrelated work. Alternatively,
call the existing selective commit API after applying approved outputs:

```python
revision = research_docs.commit_batch(
    root, proposal_path, "Apply approved reference maintenance"
)
```

The helper checks approved hashes, includes declared deletions, rejects
overlapping pre-existing staged changes and uses an isolated index. It applies
Git's path-specific clean filters and checks whitespace. Unrelated regular-index
entries are preserved.

Approval hashes describe raw worktree bytes. Git-normalized content describes
HEAD/index identity; baseline hashes describe committed bytes. These can differ
because of line-ending conversion or clean filters. Do not replace an approval
hash with a committed-blob hash to force agreement.

A commit may succeed before regular-index synchronization fails. The error
identifies the created commit and preserves conflicting staged work. Inspect that
commit and reported state before retrying; do not assume there was no commit.

## Measurements and finalization

Registry defaults and page overrides own threshold values. The implementation
counts visible words and reference units, with fenced code excluded from size
but included in comparison. Formatting, citation destinations and mechanical
review metadata are normalized or excluded as defined by the Markdown helper.

For retained pages, Git word-diff change is:
`100 * max(added_words, removed_words) / baseline_words`.
Oversized empty-baseline cases avoid division by zero. Review triggers do not
mandate splitting. Ordinary edits do not reset baselines, so relevant changes
accumulate. Incompatible measurement versions or missing Git objects require
resolution rather than a substitute baseline.

Finalize the approved bundle after its document commit. Dry-run is optional.
The packaged implementation checks:

- Approved raw worktree bytes and Git-normalized HEAD/index/document identity.
- Reviewed patch hashes and supporting sources not replaced by outputs.
- Registry identity, allowing an exact already-finalized result to be repeated.
- Declared deletions absent from worktree, HEAD and index.
- Page classifications, unit identities and structural citation requirements.

All approved items are checked before registry publication. The tool locks
finalization, rechecks relevant state and replaces the registry atomically.
A failed item prevents that registry update. Pending/rejected items remain
unresolved; a successful repeat is idempotent.

## Interrupted maintenance operations

| Reported condition | Recovery |
| --- | --- |
| Reviewed source, patch or output changed | Reconcile the affected result and approval; do not silently accept different content |
| Registry changed since proposal | Refresh the affected review unless the exact result is already present |
| Documents committed but finalization failed | Keep the commit, fix the reported mismatch and retry finalization |
| Commit created but index synchronization failed | Inspect the identified commit and staged work; preserve unrelated entries |
| Finalization or Git index lock held | Investigate ownership/state before authorized manual recovery; do not take over an unexplained lock |
| Required Git object unavailable | Recover the actual comparison object or report the prerequisite; do not substitute another revision |
| Pending/rejected item or unresolved issue | Leave its baseline unchanged and report the missing decision or evidence |

The packaged finalization lock is under
`local/research-doc-maintenance/finalize.lock`; installed versions may differ.
Do not automatically remove locks, replay commits or reset a registry to make a
batch appear complete.
