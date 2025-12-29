# Agent Instructions

- Use `uv` for everything Python-related, including dependency management, running commands, and scripts.
  - Install or sync dependencies with `uv sync` (do not use `pip` or `pipenv`).
  - Run tests with `uv run pytest` (or `uv run <tool> ...` for other CLI tools).
  - Run the application with `uv run <app command>`.
  - Add or update dependencies with `uv add` / `uv remove`.
- Prefer repository-local tooling commands (e.g., `uv run <tool>`) over global installs.
- Keep this file up to date if you add tooling conventions others should follow.
