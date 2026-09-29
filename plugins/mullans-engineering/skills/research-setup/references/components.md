# Languages, tools, and distributables

Standardize responsibilities; choose paths using the actual ecosystem. Document
component roots and concise run/test/build entry points in `docs/toolchain.md`.
Keep dependency declarations in manifests and lockfiles rather than duplicating
dependency lists in prose. Record runtime requirements and relevant verified
versions, with dates and limitations where needed.

| Situation | Decision |
| --- | --- |
| No code yet | Keep core source/script/test roles; defer runtimes and manifests. |
| Python only | Prefer conventional package layout, isolated environment, declared dependencies and appropriate lock mechanism; preserve an existing manager. |
| JavaScript only | Use the chosen stack's package manifest, lockfile, scripts, and tests. |
| Both initially | Choose component roots with clear manifest and environment ownership; define interfaces between them. |
| Python then JavaScript | Add an isolated JavaScript component; preserve Python paths and commands unless an approved migration has a concrete benefit. |
| JavaScript then Python | Add an isolated Python component; preserve existing JavaScript paths and commands. |
| Other language added | Apply the same component/environment ownership principles using its conventions. |

For example, a root Python package can coexist with `src/web/` containing a
JavaScript package and its manifest; two substantial components can instead have
their own roots. These are options, not a mandatory monorepo structure. Tests may
be in top-level or conventional component-local locations, with one documented
route to relevant checks. Avoid accidental import/package collisions and implicit
dependence on whichever environment happened to be active.

`src/` owns maintained reusable logic. `scripts/` owns runnable research and
maintenance entry points. Small one-off utilities can remain scripts; promote
substantial or recurring logic into modules with thin runners. Prefer useful
arguments, sensible defaults, and named configuration profiles over either copied
scripts or long repeated command lines. Record effective configuration when it
affects interpretation; convenient defaults must not hide it.

For Python, `pyproject.toml`, an isolated `.venv`, and a lockfile are a useful
default when the selected tooling supports them. For JavaScript, use the package
manager's normal manifest and lockfile. Keep environments and dependency trees
untracked. Preserve an existing runtime requirement; never downgrade it to match
an example. Verify with the selected tool's documented locked-environment commands.

When a component must be shared as a package, application, server, or website,
give it a public interface, explicit dependencies, build/package configuration,
and relevant independent checks. Isolate project-local paths, research data,
credentials, and shared-resource experiment coordination from distributable
behavior. Keep necessary identity checks and restoration protections in the tool.
Generated distributions are artifacts, not maintained source. Preparing a build
does not authorize publishing or deployment.

Specialist tools, source checkouts, and system-installed research applications
belong in the third-party inventory described in the project guide. Ordinary
package dependencies stay in their ecosystem manifests and lockfiles. Historical
run records identify versions actually used; a link to today's toolchain note
alone cannot establish historical identity.
