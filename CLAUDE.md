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

# Write blog posts from WhatsApp export (creates blog in ./output, default: 1 day windows)
uv run egregora write whatsapp-export.zip --output=./output

# Time-based windowing (default)
uv run egregora write export.zip --step-size=1 --step-unit=days  # 1 day (default)
uv run egregora write export.zip --step-size=7 --step-unit=days  # 1 week

# Message count windowing
uv run egregora write export.zip --step-size=100 --step-unit=messages

# Serve generated blog locally
cd output
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve

# Other commands
uv run egregora edit posts/my-post.md        # AI-powered post editor
uv run egregora rank --site-dir=. --comparisons=50  # Elo ranking

# Run tracking (observability)
uv run egregora runs tail               # View recent pipeline runs
uv run egregora runs show <run_id>      # View detailed run info
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

## Post-Commit Reflection Workflow

After each commit and push, take a moment to reflect on lessons learned from the work. This helps capture institutional knowledge and improve future development sessions.

### Reflection Process

1. **After each commit/push**, pause and reflect on:
   - What technical decisions were made and why
   - What worked well in the implementation
   - What could be improved next time
   - Any error patterns or debugging insights
   - Architecture insights or design tradeoffs

2. **Document valuable reflections** by asking the user for permission to update CLAUDE.md with these insights

3. **Add reflections to relevant sections**:
   - Technical patterns → "Development Workflow" or "Modern Patterns" sections
   - Common errors → "Common Pitfalls" section
   - Testing insights → "Testing Strategy" section
   - Architecture decisions → "Architecture: Staged Pipeline" section

### What Makes a Good Reflection

**Examples of valuable reflections**:
- "Extracted tracking code to separate module during merge to prevent future conflicts - clean separation is better than large monolithic files"
- "UUID serialization in Ibis memtables requires converting to strings first, let Ibis cast back to UUID type"
- "Content-addressed checkpointing with SHA256 enables deterministic pipeline resumption across runs"
- "Two-level validation (compile-time + runtime) provides safety without blocking execution"

**What to capture**:
- Architecture decisions that deviate from obvious approaches
- Non-obvious error fixes that took time to debug
- Patterns that emerged across multiple similar tasks
- Trade-offs made between competing design principles

**What to skip**:
- Obvious fixes (typos, simple syntax errors)
- One-off decisions unlikely to recur
- Implementation details already documented in code comments

### Integration with Roadmap Progression

After completing each task and reflecting on lessons learned:

1. **Suggest the next task** from the architecture roadmap
2. **Explain why** that task is the logical next step
3. **Reference dependencies** between completed and upcoming work
4. **Continue systematically** through roadmap priorities

This ensures steady progress while capturing knowledge for future sessions.

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

**View Registry (Priority C.1 - 2025-01-09)**:
- ✅ Callable view builders: `ViewBuilder = Callable[[Table], Table]`
- ✅ Centralized registry for pipeline transformations
- ✅ Transparent Ibis ↔ SQL swapping for performance
- ✅ Reference views by name, not implementation
- ✅ Example: `chunks_builder = views.get("chunks"); result = chunks_builder(table)`
- ✅ Built-in views: `chunks`, `chunks_optimized`, `hourly_aggregates`, `daily_aggregates`
- ✅ Register custom views with decorator: `@views.register("my_view")`
- ❌ Don't confuse with `database/views.py` (SQL materialized views for query optimization)
- See `docs/pipeline/view-registry.md` for full guide

**StorageManager (Priority C.2 - 2025-01-09)**:
- ✅ Centralized DuckDB connection management
- ✅ Automatic parquet checkpointing for persistence
- ✅ Integrated with ViewRegistry for executing views
- ✅ Context manager support: `with StorageManager() as storage:`
- ✅ Example: `storage.write_table(table, "name", checkpoint=True)`
- ✅ Table operations: read, write, drop, exists, list
- ✅ View execution: `storage.execute_view("output", builder, "input")`
- ❌ Don't use raw SQL - use StorageManager methods
- See `docs/database/storage-manager.md` for full guide

