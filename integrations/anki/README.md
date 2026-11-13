# Anki integration

Anki is an optional, independent integration. This repository provides a generic
`anki-lecture-cards` skill source under `vault-template/.claude/skills/`; it does not
bundle or authenticate an Anki MCP server.

Install/connect an Anki MCP supported by your Claude environment, then register the
skill through that environment's skill mechanism. Verify that the MCP tools and skill
are available before asking the tutor to create cards. The skill requires a review
step before writing and verifies created cards afterward.

Do not put Anki credentials, collection databases, personal deck exports, or private
deck inventories in this repository.
