# Issue #015: Define Formal Optional Dependency Groups

- **Status**: Proposed
- **Type**: Enhancement / Dependency Management
- **Priority**: Medium
- **Effort**: Low

## Problem

`pyproject.toml` currently lists optional tooling (RAG, MCP server, documentation site builders, remote sync utilities) alongside the core runtime dependencies. Contributors installing the project for CLI experimentation must pull in heavyweight extras like `chromadb`, `llama-index-*`, and `mkdocs-*`, and the code does not always provide clear guidance when these optional modules are missing.

## Proposal

1. **Restructure dependency metadata.** Move feature-specific requirements into `[project.optional-dependencies]` groups such as `remote`, `rag`, `mcp`, and expand the existing `docs` extra.
2. **Improve runtime messaging.** Harden the `try/except ImportError` blocks so users see actionable instructions (e.g., `pip install egregora[rag]`) whenever they invoke a feature whose dependencies are not installed.
3. **Document installation paths.** Update `README.md` and `docs/developer-guide/index.md` (and any other relevant pages) with examples that demonstrate installing with extras.

## Expected Benefits

- Reduces the default installation footprint.
- Makes the feature boundaries explicit to both users and maintainers.
- Provides friendlier UX when optional dependencies are missing.

## Dependencies

- Minor updates to `pyproject.toml` and potentially `uv.lock`.
- Coordination with documentation maintainers to keep installation instructions consistent across locales.
