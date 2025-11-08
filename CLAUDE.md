# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**Egregora** transforms WhatsApp group conversations into beautiful blog posts using LLM-powered synthesis. It's a privacy-first, staged pipeline that anonymizes personal data before any AI processing.

**Repository**: https://github.com/franklinbaldo/egregora
**Python**: 3.12+
**Package Manager**: uv
**Primary LLM**: Google Gemini API

## Common Commands

### Development Setup

```bash
# Install dependencies with all extras
uv sync --all-extras

# Quick setup (installs deps + pre-commit hooks)
python dev_tools/setup_hooks.py
```

### Testing

```bash
# Run all tests
uv run pytest tests/

# Run specific test categories
uv run pytest tests/unit/              # Unit tests
uv run pytest tests/integration/       # Integration tests (requires API key)
uv run pytest tests/e2e/               # End-to-end tests
uv run pytest tests/agents/            # Agent-specific tests

# Run specific test
uv run pytest tests/unit/test_anonymizer.py
uv run pytest -k test_parse_basic

# With coverage
uv run pytest --cov=egregora --cov-report=html tests/

# VCR cassette replay (no API key needed for most tests)
uv run pytest tests/e2e/test_with_golden_fixtures.py
```

**Important**: Integration tests use pytest-vcr to record/replay Gemini API calls. First runs need `GOOGLE_API_KEY`, subsequent runs use cassettes from `tests/cassettes/`.

### Linting & Formatting

```bash
# All checks (recommended before commit)
uv run pre-commit run --all-files

# Individual tools
uv run ruff check src/              # Lint
uv run ruff format src/             # Format
uv run ruff check --fix src/        # Auto-fix
uv run mypy src/                    # Type check
```

**Line length**: 110 characters (see pyproject.toml)

### Running the Pipeline

```bash
# Set API key
export GOOGLE_API_KEY="your-api-key"

# Process WhatsApp export (creates blog in ./output, default: 1 day windows)
uv run egregora process whatsapp-export.zip --output=./output

# Time-based windowing (default)
uv run egregora process export.zip --step-size=1 --step-unit=days  # 1 day (default)
uv run egregora process export.zip --step-size=7 --step-unit=days  # 1 week

# Message count windowing
uv run egregora process export.zip --step-size=100 --step-unit=messages

# Serve generated blog locally
cd output
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve

# Other commands
uv run egregora edit posts/my-post.md        # AI-powered post editor
uv run egregora rank --site-dir=. --comparisons=50  # Elo ranking
```

## Parallel Task Delegation with Subagents

When working on repetitive tasks across multiple files (e.g., fixing the same linting rule in 10+ files), use **parallel subagent delegation** for maximum efficiency.

### When to Use Subagents

Use parallel subagents when you have:
- **Similar tasks** across multiple files (same linting rule, same refactoring pattern)
- **Independent work** - files don't depend on each other
- **Clear instructions** - the fix pattern is well-defined
- **5+ files** - worthwhile for parallelization overhead

### How to Delegate Tasks

Launch multiple subagents in a single message using multiple `Task` tool calls:

```python
# Example: Fix BLE001 (blind exception catches) across 10 files
# Launch 5 subagents in parallel, each handling 2-3 related files

Task 1: Fix BLE001 in writer_agent.py
Task 2: Fix BLE001 in cli.py
Task 3: Fix BLE001 in enrichment/batch.py + enrichment/core.py
Task 4: Fix BLE001 in pipeline files (3 files)
Task 5: Fix BLE001 in utils files (3 files)
```

**Key guidelines for subagent prompts:**
1. **Be specific**: State exact file paths and error codes to fix
2. **Provide clear rules**: "NEVER use `except Exception:`" - let errors propagate
3. **Include verification**: "Run `ruff check <file> --select=BLE001` to verify"
4. **Disable git operations**: "Do NOT commit or push changes"
5. **Request summary**: "Return: Summary of changes and confirmation errors are fixed"

### Example Results

**Phase 2C Exception Handling** (24 errors across 13 files):
- Launched 6 subagents in parallel
- Completed in ~2 minutes vs. ~15-20 minutes sequentially
- Fixed: 13 BLE001 errors + 11 TRY301 errors
- All subagents returned detailed summaries for review

### After Subagents Complete

1. **Verify their work**: Run `ruff check` to confirm all errors fixed
2. **Review changes**: Check git diff for correctness
3. **Run tests**: Ensure no regressions introduced
4. **Commit once**: Single commit with comprehensive message documenting all fixes
5. **Format code**: Run `ruff format` before committing

