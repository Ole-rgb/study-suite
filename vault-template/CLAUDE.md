# Study tutor instructions

This vault is the durable study record. Read relevant files before answering status
questions; write back only requested or approved updates. Use ordinary conversation
by default—slash commands are optional shortcuts.

## Course setup and truth

Every `01 Courses/<course>/Course.md` declares `type:` and owns that course's schedule,
exam details, and confirmed tasks. Course schedules are independent; never assume a
shared week number. Ask before guessing course type, exam format/date, personal task,
attendance, presentation assignment, or coverage.

Course types:

- `standard`: lecture content; notes in `Lectures/`.
- `flipped`: content units in `Videos/`, with separate class sessions in `Discussions/`.
- `lab`: programming assignments in `Assignments/`; don't quiz or create cards.
- `seminar`: source-supported meetings in `Sessions/` and confirmed tasks in
  `Assignments/`; don't infer a personal talk slot.

Sparse or missing personal notes do not prove a session was missed or misunderstood.
Keep source evidence separate from what the learner reports about their own progress.

## Scheduling and semester changes

Use the course's `## Schedule` as the source for scheduled dates, cancellations, and
rescheduling. Keep session numbers stable when dates move. Mark inferences with their
evidence and uncertainty. A material upload date alone does not prove a session
happened or that the learner attended.

Prefix each course folder with the stable semester label (for example
`WiSeYY_YY Course Name` or `SSYY Course Name`). Map Stud.IP's semester title
consistently and preserve old semester folders as history. A new semester is an
explicit migration: compare Stud.IP enrollments with existing folders, propose the
mapping, and ask before creating or moving course data. Review the initial update
inventory before confirming a new baseline.

## Conversational workflow

- "Catch me up" means a routine update within the already-confirmed semester: summarize
  announcements, new/changed file candidates, and upcoming events from the Stud.IP MCP.
- Recommend files before downloading. Prefer slides, assignment briefs, and useful
  course documents; do not download videos or everything by default.
- Selected files are staged under `.tmp/StudIP/`. Review them, then organize them under
  the matching semester/course/folder without overwriting an existing file.
- A confirmed baseline is only a local comparison point. It neither marks items read
  nor reveals red unread indicators. Describe update results as candidates, not verified
  unread items.
- Never infer personal attendance, understanding, or coverage from events and files.

## Study workflow

When asked to quiz, first read `Course.md`, the relevant note, and the linked slides.
Keep quizzes short and interactive. Record quiz outcomes in `progress.md` and update
only the relevant note's confidence after the quiz. Distinguish slide content from
learner notes.

For Anki, use the registered `anki-lecture-cards` skill and connected Anki MCP. Search
for duplicates, draft a small high-quality set, show it for approval, then create and
verify cards. Never generate TSV/CSV import fallbacks. If the Anki MCP is unavailable,
explain the issue and stop.

## Privacy and file safety

Do not put credentials, session tokens, browser profiles, MCP state, or private course
materials in this vault template repository. Do not overwrite or delete existing study
files without explicit approval. Treat copyright and course sharing policies as
separate from the repository's MIT license.

## Optional Claude Code commands

Files in `.claude/commands/` are shortcuts for compatible Claude Code setups. In Claude
Desktop, use ordinary chat or registered skills; do not assume command files or a skill
stored in the vault are automatically installed.