**Stage Validation (Priority C.3 - 2025-01-09)**:
- ✅ `@validate_stage` decorator for automatic IR v1 schema validation
- ✅ Validates both input and output of pipeline stages
- ✅ Two-level validation: compile-time (schema structure) + runtime (sample rows)
- ✅ Ensures stages preserve IR v1 contract throughout transformations
- ✅ Example: `@validate_stage def process(self, data: Table, context) -> StageResult:`
- ✅ Helpful error messages with stage context
- ❌ Don't drop required IR columns or change types in stages
- See `docs/pipeline/stage-validation.md` for full guide

**Pipeline Run Tracking (Priority D.1 - 2025-01-09)**:
- ✅ Automatic window-level tracking in `.egregora/runs.duckdb`
- ✅ Records: run_id, stage, status, duration, rows processed, errors
- ✅ CLI commands: `egregora runs tail` (recent runs), `egregora runs show <run_id>` (details)
- ✅ Status transitions: running → completed/failed
- ✅ Graceful error handling: tracking failures logged but don't block pipeline
- ✅ Example: Every window creates a run record automatically
- ✅ Debug failures: `egregora runs tail` to find failed runs, `show <run_id>` for error details
- ✅ Performance monitoring: Track duration per window, identify bottlenecks
- ❌ Don't rely on runs database for critical pipeline logic (it's observability only)
- See `docs/observability/runs-tracking.md` for full guide

