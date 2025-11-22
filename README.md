# Egregora

**Privacy-first AI pipeline that extracts structured knowledge from unstructured communication.**

Egregora synthesizes emergent intelligence from group conversations—transforming scattered chat messages, legal notices, or archived discussions into coherent articles, documentation, and knowledge bases. Named after the concept of collective consciousness, it finds patterns and insights that emerge from group interaction.

**Core Principle:** Privacy before intelligence. Real names never reach the LLM—only deterministic UUIDs do.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)

---

## What It Does

**Transforms unstructured communication into structured knowledge:**

| Input Source | Output Format | Use Case |
|-------------|---------------|----------|
| WhatsApp group chats | Static blog (MkDocs) | Turn discussions into essays |
| Slack/Discord archives | Documentation site | Preserve team knowledge |
| Legal API feeds | Searchable archive | Monitor judicial communications |
| Self-reflection (past posts) | Meta-analysis | Identify gaps, avoid repetition |

```
Unstructured → Privacy Layer → AI Synthesis → Structured
(messages)    (UUIDs only)     (patterns)      (articles)
```

### Example: WhatsApp → Blog Post

**Input (chat messages):**
```
[2025-10-28 14:10] Alice: Did you see that article about AI agents?
[2025-10-28 14:12] Bob: Yeah, the license to exist concept is wild
[2025-10-28 14:15] Alice: Makes you think about emergent behavior...
```

**Output (generated article):** [The License to Exist](tests/fixtures/golden/expected_output/posts/2025-10-28-the-license-to-exist-emergent-agency-in-a-test-environment.md)

**What happened:**
1. **Synthesis:** Scattered thoughts → coherent narrative
2. **Context:** RAG retrieval adds citations from past discussions
3. **Metadata:** AI generates title, slug, tags, summary
4. **Privacy:** Alice/Bob → deterministic UUIDs (e.g., `author-a1b2c3d4`)

### More Use Cases

- **Research groups:** Turn journal club discussions into literature reviews
- **Legal monitoring:** Track Brazilian judicial communications (TJRO API → searchable archive)
- **Team documentation:** Convert Slack threads into structured knowledge base
- **Self-reflection:** Feed past posts back to identify gaps and avoid repetition
- **Content creators:** Extract story angles from community discussions

---

## Quick Start

### 1. Get Gemini API Key (Free)

Visit [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key) → Create API key

```bash
export GOOGLE_API_KEY="your-key-here"
```

### 2. Export WhatsApp Chat

WhatsApp → Chat → ⋮ Menu → More → Export chat → **Without media** → Save ZIP

### 3. Run Pipeline

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Process chat → generates blog in ./my-blog
uvx --from git+https://github.com/franklinbaldo/egregora \
    egregora write whatsapp-export.zip --output=./my-blog

# Serve locally
cd my-blog
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

Open http://localhost:8000 🎉

---

## Features

| Feature | Description |
|---------|-------------|
| **Privacy-First Architecture** | Deterministic anonymization (names → UUIDs) before any LLM processing |
| **Multiple Input Sources** | WhatsApp, Slack, legal APIs, self-reflection (extensible adapter system) |
| **Multiple Output Formats** | MkDocs blogs, Hugo sites (future), custom templates |
| **RAG Context Engine** | Posts reference past discussions via vector search |
| **Smart Windowing** | Group by time (hours/days), message count, or custom rules |
| **Quality Ranking** | Built-in Elo system identifies best content |
| **AI Editor** | Interactively refine posts with conversational AI |
| **Statistics Dashboard** | Auto-generated activity metrics |
| **Zero Config** | Works out of the box, customize everything later |

---

## Usage

### Basic Processing

```bash
# Default: 1 day per window, full rebuild
egregora write export.zip --output=./blog

# Custom windowing
egregora write export.zip --step-size=7 --step-unit=days     # Weekly
egregora write export.zip --step-size=100 --step-unit=messages  # By count

# Date filtering
egregora write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Resume from checkpoint (incremental)
egregora write export.zip --output=./blog --resume
```

### Privacy Commands

Users control their participation via in-chat commands:

```
/egregora set alias "Dr. Smith"    # Set display name
/egregora opt-out                  # Exclude from posts
/egregora opt-in                   # Re-include
```

### Multiple Sources

```bash
# WhatsApp (default)
egregora write export.zip --output=./blog

# Self-reflection (feed past posts back into pipeline)
egregora write ./blog --source=self --output=./blog-meta

# Brazilian judicial API (TJRO)
egregora write config.json --source=iperon-tjro --output=./blog-legal
```

---

