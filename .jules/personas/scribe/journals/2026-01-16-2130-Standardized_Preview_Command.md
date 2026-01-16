---
title: "✍️ Standardized Preview Command"
date: 2026-01-16
author: "Scribe"
emoji: "✍️"
type: journal
---

## ✍️ 2026-01-16 - Summary

**Observation:** I noticed a significant inconsistency and fragility in the documentation and CLI output regarding the command to preview the generated MkDocs site. Users were instructed to copy-paste a command with ~7 specific plugins (`--with mkdocs-material --with mkdocs-blogging-plugin ...`), which is error-prone and hard to maintain. Additionally, the CLI output for `egregora init` and `egregora demo` was also using this verbose command.

**Action:** I standardized the preview command across `README.md`, `docs/getting-started/quickstart.md`, `docs/getting-started/installation.md`, `docs/index.md`, `docs/demo/README.md`, `AGENTS.md`, `src/egregora/cli/main.py`, and `src/egregora/rendering/templates/site/README.md.jinja`.
The new robust command is:
`uv tool run --with "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs serve -f .egregora/mkdocs.yml`
This leverages the `mkdocs` extra defined in `pyproject.toml` as the single source of truth for dependencies.
I also fixed an issue where the `rich` library was interpreting `[mkdocs]` as a style tag in the CLI output by escaping the bracket (`\[mkdocs]`).
Finally, I removed outdated references to "v2" in the generated documentation templates.

**Reflection:** This change drastically simplifies the user experience and reduces maintenance burden. Any future changes to MkDocs plugins only need to be updated in `pyproject.toml`, and the documentation command will remain valid. I learned that `rich` markup requires escaping for brackets, which was a small but crucial fix for the CLI experience.
