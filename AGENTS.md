# Repository Guidelines

## Project Structure & Module Organization
- Source lives in `src/egregora`: CLI (`cli/`), orchestration (`orchestration/`), pure transforms (`transformations/`), adapters (`input_adapters/`, `output_adapters/`), persistence/RAG (`database/`, `rag/`), agents (`agents/`), prompts/templates (`prompts/`, `templates/`), utilities (`utils/`).
- Tests reside in `tests/` (unit, integration, e2e) with fixtures under `tests/fixtures/` (sample chats, VCR cassettes, golden data).
- Docs are MkDocs-based in `docs/`; dev helpers in `dev_tools/`; configs in `pyproject.toml`, `uv.lock`, `mkdocs.yml`.

## Build, Test, and Development Commands
- First-time setup: `python dev_tools/setup_hooks.py` (installs deps with uv and pre-commit hooks).
- Lint/format: `uv run ruff check src tests` and `uv run ruff format src tests`.
- Tests: `uv run pytest tests/`; quick loop `uv run pytest -m "not slow"`; coverage `uv run pytest --cov=egregora --cov-report=html tests/`.
- Docs preview: `uvx mkdocs serve` from the repo root.
- CLI smoke test: `uv run egregora --help` or `uv run egregora write tests/fixtures/sample_chats/basic_chat.zip --output=./site`.

## Coding Style & Naming Conventions
- Python 3.12+, 4-space indent, line length 100 (Black) / 110 (Ruff). Type hints required; Google-style docstrings for public APIs.
- Ibis-first policy: avoid pandas/pyarrow in `src/` (allowed only in compat/testing); absolute imports only.
- Keep transformations pure and side-effect free; prefer protocol-driven design and dependency injection over globals.
- Naming: snake_case modules; `{Name}Adapter` for adapters, `*Settings` for configs, `*Context` for runtime contexts, verb-first functions (`create_windows`, `run_pipeline`); use `utils.paths` for slug/path helpers.

## Testing Guidelines
- Pytest markers include `e2e`, `slow`, `quality`, `security`, `benchmark`. Use `-m "not slow"` for fast runs.
- Use provided fixtures (`test_config`, `minimal_config`, `config_factory`) instead of instantiating configs directly to avoid touching real `.egregora/` paths; prefer `tmp_path` for any writes.
- VCR cassettes live in `tests/fixtures/vcr_cassettes/`; delete a cassette to re-record. Update golden fixtures when expected outputs change.
- Coverage: core ~90%+, utilities ~80%+, CLI ~70%.

## Commit & Pull Request Guidelines
- Follow Conventional Commit prefixes (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`, etc.) seen in git history.
- Before pushing: `uv run pre-commit run --all-files` and `uv run pytest tests/`.
- PRs target `dev/develop`; include a concise summary, linked issues, and test evidence. Attach screenshots/log snippets for UI or doc output when relevant. Rebase workflow keeps PRs current—pull latest `dev` to avoid conflicts.

## Security & Configuration Tips
- Keep secrets in environment variables (e.g., `GOOGLE_API_KEY`); never commit keys or generated `.egregora/` or `site/` outputs.
- Prefer temporary paths for local runs and tests; cache directories such as `.egregora-cache/` should not be versioned.
