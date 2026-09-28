# Project Instructions

## Git/GitHub Interaction

- Local or read-only operations (e.g. pull, stage, commit, fetch, log, status, etc.) can be handled by the agent.
- Any significant, non-transient change to the repository should be staged and commited to the repository.
- Remote operations (e.g. push, clone, workflows, PRs, merging, etc.) REQUIRE explicit authorization from the user. Authorization of one action does not authorize subsequent actions (e.g. If the user authorizes the creation of a PR, updating the existing PR in the same session is allowed, but closing/merging the PR or opening a new PR is forbidden unless the user authorizes the new action.)

## Python and Scripts

- use `rtk uv` for Python interaction - for example `rtk uv run script.py` or `rtk uv add {package}`.
- Do NOT use `rtk proxy` for Python-related interactions.

## Local Validation

- Use `temp_{os}_live_fixture` as a temporary directory for live validation of the skills. This directory is ignored by Git.

<!-- session-learning:index -->
- Project-specific learned context is indexed at `.agents/learning/index.md`. When a task matches a listed path, scope, or trigger, load only the matching active lesson records. Candidates are not instructions.
