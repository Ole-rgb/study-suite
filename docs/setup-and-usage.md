# Setup and everyday use

## 1. Prepare a vault copy

Copy `vault-template/` to a new location. Do not point setup scripts at an existing
vault or replace its files. Review each template, then migrate personal material
selectively with backups.

## 2. Configure the Stud.IP MCP

The MCP requires Python 3.10+ and the packages in `mcps/studip/requirements.txt`.
Create a virtual environment and install those requirements in the MCP directory.
Use `mcp.json.example` as a reference, replacing its placeholders in the local
Claude Desktop configuration:

- `STUDIP_BASE_URL`: the HTTPS base URL for your institution's Stud.IP instance.
- `STUDIP_VAULT_DIR`: absolute path to the vault copy.
- `STUDIP_DATA_DIR`: private local directory for cache and update snapshots.
- `STUDIP_BROWSER_PROFILE_DIR`: optional private browser-profile directory.

Do not commit a personalized MCP configuration, browser profile, `.env`, or state
files. Start the server through the MCP client and use `open_studip_login`; complete
sign-in yourself in the dedicated browser, then call `verify_studip_login`.

## 3. Configure the tutor

### Claude Desktop

Add the copied vault as a Project, provide `CLAUDE.md` in its project instructions,
and enable read/write access to the vault. Add the Stud.IP MCP using your local
configuration. Add an Anki MCP only if you want Anki operations.

Claude Desktop skills must be installed or registered in Claude's supported skills
location. A `SKILL.md` stored in the vault or this repository is source material; it
does not automatically register itself. Follow the current Claude Desktop skill
installation instructions and verify the skill appears before relying on it.

### Claude Code

Open the copied vault as the working directory. `CLAUDE.md` supplies project
instructions; files in `.claude/commands/` are optional shortcuts. Configure MCP
servers separately in the supported user- or project-local settings, and keep
machine-specific settings out of a public repository.

## 4. First update baseline

For a semester's first sync, ask the tutor to call `preview_initial_sync` and show
the announcements, files, and events. Inspect the returned inventory. Confirm it
only after review by calling `confirm_initial_sync` with that preview's ID.

The baseline is private MCP state. It records which announcements and files were
present at the starting point; it does not mark Stud.IP items read or download files.
Do not call `check_updates` before confirming a baseline for the current semester.

## 5. Routine catch-up

Ask naturally, for example: "Catch me up on Stud.IP. Summarize recent announcements,
new file candidates, and events in the next two weeks. Recommend files before
downloading anything."

The tutor should:

1. Verify the current semester still matches the active vault semester.
2. Call `check_updates` to report new/changed candidates and upcoming events.
3. Explain that candidate changes are not confirmed unread flags.
4. Recommend useful materials (for example slides or assignment briefs); avoid videos
   and indiscriminate downloads.
5. Download only selected files. They are staged under `.tmp/StudIP/`; review and
   organize them into the relevant course folder without overwriting existing files.

## 6. New semester

A new Stud.IP semester is a migration, not a routine catch-up. Compare the semester,
enrollments, and existing vault folders; propose the mapping; preserve prior
semesters; ask before guessing course type, exam details, or personal tasks. Review
the first-sync inventory and confirm a new baseline only after approval.

## 7. Anki workflow

The optional skill searches the target deck, drafts a small card set, requests
approval, writes through the Anki MCP, and verifies the result. It does not create
TSV/CSV import files. The Anki MCP is an independent integration and is not included
or authenticated by this repository.

## Troubleshooting

- **Login expired:** open the dedicated login window, sign in yourself, verify, retry.
- **No baseline:** preview, review, and confirm before using `check_updates`.
- **MCP tools missing:** restart/reload the MCP client and verify its local server
  configuration and Python environment.
- **Unsupported Stud.IP deployment:** check whether its API matches the JSON:API
  endpoints used by this MCP; do not assume all institutions expose the same API.
