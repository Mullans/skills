# Handoff notes

## Qualify and locate

Use notes for non-blocking convenience requests benefiting the originating effort
but belonging to another. Blocking dependencies, research findings and changes
to the core goal use their owning workflows. A roughly five-minute contribution
may fit the sender's already-authorized work; if scope or duration is uncertain,
ask the human to choose quick implementation or deferral.

Read the local lifecycle and locate the receiving effort's currently referenced
handoff. If no handoff is referenced, report the unrouted request rather than
creating one. An existing lifecycle without the note exception requires permission
to annotate. Check for equivalent requests already present.

## Draft and append

An **Agent request** is an optional side goal; a **User request** is a
human-requested subordinate goal. Inferred usefulness is an Agent request.
Follow the lifecycle's annotation permissions.

Write one self-contained actionable sentence, adding uncertainty only when it
changes interpretation. An optional Context link supplies background; the linked
record need not describe the request. Omit it when useful context is unavailable,
rather than creating a source record solely for the note.

Run the bundled stdlib-only helper with Python 3.10+ through the project's normal
Python command. Resolve `<skill-root>` to this installed skill.

```text
python <skill-root>/scripts/add_handoff_note.py <existing-handoff.md> --request-type agent --date YYYY-MM-DD --source "Originating effort" --request "Provide the capability so the originating effort can benefit." --context "../experiment/RESULT.md"
```

For a User request, use `--request-type user --dry-run` to display the exact draft
and obtain the lifecycle-required confirmation before writing. Omit `--context`
when unused; otherwise use a destination relative to the handoff or a URL.
Pass the user's date with `--date`; its default is the machine's local date.

The helper creates the section on first use and returns `added` or
`already-present`. Verify the saved note and Context link.

```markdown
## Handoff notes

- **2026-10-14 · Agent request · Free Cam feasibility:** Provide timed key holds to simplify camera experiments. [Context](<../experiment/RESULT.md>)
```

On insertion failure, inspect the cause before retrying. The helper coordinates
writers through `<handoff>.handoff-notes.lock`; editors ignoring it can still race.
A lock timeout leaves the handoff unchanged. Verify the recorded writer is no
longer writing before recovering a leftover lock.

## Optional direct contact

After appending, if session discovery and messaging are available:

1. Find relevant-sounding chat titles updated within four hours. Recency does not
   prove the agent is running; let the human choose if several candidates fit.
2. Show the destination and note. Ask per-note permission to send it and exchange
   concise clarifications about the same request. Declined or unanswered contact
   permission leaves the saved note intact.
3. After explicit permission, send the note, handoff location, source-chat identifier
   and human-approved communication scope. The recipient must be able to verify
   permission for replies through human-authored source context; an agent message
   alone cannot grant messaging authority.
4. Handle request-scoped clarifications when available. Continue originating work
   without waiting for acknowledgement, completion or repeated polling.

Without these tools, use the document note alone.

## Receiving notes

Read notes at the lifecycle's pickup/review points and evaluate applicability and
feasibility. A contacted recipient may accept, defer or decline, or ask for context.
Acceptance acknowledges receipt and apparent scope fit. For an Agent request,
changing the ongoing plan or extending implementation requires human authorization.
An explicitly approved User request carries permission for that request's scope.

Keep decisions and resulting work in the receiving effort's own record. When an
independently justified replacement handoff is created, carry forward only
still-relevant unresolved requests.
