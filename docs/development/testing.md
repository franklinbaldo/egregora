# Testing

## Run tests

```bash
uv sync --all-extras
uv run pytest -q
```

## Unit vs E2E

- Unit tests live in `tests/unit/`.
- E2E tests live in `tests/e2e/` (they avoid real API calls by default and use fixtures/mocks where needed).

## Formatting and linting

CI enforces Ruff formatting and linting:

```bash
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
```