### Anti-Patterns to Avoid

❌ **Don't delegate when:**
- Tasks require coordinated changes across files (use sequential approach)
- You need to see intermediate results to decide next steps
- Files are interdependent (changes in one affect others)
- The task is exploratory (better to do it yourself first)

❌ **Don't:**
- Let subagents commit/push (causes merge conflicts)
- Give vague instructions (leads to inconsistent fixes)
- Delegate without a clear pattern (subagents need examples)
- Skip verification after subagents complete

### Benefits

✅ **Speed**: 5-10x faster for multi-file refactoring
✅ **Consistency**: All subagents follow same instructions
✅ **Focus**: You review summaries instead of making repetitive edits
✅ **Scalability**: Handles 20+ files as easily as 5 files

## Architecture: Staged Pipeline

Egregora uses a **staged pipeline** (not traditional ETL) with feedback loops and stateful operations:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Ingestion  │ -> │   Privacy   │ -> │ Augmentation│
└─────────────┘    └─────────────┘    └─────────────┘
      ↓                   ↓                   ↓
   Parse ZIP        Anonymize UUIDs     Enrich context
                    Detect PII          Build profiles

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Knowledge  │ <- │ Generation  │ -> │Publication  │
└─────────────┘    └─────────────┘    └─────────────┘
      ↑                   ↓                   ↓
   RAG Index        LLM Writer           MkDocs Site
   Annotations      Tool Calling         Templates
   Rankings
```

### Pipeline Stages

1. **Ingestion** (`src/egregora/ingestion/`, `src/egregora/sources/`)
   - **MODERN (Phase 6)**: WhatsApp parsing moved to `sources/whatsapp/parser.py`
   - Entry point: `parse_source()` (renamed from `parse_export` in Phase 6)
   - Generic interfaces in `ingestion/base.py` (InputSource, InputMetadata)
   - Source-specific implementations in `sources/{whatsapp,slack}/`
   - Schema: `CONVERSATION_SCHEMA` (timestamp, author, message, original_line, tagged_line, message_id)

2. **Privacy** (`src/egregora/privacy/`)
   - **Critical invariant**: Anonymization happens BEFORE any LLM sees data
   - Converts real names → deterministic UUIDs (`anonymizer.py`)
   - PII detection: phones, emails, addresses (`detector.py`)
   - Respects opt-out commands in messages

3. **Augmentation** (`src/egregora/enrichment/`)
   - LLM-powered URL/media descriptions (`enrichment/core.py`)
   - Author profile generation (`agents/tools/profiler.py`)
   - Uses DiskCache for persistence across runs (`.egregora-cache/`)

4. **Knowledge** (`src/egregora/agents/tools/`)
   - **RAG**: Vector store with DuckDB VSS (`agents/tools/rag/store.py`)
   - **Annotations**: Conversation metadata (`agents/tools/annotations/`)
   - **Rankings**: Elo-based post quality (`agents/ranking/`)

5. **Generation** (`src/egregora/agents/writer/`)
   - Pydantic-AI agent with tool calling (`writer_agent.py`)
   - Decides: 0-N posts per window, themes, structure ("trust the LLM")
   - Tools: `write_post`, `read/write_profile`, `search_media`, `annotate`, `generate_banner`
   - Backend switchable via `EGREGORA_LLM_BACKEND` env var

6. **Publication** (`src/egregora/init/`, `rendering/`)
   - MkDocs site scaffolding (`init/scaffolding.py`)
   - Jinja2 templates for posts, profiles, indexes

### Key Design Principles

1. **"Trust the LLM"** - Give AI full context, let it make editorial decisions (post count, themes, structure)
2. **Ibis tables everywhere** - Stay in DuckDB, convert to pandas only at boundaries
3. **Privacy-first architecture** - Anonymize before LLM processing (no PII in API calls)
4. **Schemas as contracts** - All tables conform to centralized schemas (`database/schema.py`)
5. **Functional transformations** - Pipeline stages are pure functions: `Table → Table`
6. **Alpha mindset (Phases 2-6)** - No backward compatibility; clean breaks for better architecture

### Modern Patterns (Phases 2-6 Refactoring)

The codebase has undergone comprehensive modernization (2025-01). Follow these patterns:

**Configuration Objects (Phase 2)**:
- ✅ Use `EgregoraConfig` instead of 10+ individual parameters
- ✅ Use `RuntimeContext` dataclasses for execution-specific values
- ✅ Example: `write_posts_with_pydantic_agent(prompt, config, context)` instead of 12 params
- ❌ Don't add new functions with >5 parameters

**Frozen Dataclasses (Phase 2)**:
```python
@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    """Runtime context for writer agent execution."""
    start_time: datetime  # Window start timestamp
    end_time: datetime    # Window end timestamp
    output_dir: Path
    profiles_dir: Path
    rag_dir: Path
    client: Any
    annotations_store: AnnotationStore | None = None
    # Frozen dataclass - immutable after creation