**OpenTelemetry Integration (Priority D.2 - 2025-01-10)**:
- ✅ Vendor-neutral observability framework (opt-in via `EGREGORA_OTEL=1`)
- ✅ Logfire as optional exporter (Pydantic's OTEL-compatible platform)
- ✅ No mandatory API keys - works with console exporter by default
- ✅ Exporter priority: Logfire → OTLP → Console (first available wins)
- ✅ Automatic trace_id capture and storage in runs database
- ✅ Links pipeline runs to distributed traces for deep debugging
- ✅ Example usage:
  ```bash
  # Console exporter (default, no API key needed)
  export EGREGORA_OTEL=1
  egregora write export.zip

  # Logfire exporter (optional, requires token)
  export EGREGORA_OTEL=1
  export LOGFIRE_TOKEN=your_token
  egregora write export.zip

  # Generic OTLP collector
  export EGREGORA_OTEL=1
  export OTEL_EXPORTER_OTLP_ENDPOINT=https://collector:4317
  egregora write export.zip
  ```
- ✅ Functions: `get_tracer()`, `get_current_trace_id()`, `configure_otel()`, `shutdown_otel()`
- ✅ Trace context automatically propagated through pipeline stages
- ❌ Don't use Logfire-specific APIs directly - use OTEL APIs for portability
- ❌ Don't require OTEL for core functionality - it's observability only

**Agent Skill Injection (2025-01-11)**:
- ✅ Dynamic capability extension for pydantic-ai agents via `use_skill()` tool
- ✅ Sub-agent spawning with isolated context (parent agent only sees summary)
- ✅ Skills stored in `.egregora/skills/` as Markdown/text files
- ✅ Sub-agents have full parent context + skill instructions + special `end_skill_use()` tool
- ✅ Clean context management: skill work doesn't bloat parent conversation history
- ✅ Example skills in `.egregora/skills/example-skill.md` and README
- ✅ Architecture:
  ```
  Parent Agent
      ↓ use_skill("github-api", "Analyze PR #123")
      ↓
  Sub-Agent (spawned)
      - Parent's model + tools
      - + Skill content injected
      - + end_skill_use() tool
      ↓ [does specialized work]
      ↓ end_skill_use("Found 2 security issues: ...")
      ↓
  Parent Agent receives summary only
  ```
- ✅ Creating skills:
  ```markdown
  # Skill Name

  Brief description of capability.

  ## Instructions
  1. Do X
  2. Analyze Y
  3. Call end_skill_use(summary)

  ## Examples
  Task: "Analyze XYZ"
  Output: "Found 3 insights..."
  ```
- ✅ **Enabling skill injection in agents**:
  Parent agent deps must implement `SkillInjectionSupport` protocol:
  ```python
  from egregora.agents.tools import SkillInjectionSupport

  class MyAgentState(BaseModel):
      # ... existing fields ...

      # For skill injection support (required properties)
      @property
      def agent_model(self) -> Model:
          return self._model  # Store model reference

      @property
      def agent_tools(self) -> list[Any]:
          return self._tools  # Store tools list (excluding use_skill)

      @property
      def agent_system_prompt(self) -> str:
          return self._system_prompt  # Store system prompt
  ```
- ✅ **Using skills from agents**:
  ```python
  # In agent tool or workflow
  result = await use_skill(
      ctx,
      skill_name="data-analysis",
      task="Generate hourly message distribution stats"
  )
  # result contains sub-agent's summary
  # Sub-agent has full access to parent's storage, RAG, etc. via ctx.deps
  ```
- ✅ **Dependency inheritance**: Sub-agent receives parent's deps, so parent tools work correctly
- ✅ Completion signal: Sub-agent calls `end_skill_use(summary)` or finishes naturally
- ✅ Files: `agents/tools/skill_loader.py` (loader), `agents/tools/skill_injection.py` (tool)
- ✅ Tests: `tests/agents/test_skill_injection.py` (13 unit tests)
- ❌ Don't use skills for simple tasks (overhead of sub-agent spawning)
- ❌ Don't let sub-agents commit/push (causes conflicts with parent)
- 📖 See `.egregora/skills/README.md` for full guide

## Code Structure

```
src/egregora/
├── cli.py                    # Typer CLI (entry point)
├── pipeline.py               # Windowing utilities (create_windows, Window dataclass)
├── database/
│   ├── schema.py            # ALL table schemas (CONVERSATION_SCHEMA, RAG_CHUNKS_SCHEMA, etc.)
│   ├── connection.py        # DuckDB connection management
│   ├── storage.py           # StorageManager for centralized DB access (Priority C.2)
│   ├── validation.py        # IR schema validation
│   └── views.py             # SQL materialized views (database query optimization)
├── config/
│   ├── types.py             # Config dataclasses
│   ├── pipeline.py          # Pipeline-specific configs
│   └── site.py              # Site/MkDocs config loading
├── pipeline/
│   ├── base.py              # PipelineStage protocol
│   ├── ir.py                # IR schema and validation
│   ├── views.py             # View registry for pipeline transformations (Priority C.1)
│   ├── tracking.py          # Run tracking and lineage
│   ├── checkpoint.py        # Content-addressed checkpointing
│   └── adapters.py          # SourceAdapter protocol
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
│       ├── profiler.py      # Author profiles
│       ├── skill_loader.py  # Skill loading from .egregora/skills/
│       └── skill_injection.py  # use_skill tool and sub-agent spawning
├── utils/
│   ├── gemini_dispatcher.py # LLM API client (handles retries, batching)
│   ├── cache.py             # DiskCache wrapper
│   ├── telemetry.py         # OpenTelemetry instrumentation (Priority D.2)
│   └── logfire_config.py    # Logfire helpers (deprecated - use telemetry.py)
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

### Model Thinking/Reasoning

**MODERN (2025-01)**: Egregora tracks all token types including thinking/reasoning tokens used by advanced models.

Some models support "thinking" or "reasoning" - internal step-by-step problem-solving before generating the final answer. This uses additional tokens but can improve output quality for complex tasks.

#### Enabling Thinking

**For Google Gemini models**, add model settings to enable thinking:

```python
# In your agent code or config
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings

model = GoogleModel('gemini-2.5-pro')
settings = GoogleModelSettings(
    google_thinking_config={'include_thoughts': True}
)
agent = Agent(model, model_settings=settings)
```

**For Anthropic Claude models**:

```python
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings

model = AnthropicModel('claude-sonnet-4-0')
settings = AnthropicModelSettings(
    anthropic_thinking={'type': 'enabled', 'budget_tokens': 1024}
)
agent = Agent(model, model_settings=settings)
```

See [Pydantic AI Thinking docs](https://ai.pydantic.dev/thinking/) for other providers (OpenAI, Bedrock, Groq, Mistral, Cohere).

#### Token Tracking

Egregora comprehensively tracks all token types in agent usage logs:

**Standard tokens**:
- `tokens_input` - Input/prompt tokens
- `tokens_output` - Output/completion tokens
- `tokens_total` - Total tokens (input + output)

**Cache tokens** (prompt caching for cost savings):
- `tokens_cache_write` - Tokens written to cache
- `tokens_cache_read` - Tokens read from cache
- `tokens_cache_audio_read` - Audio tokens read from cache

**Audio tokens** (multimodal models):
- `tokens_input_audio` - Audio input tokens

**Thinking/reasoning tokens** (model-specific):
- `tokens_thinking` - Thinking tokens (from `usage.details['thinking_tokens']`)
- `tokens_reasoning` - Reasoning tokens (from `usage.details['reasoning_tokens']`)
- `usage_details` - Raw details dict for other model-specific metrics

**Example log output** (with thinking enabled):
```
INFO:egregora.utils.logfire_config:Writer agent completed
  period=2025-01-15 10:00 to 12:00
  posts_created=2
  profiles_updated=3
  journal_saved=True               # Journal entry saved to .md file
  journal_entries=25               # Total journal entries
  journal_thinking_entries=8       # Number of thinking sections
  journal_freeform_entries=12      # Number of freeform sections
  journal_tool_calls=5             # Number of tool invocations
  tokens_total=15420
  tokens_input=12000
  tokens_output=3420
  tokens_cache_write=0
  tokens_cache_read=8000
  tokens_thinking=2100             # Thinking tokens used
  tokens_reasoning=0
  usage_details={'thinking_tokens': 2100}
```

All token metrics are logged to **Pydantic Logfire** (if enabled) for observability and cost tracking.

#### Saving Journal Entries

**MODERN (2025-01)**: Egregora automatically saves journal entries combining the model's thinking and freeform reflection for each window.

**Where journal files are saved**:
```
output/
├── posts/                    # Generated blog posts
├── profiles/                 # Author profiles
└── journal/                  # Model journal entries
    ├── journal_2025-01-15_10-00_to_12-00.md
    ├── journal_2025-01-15_12-00_to_14-00.md
    └── ...
```

**Journal structure** (Jinja template: `src/egregora/templates/journal.md.jinja`):

Each journal entry is an **intercalated execution log** showing the agent's complete thought process in chronological order:

1. **Thinking sections** - Step-by-step reasoning (from ThinkingPart)
2. **Freeform sections** - Continuity memos and reflections (from TextPart)
3. **Tool calls** - Tool invocations with XML tag fencing (e.g., `<tool-call name="write_post">`)
4. **Tool returns** - Tool results with XML tag fencing (e.g., `<tool-return name="write_post">`)

**Example journal entry** (`journal/journal_2025-01-15_10-00_to_12-00.md`):
```markdown
---
window_label: 2025-01-15 10:00 to 12:00
date: 2025-01-15
created: 2025-01-15T12:05:23.123456+00:00
draft: true
---

# Agent Execution Log

## Thinking

Let me analyze these conversations to identify the main themes...

First, I notice several recurring topics:
1. Technical discussions about AI development
2. Personal anecdotes about remote work
3. Philosophical questions about consciousness

Based on this analysis, I'll create a post focusing on...

<tool-call name="write_post">
Tool: write_post
Arguments:
{
  "metadata": {
    "title": "The Emergence of AI Consciousness Debates",
    "date": "2025-01-15"
  },
  "content": "..."
}
</tool-call>

<tool-return name="write_post">
Result: {'status': 'success', 'path': '/output/posts/ai-consciousness.md'}
</tool-return>

## Freeform

# Continuity Journal — 2025-01-15

## Post-Mortem and Synthesis Decisions

This writing period was defined by rich technical discussion...
I chose to focus on the emergence of AI consciousness debates...

## Unresolved Tensions and Future Inquiry

The central unresolved question is: What constitutes genuine understanding?

## Memory and Context Persistence

Key context to carry forward: the self-referential nature of consciousness...
```

**Benefits**:
- **Transparency**: See internal reasoning, editorial decisions, AND tool usage in execution order
- **Debugging**: Understand why certain posts were created or skipped, and which tools were called
- **Improvement**: Identify patterns to refine prompts, model settings, and tool usage
- **Audit trail**: Complete chronological record of AI decision-making and actions
- **Continuity**: Freeform sections become memory for next window
- **Tool visibility**: XML-fenced tool calls show exact arguments and results

**Format**:
- YAML frontmatter with ISO 8601 timestamp (`created` field)
- Simple `##` headings for thinking/freeform sections
- XML tags for tool usage (`<tool-call>`, `<tool-return>`)
- Chronological interleaving preserves actual execution order

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
- **mkdocs-rss-plugin** - RSS feed generation for blog posts (install with `uv sync --extra rss`)

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
