---
title: Personal to-do list app
status: brainstorm
created: 2026-06-23
updated: 2026-06-23
tags: [tools, productivity]
---

# Personal to-do list app

> **Gist:** A dead-simple personal to-do tool that captures tasks instantly and gets out of the way — no projects, tags, or ceremony, just a fast list I actually keep using.

## Why / the itch
Every existing to-do app makes me set up projects, priorities, and tags before I can write a task. The overhead means I stop using them within a week and fall back to scraps of paper.

## Must-haves
- Add a task in under 2 seconds from a global hotkey.
- Plain-text storage I own (no lock-in, syncable via my own files).
- Works offline.

## Nice-to-haves
- Natural-language dates ("fri", "tomorrow").
- A daily "what's due" surface.
- Quick archive of completed items instead of deletion.

## Non-goals / what I don't want
- No projects, sub-tasks, or nested hierarchies.
- No accounts, no cloud service to sign up for.
- Not a calendar, not a notes app — just tasks.

## Open questions
- [ ] Native app, CLI, or web? Hotkey capture matters most.
- [ ] How does sync work if storage is plain files?
- [ ] Do recurring tasks belong here or violate the "simple" goal?

## Loose ideas & approaches
- Could be a single markdown file the tool reads/writes.
- Menu-bar app for the global capture box.
- "Today" view = just lines tagged with today's date.

## Prior art / inspiration
- Things (too heavy), TaskWarrior (CLI, close but fiddly), plain .txt todo.txt format.

## Smallest next step
- Prototype the global-hotkey capture box that appends a line to a markdown file.

---
## Synopsis
I want a deliberately simple personal to-do list that makes capture nearly instant: hit a global hotkey, type the task, and save it. The data should stay in plain text that I control—possibly one Markdown file—and work offline. I do not want projects, sub-tasks, accounts, or a calendar replacement. Natural-language dates, a focused Today view, and quick archiving would be useful additions. A menu-bar app is one possible approach, but the native-app, CLI, or web form is still open, as are sync and whether recurring tasks fit the simple scope. Things is polished but too heavy, while TaskWarrior is closer but still too fiddly.

## Decision log
- 2026-06-23 [decision] Keep the tool focused on fast personal task capture rather than project management. Why: setup overhead makes existing apps hard to sustain.
- 2026-06-23 [decision] Store tasks in user-owned plain text and support offline use. Why: avoid lock-in and keep the tool usable anywhere.
