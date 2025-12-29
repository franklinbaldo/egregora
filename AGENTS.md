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
