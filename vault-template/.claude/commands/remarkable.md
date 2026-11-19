---
description: Fetch/update handwritten reMarkable notebooks into the vault (one course or all).
argument-hint: [course name, optional]
---

Follow CLAUDE.md → "reMarkable handwritten notes".

1. Check the reMarkable MCP responds and runs in local-directory mode. If not, say what
   is missing and stop. Never use SSH mode.
2. For each active-semester course (or only the course named), read `Course.md` `type:`
   and its `## reMarkable` block. Skip `seminar` and `lab` courses entirely.
3. Run `.claude/scripts/remarkable_sync.py --vault <vault> --cache <cache> --prefix <semester>
   [--course "<course folder>"]` as a dry run, then with `--apply`.
4. Report exported, unchanged, missing, stale, and unmapped notebooks. Propose mappings
   for unmapped ones; don't write them without approval.
5. Don't touch status, attendance, confidence, or progress.
