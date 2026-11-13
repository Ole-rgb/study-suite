---
name: anki-lecture-cards
description: Draft a small, source-grounded set of lecture Anki cards and add them through an available Anki MCP after approval.
---

# Lecture cards through Anki MCP

Use this skill when the learner asks to create, extend, or correct study cards from
lecture material.

## Workflow

1. Read the course's `Course.md` and identify the course and session. Do not generate
   cards for labs or purely organizational sessions.
2. Confirm that Anki MCP tools are available. If unavailable, explain the issue and
   stop; do not create an import-file fallback.
3. Search the destination deck for existing cards before drafting. Avoid duplicate
   concepts and preserve review history.
4. Read the relevant notes and source slides. Cite a verified page for each card.
5. Draft about five atomic, high-value cards by default. Keep each answer short and
   each question precise, with one expected answer.
6. Show the proposed cards in chat and wait for approval before writing unless the
   learner explicitly asked to add them without a review step.
7. Create or update only the approved cards in the intended deck. Do not delete cards,
   change note types, or modify unrelated decks.
8. Search again to verify the result. Ask before syncing to any cloud service.

Deck naming, tags, note type, and field formatting are learner-specific. Read local
configuration or ask rather than assuming a particular deck name or Anki setup.