```

**Simple Resume Logic (Phase 3)**:
- ✅ Check if output files exist → skip if yes, process if no
- ❌ Don't use complex checkpoint systems with JSON metadata
- Example: `if window_has_posts(window_index, posts_dir): continue`

**Source Organization (Phase 6)**:
- ✅ Source-specific code in `sources/{whatsapp,slack}/`
- ✅ Generic interfaces in `ingestion/base.py`
- ✅ Re-export from `ingestion/__init__.py` for convenience
- Example: WhatsApp parser in `sources/whatsapp/parser.py`, re-exported from `ingestion/`

**Function Naming (Phase 6)**:
- ✅ Use generic names: `parse_source()` not `parse_export()`
- ✅ Alpha mindset: rename without backward compatibility if it improves clarity

**Flexible Windowing (Phase 7 - 2025-01-07)**:
- ✅ Period-based grouping (day/week/month) → flexible windowing
- ✅ Support multiple units: `messages` (count), `hours`/`days` (time), `bytes` (text size ~4 bytes/token)
- ✅ Sequential window indices (0, 1, 2...) instead of calendar keys ("2025-W03")
- ✅ Windows are runtime-only (NOT persisted to DB - depend on dynamic config)
- ✅ CLI params: `--step-size`, `--step-unit`, `--min-window-size`
- ✅ Example: `create_windows(table, step_size=100, step_unit="messages")`
- ❌ Don't create DB schemas for windows (they're transient views of CONVERSATION_SCHEMA)
- ❌ Don't use `tokens` unit (replaced with `bytes` for simplicity/speed)

## Code Structure

```
src/egregora/
├── cli.py                    # Typer CLI (entry point)
├── pipeline.py               # Windowing utilities (create_windows, Window dataclass)
├── database/
│   ├── schema.py            # ALL table schemas (CONVERSATION_SCHEMA, RAG_CHUNKS_SCHEMA, etc.)
│   └── connection.py        # DuckDB connection management
├── config/
│   ├── types.py             # Config dataclasses
│   ├── pipeline.py          # Pipeline-specific configs
│   └── site.py              # Site/MkDocs config loading
├── ingestion/
│   ├── base.py              # Abstract base classes (InputSource, InputMetadata)
│   ├── slack_input.py       # Slack source (future)
│   └── __init__.py          # Re-exports from sources/ for convenience
├── sources/
│   └── whatsapp/            # Phase 6: WhatsApp-specific code moved here
│       ├── grammar.py       # pyparsing grammar for message format
│       ├── parser.py        # parse_source() - WhatsApp export parsing
│       ├── input.py         # WhatsAppInputSource implementation
│       ├── models.py        # WhatsAppExport dataclass
│       └── pipeline.py      # discover_chat_file() helper
├── privacy/
│   ├── anonymizer.py        # UUID generation (deterministic hashing)
│   └── detector.py          # PII regex patterns
├── enrichment/
│   ├── core.py              # LLM enrichment (URLs, media)
│   ├── batch.py             # Batch API handling
│   └── avatar.py            # Avatar download/validation
├── agents/
│   ├── writer/
│   │   ├── writer_agent.py  # Main Pydantic-AI agent
│   │   ├── tools.py         # Tool definitions
│   │   └── context.py       # RAG context loading
│   ├── editor/
│   │   └── editor_agent.py  # Interactive post refinement
│   ├── ranking/
│   │   ├── ranking_agent.py # Elo pairwise comparisons
│   │   └── elo.py           # Elo algorithm
│   └── tools/
│       ├── rag/             # Vector store (DuckDB VSS)
│       ├── annotations/     # Conversation metadata
│       └── profiler.py      # Author profiles
├── utils/
│   ├── gemini_dispatcher.py # LLM API client (handles retries, batching)
│   ├── cache.py             # DiskCache wrapper
│   └── logfire_config.py    # Observability (Pydantic Logfire)
└── rendering/
    ├── mkdocs.py            # MkDocs renderer
    └── templates/           # Jinja2 templates
