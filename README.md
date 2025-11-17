# Egregora 🤖 → 📝

**Emergent Group Reflection Engine Generating Organized Relevant Articles**

> **Turn your group chat into a magazine.**

Transform messy WhatsApp conversations into beautifully written blog posts. An AI-powered publishing system that synthesizes your group's collective intelligence into coherent, insightful articles—while keeping everyone's privacy intact.

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Powered by uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## 💡 What Does It Do?

Egregora transforms informal group conversations into polished blog posts. Here's what happens:

**Input:** Your WhatsApp group discussing AI, philosophy, or that article someone shared
**Output:** A thoughtful blog post like ["The License to Exist: What Happens When the System Says 'Write Anything You Want'?"](tests/fixtures/golden/expected_output/posts/2025-10-28-the-license-to-exist-emergent-agency-in-a-test-environment.md) with proper formatting, citations, and metadata

### ✨ Key Features

<table>
<tr>
<td width="50%">

**🧠 Emergent Intelligence**
AI synthesizes scattered messages into coherent narratives, finding patterns and themes you didn't know existed

**🛡️ Privacy-First Architecture**
Real names → deterministic UUIDs before any AI processing. No PII ever reaches the LLM.

**📊 Context-Aware Writing**
RAG retrieval ensures posts reference past discussions, creating a coherent knowledge base over time

</td>
<td width="50%">

**⚙️ Zero Configuration**
Run directly with `uvx` - no installation, no setup, just works

**🎯 Quality Ranking**
Built-in Elo system helps identify your best content

**✏️ AI Editor**
Interactive refinement of generated posts with conversational AI

</td>
</tr>
</table>

### 🎯 Perfect For

- **Research groups** turning discussions into publication drafts
- **Reading clubs** synthesizing book conversations into essays
- **Remote teams** creating knowledge bases from Slack/WhatsApp
- **Personal archiving** preserving meaningful conversations as structured content
- **Content creators** finding story angles in community discussions

---

## 🚀 Quick Start

Get your AI-powered blog running in under 5 minutes:

### Step 1: Get a Gemini API Key (Free)

1. Visit [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key)
2. Click "Get API key" → Create API key
3. Copy the key

```bash
# Set the API key
export GOOGLE_API_KEY="your-api-key-here"
```

### Step 2: Export Your WhatsApp Chat

On WhatsApp:
1. Open the group chat
2. Tap **⋮** (menu) → **More** → **Export chat**
3. Choose **"Without media"** (recommended for privacy)
4. Save the `.zip` file

### Step 3: Run Egregora

```bash
# Install uv (one-time, ~30 seconds)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Process your chat (creates a blog in ./my-blog)
uvx --from git+https://github.com/franklinbaldo/egregora \
    egregora write whatsapp-export.zip --output=./my-blog

# Serve locally
cd my-blog
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

**That's it!** Open [http://localhost:8000](http://localhost:8000) to see your blog. Generated posts are grouped by time windows (filenames such as `2025-10-28 14:10 to 14:15.md`) and all runtime state lives under `.egregora/` (config, RAG data, optional checkpoints). By default, the pipeline always rebuilds from scratch for simplicity. Use `--resume` flag to enable incremental processing.

**Output layout**
- `docs/posts/<window>.md` — windows are labeled with the start/end timestamps (e.g. `2025-10-28 14:10 to 14:15.md`)
- `docs/profiles/` — anonymized author profiles
- `.egregora/` — runtime state (config, RAG index, checkpoints when `--resume` is used)

---

## 🏗️ Architecture

Egregora uses a **modern, staged pipeline** architecture built for clarity and extensibility:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Ingestion  │ -> │   Privacy   │ -> │ Enrichment  │
└─────────────┘    └─────────────┘    └─────────────┘
      ↓                   ↓                   ↓
  Parse msgs        Anonymize UUIDs     Enrich context
  (pyparsing)       Detect PII          (LLM + cache)

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Knowledge  │ <- │ Generation  │ -> │ Publication │
└─────────────┘    └─────────────┘    └─────────────┘
      ↑                   ↓                   ↓
   RAG Index        Pydantic-AI          MkDocs Site
   Annotations      Agent w/ Tools       + Templates
```

