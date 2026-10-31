# Components, tools and distributables

Use the project's ecosystem and preserve working component roots. Add code,
environments and manifests when needed, rather than creating empty language
scaffolds. Keep environment/run/build entry points in the toolchain owner and
dependency requirements in manifests and lockfiles.

| Situation | Setup decision |
| --- | --- |
| No code or selected language | Defer product runtimes and manifests |
| One language | Reuse its package layout, environment and locked execution commands |
| Another language or substantial component is added | Give it explicit environment ownership and interfaces without relocating working components for symmetry |
| A component becomes distributable | Define its public interface, dependencies and build/check entry points |
| A specialist research tool is adopted | Record capability, access route, provenance and applicable validation with its tool owner |

Promote recurring research operations into parameterized maintained methods or
commands. Prefer sensible defaults and reusable configuration over copied scripts
or long repeated command lines. Keep effective settings with the result when they
affect interpretation.

Isolate project-local data, credentials and agent resource coordination from
standalone tools. Preserve the tool's own identity and restoration protections.
Use the artifact authority for experimental builds and package staging; keep
shared caches and published outputs in their documented owners. Read
[artifact integration](artifact-storage.md) when changing a producer or closeout
path, rather than duplicating its operating procedure here.

Ordinary libraries belong in dependency manifests, not another manual inventory.
For specialist tools, retain upstream/license, adopted identity, acquisition route
and supported use. Distinguish a located tool from a validated capability. Version
a run's relevant inputs in its evidence rather than treating today's toolchain
note as historical proof.

Preparing a package does not authorize publication or deployment.
