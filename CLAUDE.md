# Code of the Weaver

> Guidelines for contributors and AI agents working on Egregora

---

## Project Overview

**Egregora** transforms chat history into stories that remember. It creates connected narratives with contextual memory, automatically discovers meaningful conversations, and generates portraits of participants.

### Three Magical Features

These features are **enabled by default** and work without configuration:

1. **Contextual Memory (RAG)**: Posts reference previous discussions via LanceDB vector search
2. **Content Discovery (Ranking)**: ELO-based ranking surfaces meaningful conversations
3. **Author Profiles**: Emotional portraits of chat participants

### Core Philosophy

- **Privacy-first**: Runs locally by default
- **Performance-first**: Uses DuckDB and Ibis for efficient data processing
- **Type-safe AI**: Built with Pydantic-AI for structured outputs
- **Functional patterns**: Data flows through pure functions (`Table -> Table`)
- **Magic by default**: RAG, ranking, and profiling work automatically

---

## Project Structure

```
src/egregora/
├── agents/              # Pydantic-AI agents
│   ├── banner/         # Image generation
│   ├── profile/        # Author profile generation
│   ├── reader/         # ELO-based content ranking
│   ├── shared/         # Shared agent infrastructure
│   ├── tools/          # Agent tools and skill injection
│   ├── writer.py       # Main writer agent
│   └── enricher.py     # Media/URL enrichment
├── database/           # DuckDB persistence
│   ├── schemas.py      # Table definitions
│   ├── duckdb_manager.py
│   ├── repository.py   # Generic data repository
│   ├── elo_store.py    # ELO ranking storage
│   ├── task_store.py   # Background task tracking
│   └── streaming/      # ZIP streaming for large files
├── input_adapters/     # Platform-specific input handlers
│   ├── whatsapp/       # WhatsApp export adapter
│   ├── base.py         # InputAdapter protocol
│   └── registry.py     # Adapter discovery
├── output_sinks/       # Output format handlers
│   ├── mkdocs/         # MkDocs Material implementation
│   └── base.py         # OutputSink protocol
├── orchestration/      # Pipeline coordination
│   ├── pipelines/
│   │   └── write.py    # Core orchestration logic
│   ├── runner.py       # Pipeline execution loop
│   ├── context.py      # Execution context
│   ├── journal.py      # Idempotent processing journal
│   └── cache.py        # Caching layer
├── rag/                # Vector knowledge base (LanceDB)
│   ├── lancedb_backend.py
│   ├── embeddings.py   # Embedding generation
│   ├── chunking.py     # Text chunking strategies
│   └── ingestion.py    # Document ingestion
├── config/             # Configuration (Pydantic Settings + TOML)
├── cli/                # CLI (Typer)
├── llm/                # LLM provider abstraction
│   ├── providers/      # Model providers (Gemini)
│   ├── model_fallback.py
│   ├── rate_limit.py
│   └── retry.py
├── transformations/    # Pure data transformations
├── data_primitives/    # Core data types (Document, datetime utils)
├── knowledge/          # Profile extraction
├── ops/                # Media processing, taxonomy
├── security/           # Filesystem safety, PII, SSRF, ZIP validation
├── prompts/            # Jinja2 prompt templates
└── templates/          # Site templates
```

---

## Development Setup

### Prerequisites