## Architecture

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Ingestion  │ → │   Privacy   │ → │ Enrichment  │
│  (Parse)    │   │  (UUIDs)    │   │  (LLM+Cache)│
└─────────────┘   └─────────────┘   └─────────────┘
                         ↓
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Publication │ ← │ Generation  │ ← │  Knowledge  │
│  (MkDocs)   │   │ (Pydantic-AI│   │  (RAG+Elo)  │
└─────────────┘   └─────────────┘   └─────────────┘
```

### Design Principles

✅ **Privacy-First:** Anonymization BEFORE any LLM processing
✅ **Functional:** Pure `Table → Table` transformations
✅ **Type-Safe:** Pydantic V2 configs, Ibis for DataFrames
✅ **Simple Default:** Full rebuild (use `--resume` for incremental)
✅ **Alpha Mindset:** Clean breaks over backward compatibility

### Tech Stack

- **Language:** Python 3.12+ (type hints everywhere)
- **Package Manager:** [uv](https://github.com/astral-sh/uv) (Rust-powered, fast)
- **DataFrame:** [Ibis](https://ibis-project.org/) (lazy, type-safe)
- **Database:** DuckDB + VSS extension (vector search)
- **LLM Framework:** [Pydantic-AI](https://ai.pydantic.dev/) (type-safe agents)
- **LLM:** Google Gemini (configurable)
- **Site Generator:** MkDocs Material
- **Linter:** ruff (Rust-powered)

---

## Development

### Setup

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with dev dependencies
uv sync --all-extras

# Install pre-commit hooks (mandatory)
python dev_tools/setup_hooks.py
```

### Testing

```bash
# All tests
uv run pytest tests/

# Specific categories
uv run pytest tests/unit/         # Fast, no API calls
uv run pytest tests/integration/  # Uses VCR cassettes
uv run pytest tests/e2e/           # Full pipeline

# With coverage
uv run pytest --cov=egregora --cov-report=html tests/
```

**Note:** Integration tests use [pytest-vcr](https://pytest-vcr.readthedocs.io/). First run needs `GOOGLE_API_KEY`, subsequent runs replay from `tests/cassettes/`.

### Code Quality

```bash
# All checks (run before commit)
uv run pre-commit run --all-files

# Individual tools
uv run ruff check --fix src/   # Lint + auto-fix
uv run ruff format src/        # Format
uv run mypy src/               # Type check
```

**Line length:** 110 chars (see `pyproject.toml`)

---

## Project Structure

```
src/egregora/
├── cli/                  # Commands (write, init, runs)
├── orchestration/        # Pipeline workflows
├── input_adapters/       # WhatsApp, Slack, self-reflection
├── output_adapters/      # MkDocs, Hugo (future)
├── transformations/      # Pure functional data transforms
├── agents/               # Writer, enricher, reader (Pydantic-AI)
├── privacy/              # Anonymization + PII detection
├── database/             # DuckDB + schemas + views
├── config/               # Pydantic V2 settings
└── data_primitives/      # Core data models (Document, etc.)
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture and conventions.

---

## Configuration

Default config at `.egregora/config.yml`:

```yaml
models:
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5
  mode: ann  # "ann" or "exact"

pipeline:
  step_size: 1
  step_unit: days  # "days", "hours", "messages"
```

Custom prompts: `.egregora/prompts/` (overrides `src/egregora/prompts/`)

---

## Output Structure

```
my-blog/
├── docs/
│   ├── posts/              # Generated posts (YYYY-MM-DD-slug.md)
│   ├── profiles/           # Anonymized author profiles
│   ├── media/              # Enriched media descriptions
│   ├── journal/            # Continuity journals (YYYY-MM-DD-HH-MM-SS.md)
│   └── index.md            # Home page
├── .egregora/
│   ├── config.yml          # Local config
│   ├── runs.duckdb         # Run tracking
│   ├── rag.duckdb          # Vector embeddings
│   └── checkpoint.json     # Resume state (if --resume used)
└── mkdocs.yml              # Site config
```

---

## Contributing

Contributions welcome! Alpha mindset applies:

- ✅ Clean breaks for better architecture
- ❌ No backward compatibility required
- ✅ Modern patterns (Pydantic V2, frozen dataclasses)
- ❌ No functions with >5 params (use config objects)

**Before contributing:**
1. Read [CLAUDE.md](CLAUDE.md) for architecture and conventions
2. Install pre-commit hooks: `python dev_tools/setup_hooks.py`
3. Ensure tests pass: `uv run pytest tests/`

---

## Documentation

- [CLAUDE.md](CLAUDE.md) - Developer guide (architecture, patterns, conventions)
- [SECURITY.md](SECURITY.md) - Security policy
- [docs/](docs/) - Guides, architecture docs, API reference

---

## Roadmap

- [x] WhatsApp source with privacy-first anonymization
- [x] MkDocs Material output
- [x] Pydantic-AI agents with tools
- [x] RAG retrieval for context
- [x] Elo-based ranking
- [x] Interactive AI editor
- [x] Statistics auto-generation
- [ ] Slack/Discord sources
- [ ] Hugo output format
- [ ] Multi-language support

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Acknowledgments

- [Pydantic-AI](https://ai.pydantic.dev/) - Type-safe LLM agents
- [Ibis](https://ibis-project.org/) - Elegant DataFrame API
- [DuckDB](https://duckdb.org/) - Analytics database
- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) - Beautiful theme
- [uv](https://github.com/astral-sh/uv) - Fast package manager
- [ruff](https://github.com/astral-sh/ruff) - Comprehensive linter

---

**Egregora** - Preserve your group chat as structured knowledge, not just scrollback.
