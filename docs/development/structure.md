# Project Structure

## High-level layout

- `src/egregora/`: active v2 codebase (CLI + pipeline + adapters).
- `src/egregora_v3/`: v3 experiments (kept separate; see ADRs).
- `docs/`: documentation sources for MkDocs.
- `tests/`: unit + e2e tests.
- `.egregora/`: local-generated site + pipeline artifacts (ignored in git).

## Output sites

Egregora generates MkDocs sites. The canonical directories are configured via `.egregora.toml` and resolved by `MkDocsPaths`.
