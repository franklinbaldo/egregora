# Documentation Overview

This site is built with MkDocs Material (`mkdocs.yml`) and published to GitHub Pages on pushes to `main`.

## Build locally

```bash
uv sync --extra docs
uv run mkdocs serve
```

## Demo site

The CI workflow also generates an offline demo site (published under `/demo/`).

