# Research retrieval

Use the catalog to find authored working-tree documentation, including untracked
notes and historical investigations without finding metadata. Source documents
remain canonical.

## Retrieve before planning

1. Use a known maintained reference directly when it answers the question within
   scope. Search when prior work is unknown or a material gap remains.
2. Search relevant terms and open applicable results. Refine terms or widen
   beyond a subject when coverage is insufficient.
3. Assess applicability and conflicting or later findings. Consult original
   evidence for additional detail, contradictions or a specific support concern.
   Search rank and file modification time do not establish correctness.
4. Stop when references answer the question or identify a material gap. Reuse
   evidence already inspected for the current question.

Run from the project root with its Python execution prefix. The script is
`scripts/workspace/research_catalog.py`.

| Task | Arguments after the script |
| --- | --- |
| Search | `search "resource ownership" --limit 5` |
| Open a finding | `show PROJECT-SUBJECT-001` |
| Open a source section | `show experiments/YYYYMMDD-question/RESULT.md#observation` |
| Continue results | Repeat the query with `--limit 5 --offset 5` |
| Continue a long section | `show LOCATOR`, using the returned continuation locator |
| Restrict search to a subject | Add `--subject ID`; omit it for unclassified or cross-topic work |
| Inspect coverage or failures | `status --limit 20` |

For example:

```sh
python scripts/workspace/research_catalog.py search "resource ownership" --limit 5
```

Add `--format json` to `search` or `show` for structured output. Lookups discover
current text automatically; no separate refresh or manual registration is needed.
Sections/results are bounded, but indexing reads complete eligible source files.
If an editing-sensitive locator stops resolving, search again.

## Coverage and review

[config.json](config.json) owns searchable paths, exclusions and limits;
[subjects.json](subjects.json) owns navigation names, aliases and entry points.
Defaults index configured Markdown in `docs/` and `experiments/`. Add selected
entry points and research-tool or legacy paths through configuration when needed.
Tool-documentation coverage is not implicitly comprehensive.

Raw artifacts are reached through authored references rather than content-indexed.
Configured exclusions determine which Markdown is omitted. Keep review drafts
excluded. Copies and summaries are not independent evidence; navigation review
does not certify every linked technical claim.

| Result or label | Meaning and next action |
| --- | --- |
| Successful zero matches | These terms did not match within reported coverage; refine or inspect relevant paths rather than infer no prior work |
| Incomplete or failed retrieval | Inspect failures and search relevant paths directly; missing results do not establish absence |
| `complete` | The eligible source set was indexed, not all research completed or reviewed |
| Unreviewed source | Recognized finding metadata is absent; this does not invalidate a maintained reference |
| Changed or missing reviewed support | Review affected support; a warning does not automatically reverse a claim or require another experiment |
| Unavailable locator | Search for the current section or finding |
| Invalid subject metadata | Use unfiltered body search while navigation is repaired; an unknown `--subject` fails rather than widening search |

## Finding convention

Use the [reference template](../reference-template.md#verified-finding-unit) for
finding fields. For reviewed support, record the actual relative source link and
section fingerprint from `show` (`Section SHA256`, or `section_sha256` in JSON).
Use the substantive review date, not file modification time.

Malformed or duplicate finding IDs are withheld as structured findings; ordinary
source text remains searchable. Support warnings concern the finding's linked
section, not unrelated changes elsewhere in a document.

## Maintenance and failures

New text is discovered on lookup. Select focused checks for implementation,
configuration or finding-metadata changes; do not require a refresh/check/test
sequence for ordinary lookup or every text addition. `check` reports coverage,
metadata, reviewed-support and configured retrieval-regression failures.

For partial or failed retrieval, use targeted source search on explicit relevant
paths and report narrower coverage. A cache-publication warning can accompany
fresh usable results; discovery/configuration failure cannot support a zero-match
conclusion.

The [catalog implementation](../../../scripts/workspace/research_catalog.py)
owns parser, cache, retry and failure details. Generated catalog JSON is disposable,
not source evidence.