### Modern Design Principles

**✅ Configuration Objects** (Phase 2)
- Reduced function signatures from 12-16 parameters → 3-6 parameters
- Uses Pydantic V2 `EgregoraConfig` + frozen `RuntimeContext` dataclasses

**✅ Simple Resume Logic** (Opt-In)
- Checkpoint-based incremental processing disabled by default
- Enable with `--resume` flag for large datasets
- Default: Always rebuild from scratch (predictable, simple)

**✅ Source-Based Organization** (Phase 6)
- Source-specific code in `sources/{whatsapp,slack}/`
- Generic interfaces in `ingestion/base.py`
- Easy to add new sources (Discord, Telegram, etc.)

**✅ Privacy-First**
- **Critical invariant**: Anonymization happens BEFORE any LLM sees data
- Real names never leave your machine
- Deterministic UUIDs ensure consistency across runs

### Tech Stack

- **Language**: Python 3.12+ with type hints
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (Rust-powered, fast)
- **DataFrame API**: [Ibis](https://ibis-project.org/) (type-safe, lazy)
- **Database**: DuckDB with VSS extension (vector search)
- **LLM Framework**: [Pydantic-AI](https://ai.pydantic.dev/) (type-safe agents)
- **LLM Provider**: Google Gemini (switchable via env var)
- **Static Site**: MkDocs Material (beautiful, fast)
- **Parsing**: pyparsing (declarative, composable)
- **Linting**: ruff (Rust-powered, comprehensive)

---

## 📚 Usage Examples

### Basic Processing

```bash
# Process with default settings (1 day per window, full rebuild)
egregora write export.zip --output=./blog

# Group by week (7 days per window)
egregora write export.zip --step-size=7 --step-unit=days

# Group by message count (100 messages per window)
egregora write export.zip --step-size=100 --step-unit=messages

# Filter date range
egregora write export.zip \
    --from-date=2025-01-01 \
    --to-date=2025-01-31

# Custom timezone (important for accurate timestamps)
egregora write export.zip --timezone="America/Sao_Paulo"

# Resume from checkpoint (opt-in incremental processing)
egregora write export.zip --output=./blog --resume
```

### Privacy Controls

Users can control their participation via in-chat commands:

```
/egregora set alias "Dr. Smith"       # Set display name
/egregora set bio "AI researcher"     # Add bio
/egregora opt-out                     # Exclude from posts
/egregora opt-in                      # Re-include
/egregora set avatar <URL>            # Set avatar
/egregora remove avatar               # Remove avatar
```

---

## 🛠️ Development

### Setup

```bash
# Clone the repository
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with all extras (dev, test, docs)
uv sync --all-extras

# Install pre-commit hooks (auto-format, lint, type-check)
python dev_tools/setup_hooks.py
```

### Testing

```bash
# Run all tests
uv run pytest tests/

# Run specific test categories
uv run pytest tests/unit/              # Unit tests (fast)
uv run pytest tests/integration/       # Integration tests (requires API key)
uv run pytest tests/agents/            # Agent-specific tests
uv run pytest tests/e2e/               # End-to-end tests

# With coverage
uv run pytest --cov=egregora --cov-report=html tests/

# VCR cassette replay (no API key needed for most tests)
uv run pytest tests/e2e/
```

**Note**: Integration tests use [pytest-vcr](https://pytest-vcr.readthedocs.io/) to record/replay Gemini API calls. First runs need `GOOGLE_API_KEY`, subsequent runs use cassettes from `tests/cassettes/`.

### Code Quality

```bash
# Run all checks (recommended before commit)
uv run pre-commit run --all-files

# Individual tools
uv run ruff check src/              # Lint
uv run ruff format src/             # Format
uv run ruff check --fix src/        # Auto-fix
uv run mypy src/                    # Type check
```

**Line length**: 110 characters (see `pyproject.toml`)

### Project Structure

```
src/egregora/
├── cli.py                    # Typer CLI (entry point)
├── pipeline.py               # Pipeline utilities (group_by_period)
├── config/                   # Pydantic V2 configuration
│   ├── schema.py            # EgregoraConfig (root config)
│   ├── types.py             # Runtime context dataclasses
│   └── loader.py            # Config loading utilities
├── sources/                  # Source-specific implementations
│   └── whatsapp/            # WhatsApp source
│       ├── grammar.py       # pyparsing grammar
│       ├── parser.py        # parse_source() function
│       ├── input.py         # WhatsAppInputSource
│       └── models.py        # WhatsAppExport dataclass
├── ingestion/               # Generic source interfaces
│   ├── base.py             # InputSource abstraction
│   └── __init__.py         # Re-exports for convenience
├── privacy/                 # Anonymization + PII detection
├── enrichment/              # LLM-powered context enrichment
├── agents/                  # Pydantic-AI agents
│   ├── writer/             # Post generation agent
│   ├── editor/             # Interactive editing agent
│   ├── ranking/            # Elo ranking agent
│   └── tools/              # Agent tools (RAG, annotations, profiler)
├── database/                # DuckDB + schemas
├── rendering/               # MkDocs output format
└── utils/                   # Utilities (cache, batch, logging)
```

---

## 📖 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete developer guide with modern patterns
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines + TENET-BREAK philosophy
- **[BREAKING_CHANGES.md](BREAKING_CHANGES.md)** - Migration guide for Phases 2-6 modernization
- **[SECURITY.md](SECURITY.md)** - Security policy
- **[docs/](docs/)** - Comprehensive guides and API reference

### Key Concepts

**TENET-BREAK Philosophy**: Intentional violations of core principles for pragmatic reasons. Format:
```python
# TENET-BREAK(scope)[@owner][P0|P1|P2][due:YYYY-MM-DD]:
# tenet=<code>; why=<constraint>; exit=<condition> (#issue)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 🤝 Contributing

Contributions are welcome! We use an **alpha mindset**:
- ✅ Clean breaks for better architecture
- ❌ No backward compatibility required
- ✅ Modern patterns (Pydantic V2, frozen dataclasses, type hints)
- ❌ No functions with >5 parameters (use config objects)

### Before Contributing

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines
2. Review [CLAUDE.md](CLAUDE.md) for modern patterns
3. Check [BREAKING_CHANGES.md](BREAKING_CHANGES.md) for recent changes
4. Install pre-commit hooks: `python dev_tools/setup_hooks.py`

### Common Tasks

```bash
# Fix linting issues automatically
uv run ruff check --fix src/

# Format code
uv run ruff format src/

# Run type checker
uv run mypy src/

# Run tests with coverage
uv run pytest --cov=egregora tests/
```

---

## 📋 Roadmap

- [x] WhatsApp source support with privacy-first anonymization
- [x] MkDocs Material output format
- [x] Pydantic-AI agent with tool calling
- [x] RAG retrieval for context-aware posts
- [x] Elo-based post ranking system
- [x] Interactive AI editor for post refinement
- [x] Modern architecture (Phases 0-6 complete)
- [ ] Slack source support
- [ ] Discord source support
- [ ] Hugo output format
- [ ] Multi-language support
- [ ] Automated testing improvements
- [ ] Performance optimizations

---

## ⚖️ License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **[Pydantic-AI](https://ai.pydantic.dev/)** for type-safe LLM agents
- **[Ibis](https://ibis-project.org/)** for the elegant DataFrame API
- **[DuckDB](https://duckdb.org/)** for the amazing analytics database
- **[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)** for the beautiful theme
- **[uv](https://github.com/astral-sh/uv)** for the blazing-fast package manager
- **[ruff](https://github.com/astral-sh/ruff)** for the comprehensive linter/formatter

---

## 📧 Contact

- **Repository**: [github.com/franklinbaldo/egregora](https://github.com/franklinbaldo/egregora)
- **Issues**: [github.com/franklinbaldo/egregora/issues](https://github.com/franklinbaldo/egregora/issues)

---

**Egregora** - Because your group chat deserves to be preserved as more than just scrollback.
