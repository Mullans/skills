---
name: brainstorm
description: Capture a free-form idea dump and structure it into a standard brainstorm doc in the ideas/ folder. Use when the user wants to brainstorm, ramble about an idea, dump thoughts, think through a new project, or says "let's brainstorm X" / "I have an idea". Reorganizes their ramble losslessly into a fixed format — never invents content.
---

# Brainstorm capture

Turn an unstructured idea dump into a standardized, resumable brainstorm document saved in `ideas/`.

## Core rule: meaning-lossless, not generative
Capture everything the user *means*, but not every word they say. You may dedupe, fold together repeated/rephrased points, and tighten for clarity — but never invent requirements, features, rationale, or scope the user didn't express. If a bucket has nothing, leave it empty (keep the heading). The **Synopsis** holds a deduplicated prose version of the idea in the user's own framing; it is meaning-lossless but text-lossy (filler and repetition are dropped).

## Workflow (new capture)
1. Read the canonical format from `template.md` in this skill folder. (See `example.md` for a worked example.)
2. Take the user's ramble — from chat, a pasted blob, or a file they point to.
3. Sort it into the buckets defined in the template. Preserve the user's phrasing where reasonable; tighten only for clarity.
4. Write a tight, deduplicated **Synopsis** in the user's voice. Do not transcribe verbatim; fold repetition together.
5. Fill the frontmatter: `title`, `status: brainstorm`, `created`/`updated` = today's date, and `tags` if obvious from the content.
6. Save to `ideas/<kebab-case-title>.md`. If that file exists, append a numeric suffix rather than overwriting.
7. Tell the user the path and surface the **Open questions** — that's their fastest way back in.

## Workflow (updating an existing doc)
The docs are revisited over time. **Merge in place — never append a fresh ramble.**
1. Read the existing doc.
2. Fold the new input into the relevant buckets and re-synthesize the **Synopsis** so it stays one coherent, deduplicated description (not a stack of session notes).
3. Bump `updated` to today's date.
4. Add a terse line to the **Decision log** for anything that should not be re-litigated: a decision made, a dead-end ruled out (with why), or a lesson/win. Prefix `[decision]` / `[dead-end]` / `[lesson]`, newest at the bottom. The log is append-only; everything else is rewritten in place.

## Notes
- If the user's ramble is thin, capture what's there; don't pad. A near-empty doc with a good Synopsis is fine.
- The Decision log is the one append-only section. Keep entries to one line — it's a memory of settled ground, not a narrative.
- `status` graduates over time: `brainstorm → exploring → parked → promoted-to-plan`. Update it when the user signals a change.
- The format is intentionally easy to change. To revise it, edit `template.md` here. Existing docs in `ideas/` are inert files and need no migration — old docs may use an older format (e.g. a `Raw dump` section); leave them unless asked to retrofit.
