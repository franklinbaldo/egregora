# Egregora

**A privacy-first AI loom that weaves collective consciousness into structured knowledge.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)
[![Pydantic-AI](https://img.shields.io/badge/Pydantic--AI-type--safe-00D9FF.svg)](https://ai.pydantic.dev/)

> Named after the concept of collective consciousness, Egregora finds patterns and insights that emerge from group interaction—then writes them into existence as coherent articles, documentation, and living archives.

---

## The Problem

Your group chats contain **emergent intelligence**: breakthrough ideas scattered across 100 messages, collective wisdom buried in 6-month-old threads, philosophical insights lost to the scroll. But extracting this knowledge means:

❌ Exposing private conversations to AI services
❌ Manually synthesizing scattered thoughts
❌ Losing context from past discussions
❌ Watching insights fade into chat history

**Egregora solves this by inverting the paradigm:**

✅ **Privacy BEFORE intelligence** - real names become UUIDs before LLMs ever see them
✅ **Automatic synthesis** - scattered thoughts → coherent narratives
✅ **Memory across time** - RAG retrieval connects past and present
✅ **Living knowledge bases** - self-generating documentation from your team's conversations

---

## Live Example: WhatsApp → Blog Post

**Input: 3 scattered chat messages**

```
[2025-10-28 14:10] Alice: Did you see that article about AI agents?
[2025-10-28 14:12] Bob: Yeah, the license to exist concept is wild
[2025-10-28 14:15] Alice: Makes you think about emergent behavior...
```

**Output: Coherent essay with metadata**

<details>
<summary><strong>→ Click to see generated article (real output from tests)</strong></summary>

```markdown
---
title: "The License to Exist: Emergent Agency in a Test Environment"
slug: the-license-to-exist-emergent-agency-in-a-test-environment
date: 2025-10-28
authors:
  - author-a1b2c3d4  # Alice (anonymized)
  - author-e5f6g7h8  # Bob (anonymized)
tags:
  - artificial-intelligence
  - emergent-behavior
  - philosophy
summary: >
  Exploring the concept of emergent agency through the lens of
  AI systems developing unexpected behaviors in constrained environments.
---

# The License to Exist: Emergent Agency in a Test Environment

The question of when artificial systems transcend their programming to
exhibit genuine agency has long captivated researchers and philosophers
alike. Recent discussions around "the license to exist" concept highlight
a fascinating paradox...

[Full article: tests/fixtures/golden/expected_output/posts/2025-10-28-...]
```

</details>

**What happened:**

1. **Privacy Shield**: `Alice` → `author-a1b2c3d4` (deterministic UUID)
2. **Context Retrieval**: RAG finds related past discussions, adds citations
3. **Synthesis**: LLM distills scattered thoughts into coherent narrative
4. **Metadata Generation**: AI creates title, slug, tags, summary
5. **Publication**: MkDocs-ready markdown with profile pages, media enrichment

---

## Quick Start (3 Commands)

```bash
# 1. Get free Gemini API key → https://ai.google.dev/gemini-api/docs/api-key
export GOOGLE_API_KEY="your-key-here"

# 2. Export WhatsApp chat (Chat → ⋮ → Export → Without media → Save ZIP)

# 3. Generate blog (installs automatically via uvx)
uvx --from git+https://github.com/franklinbaldo/egregora \
    egregora write chat-export.zip --output=./my-blog

# Serve locally
cd my-blog && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

Open http://localhost:8000 🎉

---

## How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                      THE PRIVACY FIREWALL                        │
│                   (Names → UUIDs BEFORE LLMs)                    │
└──────────────────────────────────────────────────────────────────┘
                                 ↓
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  INGESTION  │  →  │   PRIVACY   │  →  │ ENRICHMENT  │
    │             │     │             │     │             │
    │ Parse ZIP   │     │ Anonymize   │     │ LLM Context │
    │ Normalize   │     │ PII Scan    │     │ L1 Cache    │
    └─────────────┘     └─────────────┘     └─────────────┘
                                                    ↓
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ PUBLICATION │  ←  │ GENERATION  │  ←  │  KNOWLEDGE  │
    │             │     │             │     │             │
    │ MkDocs Site │     │ Writer LLM  │     │ RAG + VSS   │
    │ Profiles    │     │ L3 Cache    │     │ L2 Cache    │
    └─────────────┘     └─────────────┘     └─────────────┘
```

**Critical Invariant:** Privacy layer runs BEFORE any LLM sees your data.

---

## Features by Category

### 🔒 Privacy-First Architecture

| Feature | Description |
|---------|-------------|
| **Deterministic Anonymization** | Names → UUIDs (same name = same UUID across runs) |
| **PII Detection** | Scans for phone numbers, emails, personal identifiers |
| **User Control** | In-chat commands: `/egregora opt-out`, `/egregora set alias` |
| **No Name Leakage** | LLMs NEVER see real names—only see anonymized UUIDs |

### 🧠 Intelligence Engine

| Feature | Description |
|---------|-------------|
| **RAG Context** | Vector search retrieves relevant past discussions |
| **Smart Windowing** | Group by time (days/hours), message count, or custom rules |
| **Quality Ranking** | Elo system identifies best conversations for synthesis |
| **Tiered Caching** | 3-level cache (L1: enrichment, L2: RAG, L3: writer) for cost reduction |

### 🔌 Extensible I/O

| Feature | Description |
|---------|-------------|
| **Input Adapters** | WhatsApp, Slack (future), legal APIs, self-reflection |
| **Output Adapters** | MkDocs blogs, Hugo (future), custom templates |
| **Custom Prompts** | Override default prompts in `.egregora/prompts/` |
| **View Registry** | Custom SQL views for statistics and analytics |

### 🚀 Developer Experience

| Feature | Description |
|---------|-------------|
| **Zero Config** | Works immediately with sensible defaults |
| **Type-Safe** | Pydantic V2 configs, Ibis DataFrames, full type hints |
| **Incremental Processing** | `--resume` flag for checkpointed rebuilds |
| **VCR Testing** | Record/replay API calls for fast, deterministic tests |

---

## Recent Improvements (Nov 2025)

### 🎯 Tiered Caching Architecture

**Massive cost reduction for unchanged content:**

```bash
# Invalidate specific cache tier
egregora write export.zip --refresh=writer  # Only regenerate posts
egregora write export.zip --refresh=rag     # Rebuild vector index
egregora write export.zip --refresh=all     # Full rebuild
```

**Cache tiers:**
- **L1 (Enrichment)**: Asset metadata (URLs, media descriptions)
- **L2 (RAG)**: Vector embeddings + HNSW index
- **L3 (Writer)**: Generated posts with semantic hashing

**Result:** Zero-cost re-runs when input hasn't changed.

### 📦 Writer Input: Markdown → XML

**40% token reduction** by switching from Markdown tables to compact XML:

```xml
<conversation window="2025-10-28 14:00-15:00">
  <msg id="1" author="a1b2c3d4" ts="14:10">Did you see that article?</msg>
  <msg id="2" author="e5f6g7h8" ts="14:12">Yeah, wild concept</msg>
</conversation>
```

**Impact:** Cheaper API calls, better structure preservation for LLMs.

### 🔍 VSS Extension & Fallbacks

- VSS extension now loaded explicitly before HNSW operations
- Fallback avatar generation using getavataaars.com (deterministic from UUID hash)
- Idempotent scaffold (detects existing `mkdocs.yml`)

### ⚡ WhatsApp Parser Refactor

Pure Python generator (`_parse_whatsapp_lines()`) eliminates DuckDB serialization overhead:

```python
# Before: Hybrid DuckDB+Python (multiple passes)
# After: Single-pass Python generator → lazy Ibis table
```

---

## Usage Examples

### Basic Processing

```bash
# Default: 1 day per window, full rebuild
egregora write export.zip --output=./blog

# Custom windowing
egregora write export.zip --step-size=7 --step-unit=days        # Weekly posts
egregora write export.zip --step-size=100 --step-unit=messages  # By message count

# Date filtering
egregora write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Incremental (resume from last checkpoint)
egregora write export.zip --resume
```

### Privacy Commands (In-Chat)

Users control their data via commands in the chat export:

```
/egregora set alias "Dr. Smith"    # Set display name
/egregora opt-out                  # Exclude messages from all posts
/egregora opt-in                   # Re-include (default state)
```

### Multiple Input Sources

```bash
# WhatsApp (default)
egregora write export.zip --output=./blog

# Self-reflection: Feed past posts back into pipeline
egregora write ./existing-blog --source=self --output=./meta-analysis

# Brazilian judicial API (TJRO)
egregora write config.json --source=iperon-tjro --output=./legal-archive
```

### Selective Cache Invalidation

```bash
# Only regenerate posts (keep enrichment + RAG)
egregora write export.zip --refresh=writer

# Rebuild RAG index (keep enrichment + writer cache)
egregora write export.zip --refresh=rag

# Full rebuild (invalidate all caches)
egregora write export.zip --refresh=all
```

---

## Architecture & Philosophy

### Design Principles

✅ **Privacy-First** - Anonymization BEFORE any LLM processing (critical invariant)
✅ **Functional Purity** - All transforms are `Table → Table` (no hidden state)
✅ **Type-Safe** - Pydantic V2 configs, Ibis DataFrames, full type hints
✅ **Simple Default** - Full rebuild by default (`--resume` for incremental)
✅ **Alpha Mindset** - Clean breaks over backward compatibility

### Three-Layer Functional Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: orchestration/                                         │
│ High-level workflows (write_pipeline.run, agent orchestration)  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: transformations/ + adapters/ + database/               │
│ Pure functional transforms, I/O adapters, persistence           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: data_primitives/                                       │
│ Foundation models (Document, Message, protocols)                │
└─────────────────────────────────────────────────────────────────┘
```

**Key Pattern:** No `PipelineStage` abstraction—all transforms are explicit functions.

### Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Language** | Python 3.12+ | Type hints, pattern matching |
| **Package Manager** | [uv](https://github.com/astral-sh/uv) | Rust-powered, 10-100x faster than pip |
| **DataFrame** | [Ibis](https://ibis-project.org/) | Lazy, type-safe, portable SQL |
| **Database** | DuckDB + VSS | Analytics DB + vector search |
| **LLM Framework** | [Pydantic-AI](https://ai.pydantic.dev/) | Type-safe agents with tool calling |
| **LLM** | Google Gemini | Free tier, fast, configurable |
| **Site Generator** | MkDocs Material | Beautiful, plugin-rich |
| **Linter/Formatter** | ruff | Rust-powered, replaces 10+ tools |

---

## Development

### Setup

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with dev dependencies
uv sync --all-extras

# Install pre-commit hooks (MANDATORY before commits)
python dev_tools/setup_hooks.py
```

### Testing

```bash
# All tests
uv run pytest tests/

# Specific categories
uv run pytest tests/unit/         # Fast, no API calls
uv run pytest tests/integration/  # Uses VCR cassettes (record/replay)
uv run pytest tests/e2e/          # Full pipeline

# With coverage
uv run pytest --cov=egregora --cov-report=html tests/

# CI mode (no VSS extension)
uv run pytest --retrieval-mode=exact tests/
```

**VCR Recording:** First run needs `GOOGLE_API_KEY`, subsequent runs replay from `tests/cassettes/`.

### Code Quality

```bash
# All checks (run before commit)
uv run pre-commit run --all-files

# Individual tools
uv run ruff check --fix src/   # Lint + auto-fix
uv run ruff format src/        # Format (line length: 110)
uv run mypy src/               # Type check
```

### Project Structure

```
src/egregora/
├── cli/                      # Typer commands (write, init, runs)
├── orchestration/            # Layer 3: High-level workflows
│   └── write_pipeline.py    # Main pipeline coordination
├── transformations/          # Layer 2: Pure functional transforms
│   ├── windowing.py         # Window creation, checkpointing
│   └── aggregation.py       # Statistics, ranking (Elo)
├── input_adapters/          # Layer 2: Bring data IN
│   ├── whatsapp.py          # WhatsApp ZIP parser
│   ├── iperon_tjro.py       # Brazilian judicial API
│   └── self_reflection.py   # Re-ingest past posts
├── output_adapters/         # Layer 2: Take data OUT
│   └── mkdocs/adapter.py    # MkDocs site generation
├── agents/                  # Pydantic-AI agents
│   ├── writer.py            # Post generation (L3 cache)
│   ├── enricher.py          # URL/media enrichment (L1 cache)
│   └── shared/rag/          # RAG implementation (L2 cache)
├── privacy/                 # Anonymization, PII detection
├── database/                # Layer 2: Persistence
│   ├── ir_schema.py         # Schemas (IR_MESSAGE_SCHEMA, etc.)
│   ├── duckdb_manager.py    # Connection management
│   ├── views.py             # View registry (daily_aggregates, etc.)
│   └── tracking.py          # Run tracking (INSERT+UPDATE pattern)
├── data_primitives/         # Layer 1: Foundation
│   ├── document.py          # Document, DocumentType
│   └── protocols.py         # InputAdapter, OutputAdapter
└── config/                  # Pydantic V2 settings
    └── settings.py          # EgregoraConfig
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
  mode: ann  # "ann" (fast) or "exact" (no VSS extension required)

pipeline:
  step_size: 1
  step_unit: days  # "days", "hours", "messages"
```

**Custom prompts:** Place in `.egregora/prompts/` to override `src/egregora/prompts/`

---

## Output Structure

```
my-blog/
├── docs/
│   ├── posts/              # Generated posts (YYYY-MM-DD-slug.md)
│   ├── profiles/           # Anonymized author profiles with avatars
│   ├── media/              # Enriched media descriptions
│   ├── journal/            # Continuity journals (YYYY-MM-DD-HH-MM-SS.md)
│   └── index.md            # Home page
├── .egregora/
│   ├── config.yml          # Local config
│   ├── runs.duckdb         # Run tracking (INSERT+UPDATE pattern)
│   ├── rag.duckdb          # Vector embeddings (L2 cache)
│   ├── enrichment.duckdb   # Asset metadata (L1 cache)
│   ├── writer_cache.duckdb # Generated posts (L3 cache)
│   └── checkpoint.json     # Resume state (if --resume used)
└── mkdocs.yml              # Site config (MkDocs Material)
```

---

## Use Cases

| Scenario | Input | Output | Value |
|----------|-------|--------|-------|
| **Research Groups** | Journal club chats | Literature reviews | Synthesize scattered insights |
| **Legal Monitoring** | TJRO API feed | Searchable archive | Track judicial communications |
| **Team Documentation** | Slack threads | Knowledge base | Preserve institutional memory |
| **Self-Reflection** | Past blog posts | Meta-analysis | Identify gaps, avoid repetition |
| **Content Creators** | Community Discord | Story angles | Extract narrative threads |
| **Personal Archives** | Family WhatsApp | Life journal | Turn conversations into memoir |

---

## Contributing

Contributions welcome! **Alpha mindset applies:**

✅ Clean breaks for better architecture
❌ No backward compatibility required
✅ Modern patterns (Pydantic V2, frozen dataclasses)
❌ No functions with >5 params (use config objects)

### Before Contributing

1. Read [CLAUDE.md](CLAUDE.md) for architecture and conventions
2. Install pre-commit hooks: `python dev_tools/setup_hooks.py`
3. Ensure tests pass: `uv run pytest tests/`
4. Check that your changes preserve `IR_MESSAGE_SCHEMA` columns

### Commit Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Developer guide (architecture, patterns, conventions)
- **[SECURITY.md](SECURITY.md)** - Security policy
- **[docs/](docs/)** - Guides, architecture docs, API reference
- **[tests/fixtures/golden/](tests/fixtures/golden/)** - Example outputs

---

## Roadmap

- [x] WhatsApp source with privacy-first anonymization
- [x] MkDocs Material output with blogging plugin
- [x] Pydantic-AI agents with tool calling
- [x] RAG retrieval with vector search (DuckDB VSS)
- [x] Elo-based content ranking
- [x] Interactive AI editor for post refinement
- [x] Auto-generated statistics dashboard
- [x] Tiered caching architecture (L1/L2/L3)
- [x] XML conversation format (40% token reduction)
- [ ] Slack/Discord input adapters
- [ ] Hugo output adapter
- [ ] Multi-language support
- [ ] Real-time incremental processing
- [ ] Web UI for configuration and monitoring

---

## Acknowledgments

Built on the shoulders of giants:

- [Pydantic-AI](https://ai.pydantic.dev/) - Type-safe LLM agents with structured outputs
- [Ibis](https://ibis-project.org/) - Elegant, portable DataFrame API
- [DuckDB](https://duckdb.org/) - Fast analytics database with VSS extension
- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) - Beautiful documentation theme
- [uv](https://github.com/astral-sh/uv) - Rust-powered Python package manager
- [ruff](https://github.com/astral-sh/ruff) - Comprehensive linter/formatter

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Philosophy

> "An egregore is a collective consciousness that emerges from the thoughts and interactions of a group. Egregora makes this tangible—transforming scattered conversations into coherent knowledge, preserving the emergent intelligence that would otherwise dissolve into the scroll."

**The Loom of Logos weaves your collective wisdom into living documentation.**

Egregora turns your group chats into **structured memory**, your team discussions into **institutional knowledge**, and your scattered insights into **coherent narratives**—all while keeping your privacy sacred.

---

**Egregora** - From collective consciousness to structured knowledge.