```

## Database Schemas

All schemas are centralized in `src/egregora/database/schema.py`:

**Ephemeral (in-memory, never persisted)**:
- `CONVERSATION_SCHEMA` - Pipeline data (timestamp, author, message, etc.)
- `WHATSAPP_CONVERSATION_SCHEMA` - Alias for CONVERSATION_SCHEMA

**Persistent (DuckDB + Parquet)**:
- `RAG_CHUNKS_SCHEMA` - Vector embeddings for RAG retrieval
- `RAG_CHUNKS_METADATA_SCHEMA` - Parquet file metadata (mtime, size, row_count)
- `RAG_INDEX_META_SCHEMA` - ANN index metadata
- `ANNOTATIONS_SCHEMA` - Conversation threading/metadata
- `ELO_RATINGS_SCHEMA` - Post quality rankings

**Key invariant**: All pipeline stages must accept and return tables conforming to `CONVERSATION_SCHEMA`.

## Testing Strategy

### Test Organization

- `tests/unit/` - Pure functions, no external dependencies
- `tests/integration/` - DuckDB, API calls (VCR cassettes)
- `tests/e2e/` - Full pipeline runs with golden fixtures
- `tests/agents/` - Pydantic-AI agent tests
- `tests/evals/` - LLM output quality evaluations
- `tests/linting/` - Code quality checks (imports, style)

### VCR Cassettes

Tests use `pytest-vcr` to record/replay Gemini API interactions:

- **First run**: Real API calls → saved to `tests/cassettes/*.yaml`
- **Subsequent runs**: Replay from cassettes (no API key needed)
- **Re-recording**: Delete cassettes, set `GOOGLE_API_KEY`, re-run tests

**VSS Extension**: Tests use `--retrieval-mode=exact` to avoid VSS extension dependency in CI.

### Golden Fixtures

End-to-end tests compare output against golden files in `tests/fixtures/golden/expected_output/`:

```bash
# Run with golden comparison
uv run pytest tests/e2e/test_with_golden_fixtures.py

# Update golden files (when intentionally changing output)
# Delete old output and re-run tests
```

## Configuration

### Environment Variables

**MODERN (Phase 2-4)**: Most configuration moved to `.egregora/config.yml`. Only credentials remain as env vars:

```bash
GOOGLE_API_KEY          # Required for Gemini API (keep out of git)
```

### Egregora Config (`.egregora/config.yml`)

**MODERN (Phase 2-4)**: Configuration lives in `.egregora/config.yml` (Pydantic `EgregoraConfig` model), separate from MkDocs.

Generated sites have this structure:

```
site-root/
├── mkdocs.yml              # MkDocs-only config (theme, plugins, nav)
├── .egregora/              # Egregora configuration directory
│   ├── config.yml          # Main configuration file
│   ├── prompts/            # Optional custom prompt overrides
│   │   ├── README.md       # Usage guide
│   │   ├── system/
│   │   │   ├── writer.jinja     # Custom writer prompt
│   │   │   └── editor.jinja     # Custom editor prompt
│   │   └── enrichment/
│   │       ├── url_simple.jinja
│   │       └── media_simple.jinja
│   └── .gitignore
└── .egregora-cache/        # Cache directory (gitignored)
```

**Example `.egregora/config.yml`** (maps to `EgregoraConfig` in `config/schema.py`):

```yaml
# Model configuration (pydantic-ai format: provider:model-name)
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
  ranking: google-gla:gemini-2.0-flash-exp
  editor: google-gla:gemini-2.0-flash-exp

# RAG (Retrieval-Augmented Generation) settings
rag:
  enabled: true
  top_k: 5
  min_similarity: 0.7
  mode: ann                    # "ann" or "exact"
  nprobe: 10                   # ANN quality (higher = better, slower)
  embedding_dimensions: 768

# Writer agent settings
writer:
  custom_instructions: |
    Write analytical posts in the style of Scott Alexander / LessWrong.
  enable_banners: true
  max_prompt_tokens: 100000

# Pipeline windowing settings
pipeline:
  step_size: 100
  step_unit: messages          # "messages", "hours", "days", "bytes"
  min_window_size: 10
  overlap_ratio: 0.0
```

### Custom Prompt Overrides

Place custom Jinja2 templates in `.egregora/prompts/` to override package defaults:

**Priority order** (highest to lowest):
1. Custom prompts in `{site_root}/.egregora/prompts/`
2. Package defaults in `src/egregora/prompts/`

**Example**: Override writer prompt

```bash
# Copy default template
mkdir -p .egregora/prompts/system
cp src/egregora/prompts/system/writer.jinja .egregora/prompts/system/writer.jinja

# Edit to customize
vim .egregora/prompts/system/writer.jinja
```

Agents automatically use custom prompts when found. Check logs for confirmation:
```
INFO:egregora.prompt_templates:Using custom prompts from /path/to/.egregora/prompts
```

## Development Workflow

### Adding a New Feature

1. **Understand the stage** - Which pipeline stage does this affect?
2. **Check schemas** - Does `CONVERSATION_SCHEMA` need updates? (rarely)
3. **Write tests first** - Add test in appropriate `tests/` subdirectory
4. **Keep it simple** - Can the LLM do this with better prompting?
5. **Update docs** - Add docstrings, update CLAUDE.md if architecture changes

### Modifying Pipeline Stages

**Critical rules**:
- All stages accept `Table` → return `Table`
- Privacy stage MUST run before any LLM processing
- Preserve `CONVERSATION_SCHEMA` columns throughout pipeline
- Add new columns via `.mutate()`, never drop core columns

### Adding LLM Tools (Writer Agent)

1. Define tool in `src/egregora/agents/writer/tools.py`
2. Register in `ToolRegistry` (`agents/registry.py`)
3. Add to agent initialization in `writer_agent.py`
4. Test with VCR cassette recording

### Debugging Tips

```python
# Inspect Ibis tables
table = parse_export(zip_path)
print(table.schema())
print(table.limit(5).execute())  # Convert to pandas for inspection

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check DuckDB VSS extension
import duckdb
conn = duckdb.connect()
conn.execute("INSTALL vss; LOAD vss")
conn.execute("SELECT * FROM duckdb_extensions() WHERE extension_name = 'vss'")
```

## TENET-BREAK Philosophy

Egregora uses `TENET-BREAK` comments for intentional violations of core principles:

**Core tenets**:
- `no-compat` - No backwards compatibility shims
- `clean` - Clean code; clarity over cleverness
- `no-defensive` - Don't guard against impossible states (trust types + tests)
- `propagate-errors` - Let errors bubble; don't swallow

**Format**:
```python
# TENET-BREAK(scope)[@owner][P0|P1|P2][due:YYYY-MM-DD]:
# tenet=<code>; why=<constraint>; exit=<condition> (#issue)
```

See `CONTRIBUTING.md` for full details and examples.

## Privacy & Security

**Anonymization flow**:
1. Parse WhatsApp export → real names in memory
2. Generate deterministic UUIDs (same person = same UUID across runs)
3. Replace names with UUIDs BEFORE any LLM API call
4. PII detection: scan for phones, emails, addresses
5. Only anonymized data sent to Gemini API

**User controls** (in-chat commands):
```
/egregora set alias "Casey"       # Set display name
/egregora set bio "AI researcher" # Add profile
/egregora opt-out                 # Exclude from posts
/egregora opt-in                  # Re-include
```

## Common Pitfalls

1. **Don't bypass privacy stage** - Never send raw conversation data to LLM APIs
2. **Use Ibis, not pandas** - Convert to pandas only at boundaries (display, serialization)
3. **Respect schemas** - Don't add arbitrary columns without updating `database/schema.py`
4. **VCR cassettes** - Commit cassettes to repo so tests run without API keys
5. **VSS extension** - Use `--retrieval-mode=exact` in environments without DuckDB VSS

## Dependencies

**Core stack**:
- **Ibis** - DataFrame API (type-safe transformations)
- **DuckDB** - Analytics database + VSS extension (vector search)
- **Pydantic-AI** - LLM agent framework
- **Google Gemini** - Content generation API
- **MkDocs Material** - Static site generation
- **uv** - Fast Python package manager

**Optional**:
- **pytest-vcr** - HTTP recording for deterministic tests
- **Pydantic Logfire** - Observability (opt-in via env var)

## Deployment

```bash
# Build static site
cd output
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy

# Or use: Netlify, Vercel, Cloudflare Pages
# (deploy the ./site directory generated by mkdocs build)
```

## Related Documentation

- `README.md` - User-facing documentation, quick start
- `CONTRIBUTING.md` - Detailed contributor guide, TENET-BREAK philosophy
- `docs/` - Comprehensive guides (architecture, privacy, API reference)
- `tests/fixtures/golden/` - Example outputs from real pipeline runs
