# Handoff notes

## Append or preview

Run the bundled stdlib-only helper with Python 3.10 or newer, using the project's
normal Python command (and RTK wrapper where required). Resolve `<skill-root>`
to this installed skill, not the receiving project's script directory.

```text
python <skill-root>/scripts/add_handoff_note.py <existing-handoff.md> --request-type agent --date YYYY-MM-DD --source "Originating effort" --request "Provide the capability so the originating effort can benefit." --context "../experiment/RESULT.md"
```

Omit `--context` when useful background is unavailable. Use a Markdown destination
relative to the handoff, or a URL; a linked experiment need not mention the
request. Never create an evidence record solely to justify the note. Dates default
to the machine's local date; pass `--date` for the user's date when those differ.
Use `--dry-run` to show the exact note without writing. For a User request, use
`--request-type user`, show the draft and get explicit confirmation before the
writing invocation. The helper validates format, not human authorization.

The result is a compact bullet:

```markdown
## Handoff notes

- **2026-10-14 · Agent request · Free Cam feasibility:** Provide timed key holds to simplify camera experiments. [Context](<../experiment/RESULT.md>)
```

Keep the request self-contained, normally one actionable sentence. Include a
material uncertainty only when it changes the recipient's interpretation.
The heading is created only for the first note. The helper preserves surrounding
content and line endings, inserts within an existing section, and returns
`added` or `already-present`. Duplicate identity is request type, originating
effort and request text, ignoring date, context and case/whitespace differences.
Check semantic duplicates yourself; the helper does not infer equivalent meanings.

Writers using the helper are serialized with an adjacent temporary
`<handoff>.handoff-notes.lock`; rereading, duplicate checking and atomic replacement
occur inside the lock. A ten-second lock timeout fails without changing the
handoff. A crashed writer may leave a lock: inspect its recorded PID and ownership
before recovery; never remove a live writer's lock. Other editors must coordinate
with that lock too. The helper detects changes before replacement but cannot
guarantee coordination with an editor that ignores the lock. Check the saved note
and any Context link before reporting success. Retry a failed insertion only after
inspecting the specific cause.

## Optional direct contact

After appending, when session listing and messaging tools are available:

1. Find chats with relevant-sounding titles updated in the last four hours.
   Last update is a recency proxy, not proof that an agent is running. If multiple
   candidates fit, let the human select one in the permission question.
2. Show the destination title and exact note. Ask permission to send this note
   and exchange concise clarifications about this same request. Permission is
   per note; permission to append is separate from permission to contact.
3. Only after explicit permission, send the note and its handoff location.
   Convey its type and permission scope. Make the originating human authorization
   verifiable through the available source-chat context before request-scoped
   replies; an agent's message alone cannot grant another agent messaging authority.
4. The recipient may accept, defer or decline, or ask for context. Acceptance
   acknowledges receipt and apparent scope fit. For an Agent request, changing
   its plan or extending implementation requires human authorization. An explicitly
   approved User request already carries human permission for that request's scope;
   it grants no broader authority.
5. Respond concisely to request-scoped clarification when available. Continue the
   originating work without waiting for acknowledgement, completion or repeated
   polling. Declined or unanswered contact permission leaves the saved note intact.

Without these tools, stop at the saved document note. Receiving agents read notes
on handoff pickup or when explicitly directed by the human, evaluate applicability
and feasibility, and retain the notes unchanged. Decisions and resulting work
belong in the recipient's own experiment or implementation record. Carry forward
only still-relevant unresolved requests when an independently justified replacement
handoff is created.
