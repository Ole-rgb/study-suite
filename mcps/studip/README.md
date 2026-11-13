# Stud.IP MCP

An MCP server for reading Stud.IP course information and staging selected course
files. It uses a persistent, user-authenticated Firefox browser context; it never
exports session cookies to the assistant.

## Capabilities

- Interactive login and authentication verification.
- Current semester and enrolled course listing.
- Paginated course file, event, personal event, and announcement listing.
- Inclusive ISO-8601 date filters for events and announcements.
- Explicit initial-sync preview and confirmation.
- Incremental new/changed announcement and file candidates, plus upcoming events.
- One-file-at-a-time download to `<vault>/.tmp/StudIP/`, preserving the Stud.IP
  course and folder names.

All authenticated API traffic is GET-only. The tools do not enroll in or leave
courses, edit course content, mark items as read, or bulk-download files.

## Install

1. Install Python 3.10 or later and Firefox.
2. Create and activate a virtual environment in this directory.
3. Install `requirements.txt`.
4. Install Playwright's Firefox browser for that Python environment.
5. Configure the MCP client using `mcp.json.example`, replacing all paths and
   `STUDIP_BASE_URL` locally. Keep this personalized configuration outside Git.
6. Start the MCP and call `open_studip_login`; sign in yourself in the opened
   browser, then call `verify_studip_login`.

The URL must use HTTPS. The default example host is intentionally non-functional;
set the real base URL for your institution.

## Update workflow

For a new semester, call `preview_initial_sync`, inspect its inventory, and only
then call `confirm_initial_sync` with the returned `preview_id`. `check_updates`
requires this baseline for the current semester. Confirmation records a private
comparison snapshot; it does not mark items read or change Stud.IP.

Routine checks report changes relative to the confirmed snapshot. The API does not
reliably expose red unread indicators. File listing data may not contain trustworthy
upload dates. Do not describe candidate changes as verified unread.

## Local state and privacy

`STUDIP_DATA_DIR` stores cache, update state, pending baseline previews, and the
persistent browser profile by default. Keep it private and outside the repository.
`STUDIP_VAULT_DIR` is the user's vault; downloaded files are staged only under
`.tmp/StudIP/` there. Do not commit credentials, browser profiles, state files, or
course downloads.

## Test

From this directory, install the requirements and run:

```sh
python -m unittest discover -s ../../tests -v
```

The current tests do not contact a Stud.IP server. Validate API compatibility and
login manually against your own deployment before relying on the integration.
