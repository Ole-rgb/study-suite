# reMarkable integration

reMarkable is an optional, independent integration. It copies handwritten notebooks
into the vault as PDFs so the tutor can link them to a course. This repository does not
bundle the server; it uses the third-party
[remarkable-mcp](https://github.com/sammorrowdrums/remarkable-mcp) in **local-directory
mode**, which reads the reMarkable desktop app's sync cache on your computer.

- **Read-only.** Local-directory mode never writes to the tablet or the cache.
- **Never use SSH mode** (`--ssh`). It is not needed here and can reset the tablet.
- **No cloud registration.** `--register` and cloud mode need a reMarkable Connect
  subscription; local mode only needs the signed-in desktop app.
- **Freshness.** Notes are only as current as the desktop app's last sync. Without
  Connect, documents left untouched for about 50 days may stop syncing to the app.

## How the sync works

Each course's `Course.md` lists which tablet notebooks belong to it in a
`## reMarkable` block. The tutor only syncs mapped notebooks, and only when you ask
("update my reMarkable files", "fetch reMarkable files for <course>"). By default:

| Course type | Synced notebooks |
|---|---|
| `standard` | the lecture notebook only |
| `flipped` | the video and in-class session notebooks |
| `seminar`, `lab` | none — not opened |

`vault-template/.claude/scripts/remarkable_sync.py` does the export. It calls
remarkable-mcp's own exporter on the cache folder and writes merged PDFs to
`01 Courses/<course>/Handwritten/<notebook> - <YYYY-MM-DD>.pdf`. It never overwrites a
file: a changed notebook gets a new dated PDF, and each export is logged in
`Handwritten/sync-log.md`. A synced notebook is never treated as evidence of
attendance, coverage, or understanding.

The script exists because the MCP's own `remarkable_export` returns a temporary
resource link that some Claude setups (for example a cloud session reaching your Mac)
cannot download. If your client can save that link directly, you can use the tool
instead; the same rules apply.

Setup: [installation step 8](../../docs/installation/08-remarkable.md).

Do not put notebooks, exported PDFs, cache folders, or personal mappings in this
repository.
