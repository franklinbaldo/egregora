# Agent Instructions

## Tooling
- Use `uv` for everything Python-related (environment management, dependency changes, and running commands). Do **not** use `pip`, `pipenv`, or `venv`.
- Install/sync dependencies with `uv sync`; add/remove with `uv add` / `uv remove`.
- Always run commands via `uv run <tool ...>` (tests, linters, formatters, app entrypoints).

## Development workflow
- Default to TDD: add or adjust tests alongside any behavior changes or refactors.
- Keep changes small and cohesive; avoid mixing unrelated refactors with fixes/features.
- Prefer repository-local tooling over global installs (e.g., `uv run ruff check .` instead of a globally installed ruff).

## Quality gates
- Tests: `uv run pytest` (narrow to relevant paths when appropriate).
- Lint/format: `uv run ruff check .` and `uv run ruff format .` for Python changes.
- Types: `uv run mypy .` when touching typed code or interfaces.
- Docs site: when modifying documentation, validate with `uv run mkdocs build`.

## Documentation & examples
- Ensure any documented commands or code snippets are copy-paste runnable; prefer `uv run ...` invocations.
- Verify usage examples against the current code before publishing.

## Frontend/UX (MkDocs/blog generation)
- Edit templates and assets under `src/` (not generated `demo/` output).
- Use `uv run egregora demo` to regenerate the demo and inspect changes when altering templates or styles.

## Security and dependencies
- Keep dependency changes minimal and justified; prefer pinned, up-to-date versions through `uv`.
- Avoid introducing `# noqa` or relaxations to bypass linters; fix root causes instead.

Update this file if you introduce new tooling conventions or workflows others should follow.

## Jules automation
- **Auto-fix workflow (`.github/workflows/jules-auto-fixer.yml`)**: Triggers after CI completes (only when CI fails) or via manual dispatch. It locates the related PR (using the workflow run payload or matching the head SHA) and then runs `uv run --with requests --with typer --with pydantic python -m jules.cli autofix analyze <pr_number>`. The CLI uses `auto_reply_to_jules` to inspect PR health, summarize failing checks/logs, and either ping an existing Jules session or create a new one with `JULES_API_KEY` plus `GITHUB_TOKEN`/`GH_TOKEN`. When a session is created or messaged, the bot posts a PR comment (via `gh` when available) describing the issues and linking to the session.
- **Scheduler & persona system**:
  - The scheduler workflow (`.github/workflows/jules_scheduler.yml`) runs hourly or on dispatch and executes `uv run --with requests --with python-frontmatter --with jinja2 --with typer --with pydantic python -m jules.cli schedule tick [--all] [--prompt-id <id>] [--dry-run]`.
  - `jules.scheduler.run_scheduler` scans `.jules/personas/*/prompt.md`, ensures `.jules/personas/<id>/journals/` exists, and renders each prompt with injected identity branding, pre-commit instructions, and journal management blocks. It uses `schedules.toml` (or per-prompt `schedule` metadata) to decide when to run and creates sessions via `JulesClient` targeting the configured branch and automation mode.
  - Personas live under `.jules/personas/<persona>/prompt.md` with frontmatter keys like `id`, `emoji`, `enabled`, `title`, and optional `schedule`. Journals are append-only entries in `.jules/personas/<persona>/journals/`, and the scheduler includes the latest entries in the rendered prompt to provide context.
