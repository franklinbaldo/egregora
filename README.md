# Egregora

*Turn noisy conversations and feeds into a polished, privacy-aware knowledge site.*

[![CI](https://github.com/franklinbaldo/egregora/actions/workflows/ci.yml/badge.svg)](https://github.com/franklinbaldo/egregora/actions/workflows/ci.yml)
[![CodeQL](https://github.com/franklinbaldo/egregora/actions/workflows/codeql.yml/badge.svg)](https://github.com/franklinbaldo/egregora/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/franklinbaldo/egregora/branch/main/graph/badge.svg)](https://codecov.io/gh/franklinbaldo/egregora)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)
[![Docs](https://img.shields.io/badge/docs-live-green.svg)](https://franklinbaldo.github.io/egregora/)

Egregora ingests chat exports (WhatsApp, RSS, and more), anonymizes participants, enriches content with LLM agents, and publishes an MkDocs site you can host anywhere. Pipelines run locally by default, while letting you opt into cloud models when you want more horsepower.

---

## What makes Egregora different?

- **Composable agents:** Writer, Editor, Enricher, and Reader agents collaborate to summarize, enrich, score, and illustrate each post.
- **Feed-first architecture:** Everything becomes structured feed entries, enabling repeatable pipelines and interop with the wider RSS ecosystem.
- **Privacy aware:** Names are replaced with stable IDs before content leaves your machine; caching and RAG live in local DuckDB + LanceDB stores.
- **Production-grade outputs:** Generates MkDocs sites (Material theme) with banners, media captions, and ranking signals ready for deployment.
- **Extensible inputs:** Ships with WhatsApp and Atom/RSS adapters; implement your own adapter to ingest any text stream.

---

## Quickstart (5 minutes)

Requirements: Python 3.12+, [uv](https://github.com/astral-sh/uv), and a [Google Gemini API key](https://ai.google.dev/gemini-api/docs/api-key).

```bash
# 1) Install or run the CLI
uvx --from git+https://github.com/franklinbaldo/egregora egregora --help
# or cache it locally:
uv tool install git+https://github.com/franklinbaldo/egregora

# 2) Export a WhatsApp chat (.zip) without media for privacy

# 3) Create a site scaffold
uvx --from git+https://github.com/franklinbaldo/egregora egregora init my-blog
cd my-blog

# 4) Provide your model credentials
export GOOGLE_API_KEY="your-api-key"

# 5) Generate posts
uvx --from git+https://github.com/franklinbaldo/egregora egregora write \
  path/to/export.zip \
  --output-dir=. \
  --timezone="America/New_York"

# 6) Preview the site
uv sync --all-extras
uv run mkdocs serve -f .egregora/mkdocs.yml
```

The `write` command parses the export, anonymizes names, builds a LanceDB index for retrieval, and emits Markdown posts under `docs/posts/`. Visit <http://localhost:8000> to read the site.

---

## Configure your pipeline

Egregora stores run settings in `.egregora.toml`. A minimal multi-site configuration looks like:

```toml
[sources.chat]
type = "whatsapp"
path = "exports/friends.zip"

[sites.blog]
sources = ["chat"]

[sites.blog.output]
adapters = [{ type = "mkdocs", config_path = ".egregora/mkdocs.yml" }]
```

Key knobs to adjust:

- **Windowing:** `--step-size` and `--step-unit` (hours, days, messages) control how messages are grouped into posts.
- **Models:** `--model` or `[writer]/[enricher]/[banner]` blocks select the provider (e.g., `google-gla:gemini-flash-latest` or OpenRouter models).
- **Enrichment:** `--enable-enrichment` pulls in media and URL context; use `--refresh` to invalidate caches tier-by-tier.
- **Target site/source:** When multiple entries exist, pick one explicitly with `--site` and `--source` or the `EGREGORA_SITE`/`EGREGORA_SOURCE` env vars.

Prompts live under `.egregora/prompts/`—tweak them to change tone, writing style, or image prompts. See the [Configuration guide](docs/getting-started/configuration.md) for full details.

---

## Frequently used commands

```bash
# Resume a previous run without rebuilding embeddings
egregora write export.zip --resume

# Focus on a date range
egregora write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Rank generated posts with ELO comparisons
egregora read rank docs/posts/
egregora top --limit=10

# Inspect recent pipeline runs
egregora runs list
egregora runs show <run_id>
```

If you installed with `uv tool install`, the `egregora` command is available directly. Otherwise prefix with `uvx --from git+https://github.com/franklinbaldo/egregora`.

---

## Developing and contributing

Clone the repo and set up a local environment with uv:

```bash
uv sync --all-extras

# Lint and format
uv run ruff format .
uv run ruff check .

# Tests
uv run pytest

# Types (run when touching typed interfaces)
uv run mypy .

# Documentation
uv run mkdocs build
```

Relevant directories:

- `src/egregora/agents/` — LLM-driven agents (writer, editor, enricher, reader, banner).
- `src/egregora/input_adapters/` — Data ingress points; implement a new adapter to support another feed.
- `src/egregora/orchestration/` — Pipelines that coordinate ingestion, enrichment, and publishing.
- `src/egregora/database/` — DuckDB + LanceDB storage and retrieval helpers.

For a guided walkthrough of the architecture, start with the [V3 overview](docs/v3/architecture/overview.md) and the [Quickstart](docs/getting-started/quickstart.md).