- Python 3.12 (see `.python-version`)
- [uv](https://github.com/astral-sh/uv) for dependency management
- Google Gemini API key

### Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Set API key
export GOOGLE_API_KEY="your-api-key"
```

### Running Tests

```bash
# Unit tests (parallel)
uv run pytest tests/unit/ -n auto -v

# E2E tests
uv run pytest tests/e2e/ -n auto -v

# With coverage
uv run pytest --cov=src/egregora --cov-branch --cov-report=term

# Skip slow tests
uv run pytest -m "not slow"
```

### Code Quality

```bash
# Linting (Ruff)
uv run ruff check src/ tests/

# Type checking (MyPy)
uv run mypy src/

# Dead code detection
uv run vulture src/ tests/

# Security scanning
uv run bandit -r src/

# All pre-commit hooks
uv run pre-commit run --all-files
```

---

## Code Standards

### Formatting

- **Ruff line length**: 110 characters
- **Black line length**: 100 characters
- **Target Python**: 3.12

### Imports

- **Absolute imports only** (relative imports banned by Ruff)
- **Banned imports**: `pandas`, `pyarrow` (use `ibis-framework` instead)

### Type Annotations

- Required for all function signatures
- MyPy strict mode enabled (some CLI exceptions)

### Docstrings

- Google-style docstrings
- Required for public classes and complex functions
- Not required for tests or internal helpers

### Naming

| Type | Style | Example |
|------|-------|---------|
| Files | snake_case | `writer_agent.py` |
| Classes | PascalCase | `WriterAgent` |
| Functions | snake_case | `process_window` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Private | _leading_underscore | `_internal_method` |

---

## Exception Hierarchy

```
EgregoraError (base)
├── ConfigError
├── DatabaseError
├── AgentError
│   └── PromptTooLargeError
├── OrchestrationError
├── TransformationsError
├── OutputAdapterError
├── WhatsAppError
├── RAGError
├── EmbeddingError
├── LLMProviderError
├── ProfileError
├── DateTimeError
├── SlugifyError
├── AvatarProcessingError
└── ToolRegistryError
```

Define domain-specific exceptions inheriting from `EgregoraError`.

---

## Key Patterns

### 1. Ibis-First Data Processing

Always use Ibis for data operations, never pandas:

```python
# Correct
def filter_messages(table: ibis.Table, min_length: int) -> ibis.Table:
    return table.filter(ibis._['message_length'] >= min_length)
```

### 2. Adapter Pattern

Input and output adapters implement protocols:

```python
class InputAdapter(Protocol):
    def read(self, source: Path) -> Table: ...

class OutputSink(Protocol):
    def write(self, data: Table, path: Path) -> None: ...
```

### 3. Pydantic-AI Agents

AI agents use structured outputs:

```python
agent = Agent(
    model="google-gla:gemini-2.0-flash-exp",
    deps_type=WriterDeps,
    system_prompt_template=template,
)

result = agent.run_sync(prompt=prompt, deps=deps, tools=[...])
```

### 4. RAG with LanceDB

Vector knowledge base for contextual memory:

- Stores conversation history as embeddings
- Retrieves related discussions when writing
- Enabled by default, works transparently

### 5. Configuration Management

Use Pydantic Settings:

```python
from pydantic_settings import BaseSettings

class EgregoraConfig(BaseSettings):
    google_api_key: str = Field(alias='GOOGLE_API_KEY')
```

### 6. Streaming for Large Files

```python
from egregora.database.streaming import stream_whatsapp_zip

for chunk in stream_whatsapp_zip(zip_path):
    process_chunk(chunk)
```

---

## Testing

### Structure

```
tests/
├── unit/          # Fast, isolated tests
├── e2e/           # End-to-end pipeline tests
├── integration/   # Tests with real dependencies
├── fixtures/      # Shared test data
│   ├── golden/   # Expected output snapshots
│   └── input/    # Input test data
├── benchmarks/    # Performance baselines
├── evals/         # LLM evaluation tests
└── conftest.py    # Global fixtures
```

### Markers

- `@pytest.mark.slow`: Tests > 1 second
- `@pytest.mark.e2e`: Full pipeline tests
- `@pytest.mark.benchmark`: Performance baselines
- `@pytest.mark.quality`: Code quality checks

### Test Dependencies

- `pytest`, `pytest-asyncio`, `pytest-xdist`, `pytest-mock`
- `hypothesis`: Property-based testing
- `freezegun`: Deterministic timestamps
- `syrupy`: Snapshot testing
- `respx`: HTTP mocking
- `faker`: Test data generation
- `moto`: AWS mocking

---

## CI/CD

### GitHub Actions Workflows

**CI (`ci.yml`)** - Runs on push/PR:
- `pre-commit`: Ruff linting, formatting, vulture
- `test-unit`: Unit tests with coverage (10 min timeout)
- `test-e2e`: E2E tests with coverage (30 min timeout)
- `security`: Dependency vulnerability scanning (safety, pip-audit)
- `build`: Package build verification

**Jules (`jules.yml`)** - AI agent automation:
- Stateless persona rotation
- API-driven session management
- Auto-merge on CI pass
- Auto-fix for failed PRs

**Docs (`docs-pages.yml`)** - Documentation deployment

### Pre-commit Hooks

- `ruff check --fix --unsafe-fixes`
- `vulture` (dead code)
- `check-private-imports`
- `check-test-config`
- Standard hooks: JSON, YAML, merge conflicts, large files

---

## Key Dependencies

```
Core:
  ibis-framework[duckdb]    # Data processing
  pydantic-ai              # Structured LLM outputs
  google-genai             # Gemini API
  lancedb==0.27.0          # Vector store
  diskcache                # Embedding cache
  typer                    # CLI framework

Database:
  DuckDB                   # OLAP database
  LanceDB                  # Vector store

Content:
  mkdocs-material[imaging] # Static site generation
  jinja2                   # Template rendering
  python-frontmatter       # Markdown with YAML

Utilities:
  pydantic-settings        # Config management
  tenacity                 # Retry logic
  ratelimit                # Rate limiting
  scikit-learn             # ELO algorithm
```

---

## Jules Automation System

The repository uses autonomous AI agents (Jules personas) for maintenance. See [.team/README.md](.team/README.md) for full documentation.

### 21 Personas (20 AI + 1 Human)

Persona prompts use the **ROSAV framework** (Role, Objective, Situation, Act, Verify) defined in `.team/repo/templates/base/persona.md.j2`. Each persona extends this base template via Jinja2 inheritance.

| Emoji | Name | Role |
|:---:|:---|:---|
| 💯 | Absolutist | Legacy code removal |
| 🔨 | Artisan | Code craftsmanship |
| 🥒 | BDD Specialist | Behavior-driven testing |
| ⚡ | Bolt | Performance optimization |
| 🏗️ | Builder | Data architecture |
| 🎭 | Curator | UX/UI evaluation |
| 📦 | Deps | Dependency management |
| 💎 | Essentialist | Radical simplicity |
| ⚒️ | Forge | Feature implementation |
| 🧔 | Franklin | Human project lead |
| 🧹 | Janitor | Code cleanup |
| 📚 | Lore | System historian |
| 💝 | Maya | User advocate |
| 🔍 | Meta | System introspection |
| 🔮 | Oracle | Technical support |
| 💣 | Sapper | Exception patterns |
| ✍️ | Scribe | Documentation |
| 🛡️ | Sentinel | Security audits |
| 🧑‍🌾 | Shepherd | Test coverage |
| 🌊 | Streamliner | Data optimization |
| 🔭 | Visionary | Strategic RFCs |

### Running Personas

```bash
# Run specific persona
uv run jules schedule tick --prompt-id curator

# Dry run
uv run jules schedule tick --prompt-id curator --dry-run

# Run all
uv run jules schedule tick --all
```

---

## AI Agent Guidelines

### General Principles

1. **Read before modifying**: Always read files before making changes
2. **Understand context**: Review related code and documentation
3. **Follow patterns**: Match existing code style
4. **Test your changes**: Ensure tests pass before committing
5. **Document decisions**: Update relevant docs where needed

### Before Making Changes

1. Search for similar patterns with grep/glob
2. Check for existing tests
3. Review `exceptions.py` for proper error types

### Making Changes

1. Small commits: One logical change per commit
2. Descriptive messages: Explain why, not just what
3. Update tests for changed behavior
4. Run pre-commit hooks

### Code Review Checklist

- [ ] Type annotations present and correct
- [ ] Tests added/updated
- [ ] No banned imports (pandas, pyarrow)
- [ ] Docstrings for public APIs
- [ ] Error handling with custom exceptions

---

## Ruff Configuration Highlights

### Legitimately Ignored Rules

| Rule | Reason |
|------|--------|
| `S608` | False positive with DuckDB parameterized queries |
| `ARG001/002/005` | Unused args needed for interface compatibility |
| `ANN401` | `Any` type sometimes necessary |
| `SLF001` | Private member access needed for testing |
| `C901`, `PLR*` | Complexity tracked but not blocking |
| `DTZ*` | Timezone enforcement (gradual migration) |

### Per-File Ignores

- `tests/**/*.py`: Allow asserts, magic values, skip type annotations
- `src/egregora/cli/*.py`: Allow `B008` (Typer requires Option() in defaults)
- Fault-tolerant components: Allow `BLE001` for graceful degradation

---

## Common Pitfalls

### 1. DuckDB SQL Injection (S608)

This is a false positive. Ibis handles parameterization safely:

```python
# Safe - Ibis handles parameterization
table.filter(ibis._['user_input'] == user_value)
```

### 2. Timezone-Naive Datetimes

Use timezone-aware datetimes for new code:

```python
from datetime import datetime, timezone

now = datetime.now(tz=timezone.utc)  # Correct
```

### 3. Test Isolation

Always clean up test resources:

```python
@pytest.fixture
def temp_db():
    db_path = "test.db"
    yield db_path
    if Path(db_path).exists():
        Path(db_path).unlink()
```

---

## Contributing

### Workflow

1. Create branch: `git checkout -b feature/your-feature`
2. Make changes following code standards
3. Run tests: `uv run pytest tests/`
4. Run pre-commit: `uv run pre-commit run --all-files`
5. Commit with descriptive message
6. Push and open PR

### Commit Message Format

```
<type>: <description>

[optional body]
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## Resources

- [Ibis Documentation](https://ibis-project.org/)
- [Pydantic-AI Documentation](https://ai.pydantic.dev/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)

---

## Questions?

- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **Security**: See [SECURITY.md](SECURITY.md)

---

*Maintained by the Weaver persona and human contributors. Last updated: 2026-01-29*
