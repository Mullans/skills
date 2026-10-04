---
title: Session learning drafting and reflection
status: brainstorm
created: 2026-10-04
updated: 2026-10-04
tags: [session-learning, lessons, skills, reflection]
---

# Session learning drafting and reflection

> **Gist:** Two potential future directions for session learning: lightweight, automatic drafting of lessons during active work, and a separate reflection process that refines and integrates lessons already learned.

## Why / the itch

Currently, the user has to manually invoke session learning to go through the work and create lessons. Capturing a draft as a mistake or concrete lesson occurs would preserve the most up-to-date context.

After accumulating lessons, there is also an opportunity to reflect on them together and make the lesson base more unified, useful, efficient, and effective.

## Must-haves

- The lightweight drafter would operate during active work, separately from the more significant session learning invocation.
- The session learning invocation would review and codify those drafts, alongside anything new it discovers.
- Reflection would operate on lessons already learned and could run in a new context.
- Reflection would retain lessons as the underlying model, while allowing existing lessons to be updated, new lessons to be added through reflection, and lessons to be merged.

## Nice-to-haves

- Automatically create new skills, or at least skill drafts, when the agent recognizes a mistake or a concrete lesson in the same vein as the lessons learned so far.

## Non-goals / what I don't want

- The reflection process is not about learning brand-new lessons from active work. Its purpose is to maintain and improve the lessons already collected.

## Open questions

- [ ] Would the on-the-fly capture create new skills, skill drafts, or lightweight lesson drafts for later codification?
- [ ] What is the Hermes memory backend or reflection mechanism being recalled, and is "dreaming" its name?

## Loose ideas & approaches

- **During work:** A lightweight lesson drafter could capture a mistake or concrete lesson immediately, while the context is freshest. Later, an explicit session learning invocation could review and codify the captured drafts along with additional lessons.
- **After learning:** A more significant add-on could review accumulated lessons, determine their significance, and refine them into a more integrated lesson or knowledge base.
- The second direction resembles an audit, review, or maintenance protocol that can update, add, or merge lessons in a fresh context.
- The analogy is reflecting at the end of a day on everything learned throughout that day, putting separate lessons together into a unified understanding.

## Prior art / inspiration

- Hermes agent: a remembered memory-backend process, possibly called "dreaming," that reviews learned lessons and determines their significance. The exact backend and terminology are uncertain.

## Smallest next step

---

## Synopsis

I see two potential future directions for session learning. The first is a lightweight mechanism the agent can use while it is working. When it recognizes that it made a mistake or learned something concrete, it could automatically create a new skill, or at least a skill draft. At a minimum, I want it to draft the lesson on the fly, while it has the most up-to-date context, instead of requiring me to manually invoke session learning to capture everything afterward. This drafter would be separate from the more significant session learning invocation. That invocation could then review and codify the drafts, in addition to anything new it finds.

The second direction is a more significant reflection add-on, inspired by something I have seen in the Hermes agent's memory backend. I think they call it dreaming: reviewing learned lessons, determining significance, and doing additional thinking and refinement. Like reflecting at the end of a day, it could bring separate lessons together into a more unified and integrated lesson or knowledge base. We would still use lessons, but the process could update existing lessons, add lessons through reflection, or merge lessons. It would be an audit, review, or maintenance protocol that can run in a new context, focused on making what we have already learned as useful, efficient, and effective as possible, rather than learning brand-new lessons from active work.

## Decision log
